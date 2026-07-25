// Package creds stores the codeblox bearer token.
//
// The OS keyring is the default backend; a 0600 file store under the base dir is
// the fallback for headless hosts with no keyring daemon. The token is never
// written to the settings file, never logged, and only ever printed through Mask.
package creds

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/zalando/go-keyring"

	"github.com/teocci/vite-codebox/clients/codeblox/internal/config"
)

// ErrNoCredential means no token is stored — the caller should tell the user to
// run `codeblox auth login`, not treat it as a hard failure.
var ErrNoCredential = errors.New("no stored credential")

// service and account name the entry in the OS keyring.
const (
	service = "codeblox"
	account = "default"

	// maskEdge is how many leading/trailing characters Mask keeps.
	maskEdge = 4
	// maskMinLen is the shortest token that keeps any visible characters; below
	// this, showing edges would leak most of a short secret.
	maskMinLen = 12
)

// Backend is a place a single bearer token can live. Two implementations exist
// (keyring and file), which is what earns the interface.
type Backend interface {
	Get() (string, error)
	Set(token string) error
	Delete() error
	// Name is the backend's identifier, shown by `auth list` / `auth status`.
	Name() string
}

// Mask renders a token safe to print. Short tokens lose their edges entirely.
func Mask(token string) string {
	if token == "" {
		return "(none)"
	}
	if len(token) < maskMinLen {
		return strings.Repeat("*", len(token))
	}
	return token[:maskEdge] + "…" + token[len(token)-maskEdge:]
}

// Open selects a backend: an explicit flag, then $CODEBLOX_AUTH_BACKEND, then
// the keyring, falling back to the file store when no keyring is available.
func Open(e config.Env, flagBackend string) (Backend, error) {
	choice := flagBackend
	if choice == "" && e.Getenv != nil {
		choice = e.Getenv(config.EnvBackend)
	}
	switch choice {
	case "file":
		return newFileBackend(e.AuthPath()), nil
	case "keyring":
		return newKeyringBackend(), nil
	case "":
		if keyringAvailable() {
			return newKeyringBackend(), nil
		}
		return newFileBackend(e.AuthPath()), nil
	default:
		return nil, fmt.Errorf("unknown auth backend %q: want %q or %q", choice, "keyring", "file")
	}
}

// Resolve returns the active token and where it came from. The stored credential
// wins; the environment variable is only a fallback for CI and automation.
func Resolve(b Backend, e config.Env) (token, source string, err error) {
	tok, err := b.Get()
	if err == nil {
		return tok, b.Name(), nil
	}
	if !errors.Is(err, ErrNoCredential) {
		return "", "", err
	}
	if e.Getenv != nil {
		if v := e.Getenv(config.EnvToken); v != "" {
			return v, config.EnvToken, nil
		}
	}
	return "", "", ErrNoCredential
}

// ── keyring backend ─────────────────────────────────────────────────────────

type keyringBackend struct{}

func newKeyringBackend() Backend { return keyringBackend{} }

func (keyringBackend) Name() string { return "keyring" }

func (keyringBackend) Get() (string, error) {
	tok, err := keyring.Get(service, account)
	if errors.Is(err, keyring.ErrNotFound) {
		return "", ErrNoCredential
	}
	if err != nil {
		return "", fmt.Errorf("read from keyring: %w", err)
	}
	return tok, nil
}

func (keyringBackend) Set(token string) error {
	if err := keyring.Set(service, account, token); err != nil {
		return fmt.Errorf("write to keyring: %w", err)
	}
	return nil
}

func (keyringBackend) Delete() error {
	err := keyring.Delete(service, account)
	if errors.Is(err, keyring.ErrNotFound) {
		return ErrNoCredential
	}
	if err != nil {
		return fmt.Errorf("delete from keyring: %w", err)
	}
	return nil
}

// keyringAvailable probes the OS keyring with a read that is expected to miss.
// ErrNotFound proves the daemon answered; any other error means no keyring.
func keyringAvailable() bool {
	_, err := keyring.Get(service, account)
	return err == nil || errors.Is(err, keyring.ErrNotFound)
}

// ── file backend ────────────────────────────────────────────────────────────

// authFile is the on-disk shape of the file backend. It holds the secret inline,
// which is why it is written 0600 and lives outside any committed tree.
type authFile struct {
	Token string `json:"token"`
}

type fileBackend struct{ path string }

func newFileBackend(path string) Backend { return fileBackend{path: path} }

func (fileBackend) Name() string { return "file" }

func (f fileBackend) Get() (string, error) {
	raw, err := os.ReadFile(f.path)
	if errors.Is(err, os.ErrNotExist) {
		return "", ErrNoCredential
	}
	if err != nil {
		return "", fmt.Errorf("read auth store: %w", err)
	}
	var stored authFile
	if err := json.Unmarshal(raw, &stored); err != nil {
		return "", fmt.Errorf("parse auth store %s: %w", f.path, err)
	}
	if stored.Token == "" {
		return "", ErrNoCredential
	}
	return stored.Token, nil
}

func (f fileBackend) Set(token string) error {
	if err := os.MkdirAll(filepath.Dir(f.path), 0o700); err != nil {
		return fmt.Errorf("create auth dir: %w", err)
	}
	raw, err := json.Marshal(authFile{Token: token})
	if err != nil {
		return fmt.Errorf("encode auth store: %w", err)
	}
	if err := os.WriteFile(f.path, append(raw, '\n'), 0o600); err != nil {
		return fmt.Errorf("write auth store: %w", err)
	}
	return nil
}

func (f fileBackend) Delete() error {
	err := os.Remove(f.path)
	if errors.Is(err, os.ErrNotExist) {
		return ErrNoCredential
	}
	if err != nil {
		return fmt.Errorf("delete auth store: %w", err)
	}
	return nil
}
