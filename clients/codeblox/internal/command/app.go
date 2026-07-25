// Package command implements the codeblox CLI verbs.
//
// The package has two domains and a type for each: authApp owns the credential
// lifecycle (auth.go), buildApp owns world building (build.go). Both embed
// base, the injected substrate — host environment, credential store, streams,
// dialer — so every verb is testable without touching the real keyring, the
// real home directory, or the network.
//
// The split is what keeps a build verb from reaching a credential prompt and an
// auth verb from reaching a command batch. The two halves lived in separate
// files long before they were separate types, but the compiler does not read
// filenames; only the type boundary actually enforces it.
package command

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"

	"github.com/teocci/vite-codebox/clients/codeblox/internal/config"
	"github.com/teocci/vite-codebox/clients/codeblox/internal/contract"
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

// base is the substrate both domains share. Every field is injected: nothing
// here reads the ambient process environment, so a test supplies all of it.
//
// Both halves genuinely use all of it — Stdin carries the token for `auth
// login` and the batch for `exec`, and the credential store is what `connect`
// resolves a token from. What the split narrows is the method set, not the data.
type base struct {
	Env    config.Env
	Store  creds.Backend
	Stdin  io.Reader
	Stdout io.Writer

	// Dial opens a connection. Injected so tests need no server; nil means use
	// the real dialer.
	Dial func(context.Context, transport.Dialer) (Session, error)
}

// dialOptions is the connection-shaped subset every verb shares.
type dialOptions struct {
	Endpoint   string
	ConfigPath string
	Insecure   bool
}

// connection is a dialed session plus how it was reached. `auth status` reports
// these facts; the build verbs only need the session.
type connection struct {
	session  Session
	endpoint string
	token    string
	source   string
}

// connect resolves the endpoint and credential, refuses an unsafe transport,
// and dials — classifying every failure on the way.
//
// Both the build verbs and `auth status` go through here, which is why it lives
// on base rather than in either domain's file. They used to repeat these four
// steps, which is how `auth status` ended up returning an unclassified exit 1
// for failures the build path already reported as auth or network. Giving each
// half its own copy would reopen that.
func (b *base) connect(ctx context.Context, opts dialOptions) (connection, error) {
	endpoint, err := b.Env.Endpoint(opts.Endpoint, opts.ConfigPath)
	if err != nil {
		// A malformed endpoint came from a flag, an env var, or the settings
		// file — the caller supplied it either way.
		return connection{}, fail(ExitUsage, "usage", err)
	}

	token, source, err := creds.Resolve(b.Store, b.Env)
	if errors.Is(err, creds.ErrNoCredential) {
		return connection{}, fail(ExitAuth, "not_authenticated",
			errors.New("not authenticated — run `codeblox auth login`"))
	}
	if err != nil {
		return connection{}, fail(ExitAuth, "credential_unreadable", err)
	}

	// The guard runs before the dial so a rejected endpoint never puts the
	// token on the wire.
	if err := transport.CheckTransportSecurity(endpoint, opts.Insecure); err != nil {
		return connection{}, fail(ExitNetwork, "insecure_transport", err)
	}

	session, err := b.dial(ctx, transport.Dialer{
		Endpoint: endpoint, Token: token, Insecure: opts.Insecure,
	})
	if err != nil {
		if errors.Is(err, transport.ErrUnauthorized) {
			return connection{}, fail(ExitAuth, "unauthorized", err)
		}
		return connection{}, fail(ExitNetwork, "unreachable", err)
	}
	return connection{session: session, endpoint: endpoint, token: token, source: source}, nil
}

// session authenticates, connects, and returns the live session plus the freshly
// published contract, which it also caches.
func (b *base) session(ctx context.Context, opts dialOptions) (Session, contract.Contract, error) {
	conn, err := b.connect(ctx, opts)
	if err != nil {
		return nil, contract.Contract{}, err
	}
	session := conn.session

	var spec contract.Contract
	if err := json.Unmarshal(session.Contract(), &spec); err != nil {
		session.Close()
		return nil, contract.Contract{}, fmt.Errorf("parse server contract: %w", err)
	}
	// Best-effort: a read-only home must not fail an otherwise good command.
	_ = spec.Save(b.Env.ContractPath())
	return session, spec, nil
}

func (b *base) dial(ctx context.Context, d transport.Dialer) (Session, error) {
	if b.Dial != nil {
		return b.Dial(ctx, d)
	}
	return d.Connect(ctx)
}

func (b *base) emitJSON(v any) error {
	raw, err := json.Marshal(v)
	if err != nil {
		return fmt.Errorf("encode report: %w", err)
	}
	_, err = fmt.Fprintln(b.Stdout, string(raw))
	return err
}
