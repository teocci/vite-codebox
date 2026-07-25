package command

import (
	"context"
	"flag"
	"fmt"
)

// buildFlags is the flag set shared by every world-facing verb.
type buildFlags struct {
	fs       *flag.FlagSet
	backend  *string
	cfgPath  *string
	endpoint *string
	insecure *bool
	asJSON   *bool
	dryRun   *bool
	refresh  *bool
	family   *string
	at       *string
	size     *string
	radius   *int
	height   *int
	id       *int
	mat      *string
}

func newBuildFlags(verb string, out interface{ Write([]byte) (int, error) }) *buildFlags {
	fs := flag.NewFlagSet(verb, flag.ContinueOnError)
	fs.SetOutput(out)
	return &buildFlags{
		fs:       fs,
		backend:  fs.String("backend", "", "credential backend: keyring or file"),
		cfgPath:  fs.String("config", "", "path to the settings file"),
		endpoint: fs.String("endpoint", "", "server endpoint (ws:// or wss://)"),
		insecure: fs.Bool("insecure", false, "allow plain ws:// to a remote host"),
		asJSON:   fs.Bool("json", false, "emit a compact JSON report"),
		dryRun:   fs.Bool("dry-run", false, "validate against the contract without sending"),
		refresh:  fs.Bool("refresh", false, "re-fetch the contract instead of using the cache"),
		family:   fs.String("family", "", "limit materials to one render family"),
		at:       fs.String("at", "", "position as x,y,z (box: min corner; sphere/cylinder: centre)"),
		size:     fs.String("size", "", "box extent as w,h,d"),
		radius:   fs.Int("r", 0, "radius in blocks"),
		height:   fs.Int("h", 0, "height in blocks"),
		id:       fs.Int("id", -1, "part id to remove"),
		mat:      fs.String("mat", "", "material name"),
	}
}

func (b *buildFlags) exec() ExecOptions {
	return ExecOptions{
		Endpoint: *b.endpoint, ConfigPath: *b.cfgPath, Insecure: *b.insecure,
		JSON: *b.asJSON, DryRun: *b.dryRun,
	}
}

// dispatchBuild routes the world-facing verbs.
func dispatchBuild(ctx context.Context, d Deps, verb string, args []string) error {
	f := newBuildFlags(verb, d.Stderr)
	if err := f.fs.Parse(args); err != nil {
		return err
	}
	app, err := d.app(*f.backend)
	if err != nil {
		return err
	}

	switch verb {
	case "info":
		return app.Info(ctx, InfoOptions{
			Endpoint: *f.endpoint, ConfigPath: *f.cfgPath, Insecure: *f.insecure, JSON: *f.asJSON,
		})
	case "materials":
		return app.Materials(ctx, MaterialsOptions{
			Endpoint: *f.endpoint, ConfigPath: *f.cfgPath, Insecure: *f.insecure,
			JSON: *f.asJSON, Family: *f.family, Refresh: *f.refresh,
		})
	case "exec":
		return app.Exec(ctx, f.exec())
	case "clear":
		return app.RunOne(ctx, map[string]any{"op": "clear"}, f.exec())
	case "remove":
		if *f.id < 0 {
			return fmt.Errorf("remove needs --id <non-negative integer>")
		}
		return app.RunOne(ctx, map[string]any{"op": "remove", "id": float64(*f.id)}, f.exec())
	case "box", "sphere", "cylinder":
		cmd, err := shapeCommand(verb, f)
		if err != nil {
			return err
		}
		return app.RunOne(ctx, cmd, f.exec())
	default:
		return fmt.Errorf("unknown command %q", verb)
	}
}

// shapeCommand builds the command for an ergonomic part verb.
func shapeCommand(verb string, f *buildFlags) (map[string]any, error) {
	if *f.mat == "" {
		return nil, fmt.Errorf("%s needs --mat <material> (run `codeblox materials`)", verb)
	}
	if *f.at == "" {
		return nil, fmt.Errorf("%s needs --at x,y,z", verb)
	}
	at, err := ParseInt3(*f.at)
	if err != nil {
		return nil, fmt.Errorf("--at: %w", err)
	}
	cmd := map[string]any{"op": verb, "at": at, "mat": *f.mat}

	switch verb {
	case "box":
		if *f.size == "" {
			return nil, fmt.Errorf("box needs --size w,h,d")
		}
		size, err := ParseInt3(*f.size)
		if err != nil {
			return nil, fmt.Errorf("--size: %w", err)
		}
		cmd["size"] = size
	case "sphere":
		if *f.radius <= 0 {
			return nil, fmt.Errorf("sphere needs --r <positive integer>")
		}
		cmd["r"] = float64(*f.radius)
	case "cylinder":
		if *f.radius <= 0 || *f.height <= 0 {
			return nil, fmt.Errorf("cylinder needs --r and --h as positive integers")
		}
		cmd["r"] = float64(*f.radius)
		cmd["h"] = float64(*f.height)
	}
	return cmd, nil
}
