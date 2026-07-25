package command

import (
	"context"
	"flag"
	"fmt"
	"io"

	"github.com/teocci/vite-codebox/clients/codeblox/internal/config"
	"github.com/teocci/vite-codebox/clients/codeblox/internal/creds"
	"github.com/teocci/vite-codebox/clients/codeblox/internal/transport"
)

// Version is the CLI's own version, independent of the server's.
const Version = "0.3.0"

const usage = `codeblox — command a codeblox build server

usage:
  codeblox auth login  [--with-token] [--endpoint URL] [--backend keyring|file] [--config PATH]
  codeblox auth logout [--backend keyring|file]
  codeblox auth list   [--backend keyring|file] [--json]
  codeblox auth status [--endpoint URL] [--backend keyring|file] [--insecure] [--json]
  codeblox version

credentials:
  The token is kept in the OS keyring by default, or a 0600 file store when no
  keyring is available. It is never written to the settings file and is always
  masked in output. ` + config.EnvToken + ` is a fallback for automation.

settings:
  Non-secret settings live in ~/` + config.DirName + `/` + config.FileName + `.
  The endpoint resolves as: --endpoint, then ` + config.EnvEndpoint + `,
  then the settings file, then ` + config.DefaultEndpoint + `.
`

// Deps is everything Dispatch needs from the host. Injected so the whole CLI is
// exercisable in tests without a keyring, a home directory, or a network.
type Deps struct {
	Env    config.Env
	Stdin  io.Reader
	Stdout io.Writer
	Stderr io.Writer

	// Dial and OpenStore default to the real implementations when nil.
	Dial      func(context.Context, transport.Dialer) (*transport.Conn, error)
	OpenStore func(config.Env, string) (creds.Backend, error)
}

// Dispatch parses args and runs the requested verb.
func Dispatch(ctx context.Context, d Deps, args []string) error {
	if len(args) == 0 {
		fmt.Fprint(d.Stdout, usage)
		return nil
	}

	switch args[0] {
	case "auth":
		return dispatchAuth(ctx, d, args[1:])
	case "version":
		fmt.Fprintf(d.Stdout, "codeblox %s\n", Version)
		return nil
	case "help", "-h", "--help":
		fmt.Fprint(d.Stdout, usage)
		return nil
	default:
		return fmt.Errorf("unknown command %q — run `codeblox help`", args[0])
	}
}

// dispatchAuth routes the credential lifecycle verbs.
func dispatchAuth(ctx context.Context, d Deps, args []string) error {
	if len(args) == 0 {
		return fmt.Errorf("`auth` needs a subcommand: login, logout, list, or status")
	}

	sub := args[0]
	fs := flag.NewFlagSet("auth "+sub, flag.ContinueOnError)
	fs.SetOutput(d.Stderr)
	backend := fs.String("backend", "", "credential backend: keyring or file")
	cfgPath := fs.String("config", "", "path to the settings file")
	endpoint := fs.String("endpoint", "", "server endpoint (ws:// or wss://)")
	withToken := fs.Bool("with-token", false, "read the token from stdin instead of prompting")
	insecure := fs.Bool("insecure", false, "allow sending the token over plain ws:// to a remote host")
	asJSON := fs.Bool("json", false, "emit a compact JSON report")

	if err := fs.Parse(args[1:]); err != nil {
		return err
	}

	app, err := d.app(*backend)
	if err != nil {
		return err
	}

	switch sub {
	case "login":
		return app.Login(LoginOptions{
			FromStdin: *withToken, Endpoint: *endpoint, ConfigPath: *cfgPath,
		})
	case "logout":
		return app.Logout()
	case "list":
		return app.List(*asJSON)
	case "status":
		return app.Status(ctx, StatusOptions{
			Endpoint: *endpoint, ConfigPath: *cfgPath, Insecure: *insecure, JSON: *asJSON,
		})
	default:
		return fmt.Errorf("unknown auth subcommand %q: want login, logout, list, or status", sub)
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
		return nil, err
	}
	return &App{
		Env:    d.Env,
		Store:  store,
		Stdin:  d.Stdin,
		Stdout: d.Stdout,
		Stderr: d.Stderr,
		Dial:   d.Dial,
	}, nil
}
