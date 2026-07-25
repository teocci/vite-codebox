package command

import "context"

// buildFlags carries the flags a world-facing verb may accept. Every field is a
// value, not a pointer: a verb registers only its own flags, and the fields it
// never registers keep their zero value rather than a nil pointer to deref.
type buildFlags struct {
	flagSurface

	backend  string
	cfgPath  string
	endpoint string
	insecure bool
	asJSON   bool

	dryRun  bool
	refresh bool
	family  string
	at      string
	size    string
	radius  int
	height  int
	id      int
	mat     string
}

// registerCommon adds the five flags every world-facing verb accepts.
func (b *buildFlags) registerCommon() {
	b.fs.StringVar(&b.backend, "backend", "", "credential backend: keyring or file")
	b.fs.StringVar(&b.cfgPath, "config", "", "path to the settings file")
	b.fs.StringVar(&b.endpoint, "endpoint", "", "server endpoint (ws:// or wss://)")
	b.fs.BoolVar(&b.insecure, "insecure", false, "allow plain ws:// to a remote host")
	b.fs.BoolVar(&b.asJSON, "json", false, "emit a compact JSON report")
}

func (b *buildFlags) registerDryRun() {
	b.fs.BoolVar(&b.dryRun, "dry-run", false, "validate against the contract without sending")
}

func (b *buildFlags) registerPlacement() {
	b.registerDryRun()
	b.fs.StringVar(&b.at, "at", "", "position as x,y,z (box: min corner; sphere/cylinder: centre)")
	b.fs.StringVar(&b.mat, "mat", "", "material name")
}

// buildVerbs declares each world-facing verb's flag surface beyond the common
// five. A verb absent from this map does not exist — the lookup is what rejects
// an unknown command before anything opens a credential store.
var buildVerbs = map[string]func(*buildFlags){
	"info": func(*buildFlags) {},
	"materials": func(b *buildFlags) {
		b.fs.StringVar(&b.family, "family", "", "limit materials to one render family")
		b.fs.BoolVar(&b.refresh, "refresh", false, "re-fetch the contract instead of using the cache")
	},
	"exec":  (*buildFlags).registerDryRun,
	"clear": (*buildFlags).registerDryRun,
	"remove": func(b *buildFlags) {
		b.registerDryRun()
		b.fs.IntVar(&b.id, "id", -1, "part id to remove")
	},
	"box": func(b *buildFlags) {
		b.registerPlacement()
		b.fs.StringVar(&b.size, "size", "", "box extent as w,h,d")
	},
	"sphere": func(b *buildFlags) {
		b.registerPlacement()
		b.fs.IntVar(&b.radius, "r", 0, "radius in blocks")
	},
	"cylinder": func(b *buildFlags) {
		b.registerPlacement()
		b.fs.IntVar(&b.radius, "r", 0, "radius in blocks")
		b.fs.IntVar(&b.height, "h", 0, "height in blocks")
	},
}

// newBuildFlags builds the flag set for one verb, or reports that the verb does
// not exist.
func newBuildFlags(verb string) (*buildFlags, error) {
	register, ok := buildVerbs[verb]
	if !ok {
		return nil, usagef("unknown command %q", verb)
	}
	b := &buildFlags{flagSurface: newFlagSurface(verb), id: -1}
	b.registerCommon()
	register(b)
	return b, nil
}

func (b *buildFlags) exec() ExecOptions {
	return ExecOptions{
		Endpoint: b.endpoint, ConfigPath: b.cfgPath, Insecure: b.insecure,
		JSON: b.asJSON, DryRun: b.dryRun,
	}
}

// dispatchBuild routes the world-facing verbs. Argv is fully validated, and the
// verb's own command is built, before the credential store is opened — nothing
// should touch the keyring to discover that --mat is missing.
func dispatchBuild(ctx context.Context, d Deps, verb string, args []string) error {
	f, err := newBuildFlags(verb)
	if err != nil {
		return err
	}
	if err := f.parse(args); err != nil {
		return err
	}
	cmd, err := f.command()
	if err != nil {
		return err
	}

	app, err := d.app(f.backend)
	if err != nil {
		return err
	}

	switch verb {
	case "info":
		return app.Info(ctx, InfoOptions{
			Endpoint: f.endpoint, ConfigPath: f.cfgPath, Insecure: f.insecure, JSON: f.asJSON,
		})
	case "materials":
		return app.Materials(ctx, MaterialsOptions{
			Endpoint: f.endpoint, ConfigPath: f.cfgPath, Insecure: f.insecure,
			JSON: f.asJSON, Family: f.family, Refresh: f.refresh,
		})
	case "exec":
		return app.Exec(ctx, f.exec())
	default:
		return app.RunOne(ctx, cmd, f.exec())
	}
}

// command builds the single command a verb sends, validating that verb's own
// flags. It returns nil for the verbs that send no single command.
func (b *buildFlags) command() (map[string]any, error) {
	switch b.verb {
	case "info", "materials", "exec":
		return nil, nil
	case "clear":
		return map[string]any{"op": "clear"}, nil
	case "remove":
		if b.id < 0 {
			return nil, usagef("remove needs --id <non-negative integer>")
		}
		return map[string]any{"op": "remove", "id": float64(b.id)}, nil
	default:
		return shapeCommand(b)
	}
}

// shapeCommand builds the command for an ergonomic part verb.
func shapeCommand(b *buildFlags) (map[string]any, error) {
	if b.mat == "" {
		return nil, usagef("%s needs --mat <material> (run `codeblox materials`)", b.verb)
	}
	if b.at == "" {
		return nil, usagef("%s needs --at x,y,z", b.verb)
	}
	at, err := ParseInt3(b.at)
	if err != nil {
		return nil, usagef("--at: %w", err)
	}
	cmd := map[string]any{"op": b.verb, "at": at, "mat": b.mat}

	switch b.verb {
	case "box":
		if b.size == "" {
			return nil, usagef("box needs --size w,h,d")
		}
		size, err := ParseInt3(b.size)
		if err != nil {
			return nil, usagef("--size: %w", err)
		}
		cmd["size"] = size
	case "sphere":
		if b.radius <= 0 {
			return nil, usagef("sphere needs --r <positive integer>")
		}
		cmd["r"] = float64(b.radius)
	case "cylinder":
		if b.radius <= 0 || b.height <= 0 {
			return nil, usagef("cylinder needs --r and --h as positive integers")
		}
		cmd["r"] = float64(b.radius)
		cmd["h"] = float64(b.height)
	}
	return cmd, nil
}
