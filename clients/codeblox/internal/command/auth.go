// Package command implements the codeblox CLI verbs.
//
// App holds the injected dependencies (host environment, credential store, I/O
// streams, dialer) so every verb is testable without touching the real keyring,
// the real home directory, or the network.
package command

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"strings"

	"golang.org/x/term"

	"github.com/teocci/vite-codebox/clients/codeblox/internal/config"
	"github.com/teocci/vite-codebox/clients/codeblox/internal/creds"
	"github.com/teocci/vite-codebox/clients/codeblox/internal/transport"
)

// Session is a live, authenticated connection to a codeblox server. It exists so
// the verbs can be tested against a fake without a socket; *transport.Conn is the
// production implementation.
type Session interface {
	// Contract is the server's published world_info, raw.
	Contract() json.RawMessage
	// SendBatch submits a command batch and returns the server's ack.
	SendBatch(context.Context, []any) (transport.Ack, error)
	Close() error
}

// App is the CLI's injected context.
type App struct {
	Env    config.Env
	Store  creds.Backend
	Stdin  io.Reader
	Stdout io.Writer
	Stderr io.Writer

	// Dial opens a connection. Injected so tests need no server; nil means use
	// the real dialer.
	Dial func(context.Context, transport.Dialer) (Session, error)
	// PromptSecret reads a secret without echoing. nil means use the terminal.
	PromptSecret func(prompt string) (string, error)
}

// LoginOptions configures `codeblox auth login`.
type LoginOptions struct {
	// FromStdin reads the token from stdin instead of prompting (--with-token).
	FromStdin bool
	// Endpoint, when set, is validated and saved to the settings file.
	Endpoint   string
	ConfigPath string
}

// StatusOptions configures `codeblox auth status`.
type StatusOptions struct {
	Endpoint   string
	ConfigPath string
	Insecure   bool
	JSON       bool
}

// Login obtains a token, stores it, and optionally records the endpoint. The
// token is never echoed and never written to the settings file.
func (a *App) Login(opts LoginOptions) error {
	token, err := a.readToken(opts.FromStdin)
	if err != nil {
		return err
	}
	if token == "" {
		return errors.New("empty token — nothing was stored")
	}

	if opts.Endpoint != "" {
		if err := a.saveEndpoint(opts); err != nil {
			return err
		}
	}
	if err := a.Store.Set(token); err != nil {
		return err
	}

	endpoint, err := a.Env.Endpoint(opts.Endpoint, opts.ConfigPath)
	if err != nil {
		return err
	}
	fmt.Fprintf(a.Stdout, "stored %s in the %s backend for %s\n",
		creds.Mask(token), a.Store.Name(), endpoint)
	fmt.Fprintf(a.Stdout, "run `codeblox auth status` to check it against the server\n")
	return nil
}

// Logout removes the stored credential. Having nothing to remove is reported,
// not treated as a failure — the end state the user asked for already holds.
func (a *App) Logout() error {
	err := a.Store.Delete()
	if errors.Is(err, creds.ErrNoCredential) {
		fmt.Fprintf(a.Stdout, "no stored credential in the %s backend — nothing to remove\n", a.Store.Name())
		return nil
	}
	if err != nil {
		return err
	}
	fmt.Fprintf(a.Stdout, "removed the credential from the %s backend\n", a.Store.Name())
	return nil
}

// listReport is the machine-readable shape of `auth list`.
type listReport struct {
	Backend  string `json:"backend"`
	Source   string `json:"source"`
	Token    string `json:"token"`
	Endpoint string `json:"endpoint"`
}

// List shows the stored credential, always masked.
func (a *App) List(asJSON bool) error {
	endpoint, err := a.Env.Endpoint("", "")
	if err != nil {
		return err
	}

	token, source, err := creds.Resolve(a.Store, a.Env)
	if errors.Is(err, creds.ErrNoCredential) {
		report := listReport{Backend: a.Store.Name(), Source: "none",
			Token: creds.Mask(""), Endpoint: endpoint}
		if asJSON {
			return a.emitJSON(report)
		}
		fmt.Fprintf(a.Stdout, "no stored credential — run `codeblox auth login`\n")
		fmt.Fprintf(a.Stdout, "backend: %s   endpoint: %s\n", report.Backend, endpoint)
		return nil
	}
	if err != nil {
		return err
	}

	report := listReport{Backend: a.Store.Name(), Source: source,
		Token: creds.Mask(token), Endpoint: endpoint}
	if asJSON {
		return a.emitJSON(report)
	}
	fmt.Fprintf(a.Stdout, "token: %s   source: %s   backend: %s\n",
		report.Token, report.Source, report.Backend)
	fmt.Fprintf(a.Stdout, "endpoint: %s\n", endpoint)
	return nil
}

// statusReport is the machine-readable shape of `auth status`.
type statusReport struct {
	Connected bool   `json:"connected"`
	Endpoint  string `json:"endpoint"`
	Backend   string `json:"backend"`
	Source    string `json:"source"`
	Token     string `json:"token"`
	Contract  bool   `json:"contract"`
}

// Status runs the live check: resolve the credential, connect, and report what
// the server did with it.
func (a *App) Status(ctx context.Context, opts StatusOptions) error {
	conn, err := a.connect(ctx, dialOptions{
		Endpoint: opts.Endpoint, ConfigPath: opts.ConfigPath, Insecure: opts.Insecure,
	})
	if err != nil {
		return err
	}
	defer conn.session.Close()

	report := statusReport{
		Connected: true,
		Endpoint:  conn.endpoint,
		Backend:   a.Store.Name(),
		Source:    conn.source,
		Token:     creds.Mask(conn.token),
		Contract:  len(conn.session.Contract()) > 0,
	}
	if opts.JSON {
		return a.emitJSON(report)
	}
	fmt.Fprintf(a.Stdout, "connected to %s\n", conn.endpoint)
	fmt.Fprintf(a.Stdout, "token: %s   source: %s   backend: %s\n",
		report.Token, report.Source, report.Backend)
	if report.Contract {
		fmt.Fprintf(a.Stdout, "server returned its world_info contract\n")
	}
	// A server started with auth.required=false accepts any token, so a
	// successful connection is not proof the credential is correct.
	fmt.Fprintf(a.Stdout, "note: a server running with auth disabled accepts any token\n")
	return nil
}

// readToken gets the secret from stdin or a no-echo prompt.
func (a *App) readToken(fromStdin bool) (string, error) {
	if fromStdin {
		raw, err := io.ReadAll(a.Stdin)
		if err != nil {
			return "", fmt.Errorf("read token from stdin: %w", err)
		}
		return strings.TrimSpace(string(raw)), nil
	}
	prompt := a.PromptSecret
	if prompt == nil {
		prompt = promptSecret
	}
	token, err := prompt("Token: ")
	if err != nil {
		return "", err
	}
	return strings.TrimSpace(token), nil
}

// promptSecret reads from the terminal with echo off.
func promptSecret(prompt string) (string, error) {
	fd := int(os.Stdin.Fd())
	if !term.IsTerminal(fd) {
		return "", errors.New("no terminal available — pipe the token in with `auth login --with-token`")
	}
	fmt.Fprint(os.Stderr, prompt)
	raw, err := term.ReadPassword(fd)
	fmt.Fprintln(os.Stderr)
	if err != nil {
		return "", fmt.Errorf("read token: %w", err)
	}
	return string(raw), nil
}

// saveEndpoint validates and persists a non-secret endpoint override.
func (a *App) saveEndpoint(opts LoginOptions) error {
	if err := config.ValidateEndpoint(opts.Endpoint); err != nil {
		return err
	}
	cfg, err := a.Env.Load(opts.ConfigPath)
	if err != nil {
		return err
	}
	cfg.Endpoint = opts.Endpoint
	return cfg.Save(a.Env.ConfigPath(opts.ConfigPath))
}

func (a *App) dial(ctx context.Context, d transport.Dialer) (Session, error) {
	if a.Dial != nil {
		return a.Dial(ctx, d)
	}
	return d.Connect(ctx)
}

func (a *App) emitJSON(v any) error {
	raw, err := json.Marshal(v)
	if err != nil {
		return fmt.Errorf("encode report: %w", err)
	}
	_, err = fmt.Fprintln(a.Stdout, string(raw))
	return err
}
