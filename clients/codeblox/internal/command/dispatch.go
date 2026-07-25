package command

import (
	"context"
	"errors"
	"fmt"
	"io"

	"github.com/teocci/vite-codebox/clients/codeblox/internal/config"
	"github.com/teocci/vite-codebox/clients/codeblox/internal/creds"
	"github.com/teocci/vite-codebox/clients/codeblox/internal/transport"
)

// Version is the CLI's own version, independent of the server's.
//
// This is a second version site: the project's source of truth is package.json,
// and a release must bump both. docs/conventions/tracking.md records that.
const Version = "0.5.0"

const usage = `codeblox — command a codeblox build server

auth:
  codeblox auth login  [--with-token] [--endpoint URL] [--backend keyring|file] [--config PATH]
  codeblox auth logout [--backend keyring|file]
  codeblox auth list   [--backend keyring|file] [--json]
  codeblox auth status [--endpoint URL] [--backend keyring|file] [--insecure] [--json]

discovery:
  codeblox info        [--json]              fetch and cache the world_info contract
  codeblox materials   [--family F] [--json] [--refresh]

building:
  codeblox exec        [--dry-run] [--json]  read a batch from stdin (JSON array, object, or NDJSON)
  codeblox box         --at x,y,z --size w,h,d --mat NAME
  codeblox sphere      --at x,y,z --r N --mat NAME
  codeblox cylinder    --at x,y,z --r N --h N --mat NAME
  codeblox remove      --id N
  codeblox clear

  codeblox version

Batches are validated against the server's published schema and palette before
anything is sent. World bounds are enforced by the server and reported in its ack.

credentials:
  The token is kept in the OS keyring by default, or a 0600 file store when no
  keyring is available. It is never written to the settings file and is always
  masked in output. ` + config.EnvToken + ` is a fallback for automation.

settings:
  Non-secret settings live in ~/` + config.DirName + `/` + config.FileName + `.
  The endpoint resolves as: --endpoint, then ` + config.EnvEndpoint + `,
  then the settings file, then ` + config.DefaultEndpoint + `.

exit codes:
  0 success                     2 usage — argv is wrong
  3 auth — no or bad credential 4 network — server unreachable or unsafe
  5 contract — rejected here, nothing sent
  6 server — sent, and the server refused it

  Failures go to stderr. With --json they are a single-line envelope:
  {"ok":false,"code":"...","exit":N,"detail":"..."} — so a caller parses one
  shape on both paths and branches on the code, never on the message text.
`

// Deps is everything Dispatch needs from the host. Injected so the whole CLI is
// exercisable in tests without a keyring, a home directory, or a network.
type Deps struct {
	Env    config.Env
	Stdin  io.Reader
	Stdout io.Writer
	Stderr io.Writer

	// Dial and OpenStore default to the real implementations when nil.
	Dial      func(context.Context, transport.Dialer) (Session, error)
	OpenStore func(config.Env, string) (creds.Backend, error)
	// PromptSecret reads a secret without echoing. nil means use the terminal;
	// injected so an interactive `auth login` is testable without one.
	PromptSecret func(prompt string) (string, error)
}

// Dispatch parses args and runs the requested verb.
func Dispatch(ctx context.Context, d Deps, args []string) error {
	if len(args) == 0 {
		// Usage goes to stderr and fails: a wrapper that computed an empty argv
		// must not read a success exit and a stdout blob as a result.
		fmt.Fprint(d.Stderr, usage)
		return fail(ExitUsage, "usage", errors.New("no command given — run `codeblox help`"))
	}

	switch args[0] {
	case "auth":
		return dispatchAuth(ctx, d, args[1:])
	case "info", "materials", "exec", "box", "sphere", "cylinder", "remove", "clear":
		return dispatchBuild(ctx, d, args[0], args[1:])
	case "version":
		fmt.Fprintf(d.Stdout, "codeblox %s\n", Version)
		return nil
	case "help", "-h", "--help":
		fmt.Fprint(d.Stdout, usage)
		return nil
	default:
		return usagef("unknown command %q — run `codeblox help`", args[0])
	}
}

// authFlags carries the flags an auth subcommand may accept. As with the build
// verbs, every field is a value: a subcommand registers only its own flags and
// the rest keep their zero value.
type authFlags struct {
	flagSurface

	backend   string
	cfgPath   string
	endpoint  string
	withToken bool
	insecure  bool
	asJSON    bool
}

// authSubs declares each subcommand's flag surface beyond --backend, which all
// of them accept because all of them open the credential store. A subcommand
// absent from this map does not exist.
var authSubs = map[string]func(*authFlags){
	"login": func(a *authFlags) {
		a.fs.StringVar(&a.cfgPath, "config", "", "path to the settings file")
		a.fs.StringVar(&a.endpoint, "endpoint", "", "server endpoint (ws:// or wss://)")
		a.fs.BoolVar(&a.withToken, "with-token", false, "read the token from stdin instead of prompting")
	},
	"logout": func(*authFlags) {},
	"list": func(a *authFlags) {
		a.fs.BoolVar(&a.asJSON, "json", false, "emit a compact JSON report")
	},
	"status": func(a *authFlags) {
		a.fs.StringVar(&a.cfgPath, "config", "", "path to the settings file")
		a.fs.StringVar(&a.endpoint, "endpoint", "", "server endpoint (ws:// or wss://)")
		a.fs.BoolVar(&a.insecure, "insecure", false, "allow sending the token over plain ws:// to a remote host")
		a.fs.BoolVar(&a.asJSON, "json", false, "emit a compact JSON report")
	},
}

func newAuthFlags(sub string) (*authFlags, error) {
	register, ok := authSubs[sub]
	if !ok {
		return nil, usagef("unknown auth subcommand %q: want login, logout, list, or status", sub)
	}
	a := &authFlags{flagSurface: newFlagSurface("auth " + sub)}
	a.fs.StringVar(&a.backend, "backend", "", "credential backend: keyring or file")
	register(a)
	return a, nil
}

// dispatchAuth routes the credential lifecycle verbs. The subcommand and its
// argv are validated before the credential store is opened, so an unknown
// subcommand never probes the keyring.
func dispatchAuth(ctx context.Context, d Deps, args []string) error {
	if len(args) == 0 {
		return usagef("`auth` needs a subcommand: login, logout, list, or status")
	}

	sub := args[0]
	f, err := newAuthFlags(sub)
	if err != nil {
		return err
	}
	if err := f.parse(args[1:]); err != nil {
		return err
	}

	app, err := d.app(f.backend)
	if err != nil {
		return err
	}

	switch sub {
	case "login":
		return app.Login(LoginOptions{
			FromStdin: f.withToken, Endpoint: f.endpoint, ConfigPath: f.cfgPath,
		})
	case "logout":
		return app.Logout()
	case "list":
		return app.List(f.asJSON)
	default:
		return app.Status(ctx, StatusOptions{
			Endpoint: f.endpoint, ConfigPath: f.cfgPath, Insecure: f.insecure, JSON: f.asJSON,
		})
	}
}

// app builds the App, opening the credential store with the selected backend.
func (d Deps) app(backend string) (*App, error) {
	open := d.OpenStore
	if open == nil {
		open = creds.Open
	}
	store, err := open(d.Env, backend)
	if err != nil {
		// The only failure here is an unrecognised --backend value.
		return nil, fail(ExitUsage, "usage", err)
	}
	return &App{
		Env:          d.Env,
		Store:        store,
		Stdin:        d.Stdin,
		Stdout:       d.Stdout,
		Stderr:       d.Stderr,
		Dial:         d.Dial,
		PromptSecret: d.PromptSecret,
	}, nil
}
