package creds

import (
	"errors"
	"os"
	"runtime"
	"testing"

	"github.com/teocci/vite-codebox/clients/codeblox/internal/config"
)

func env(t *testing.T, vars map[string]string) config.Env {
	t.Helper()
	return config.Env{
		Home:   t.TempDir(),
		Cwd:    t.TempDir(),
		Getenv: func(k string) string { return vars[k] },
	}
}

func TestMaskKeepsOnlyTheEdges(t *testing.T) {
	got := Mask("abcdefghijklmnop")
	if got != "abcd…mnop" {
		t.Fatalf("Mask() = %q, want %q", got, "abcd…mnop")
	}
}

func TestMaskDoesNotLeakShortTokens(t *testing.T) {
	for _, tok := range []string{"a", "abcd", "abcdefg"} {
		got := Mask(tok)
		if got == tok {
			t.Fatalf("Mask(%q) returned the token verbatim", tok)
		}
	}
}

func TestMaskOfEmptyIsAPlaceholder(t *testing.T) {
	if got := Mask(""); got != "(none)" {
		t.Fatalf("Mask(\"\") = %q, want %q", got, "(none)")
	}
}

func TestFileBackendRoundTrips(t *testing.T) {
	e := env(t, nil)
	b := newFileBackend(e.AuthPath())

	if err := b.Set("s3cret-token-value"); err != nil {
		t.Fatal(err)
	}
	got, err := b.Get()
	if err != nil {
		t.Fatal(err)
	}
	if got != "s3cret-token-value" {
		t.Fatalf("Get() = %q, want the stored token", got)
	}
}

func TestFileBackendGetOnEmptyStoreReportsNotFound(t *testing.T) {
	e := env(t, nil)
	b := newFileBackend(e.AuthPath())
	if _, err := b.Get(); !errors.Is(err, ErrNoCredential) {
		t.Fatalf("Get() on an empty store returned %v, want ErrNoCredential", err)
	}
}

func TestFileBackendDeleteRemovesTheToken(t *testing.T) {
	e := env(t, nil)
	b := newFileBackend(e.AuthPath())
	if err := b.Set("tok"); err != nil {
		t.Fatal(err)
	}
	if err := b.Delete(); err != nil {
		t.Fatal(err)
	}
	if _, err := b.Get(); !errors.Is(err, ErrNoCredential) {
		t.Fatalf("Get() after Delete returned %v, want ErrNoCredential", err)
	}
}

func TestFileBackendDeleteOnEmptyStoreReportsNotFound(t *testing.T) {
	e := env(t, nil)
	b := newFileBackend(e.AuthPath())
	if err := b.Delete(); !errors.Is(err, ErrNoCredential) {
		t.Fatalf("Delete() on an empty store returned %v, want ErrNoCredential", err)
	}
}

func TestFileBackendWritesOwnerOnlyPermissions(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("unix permission bits are not meaningful on windows")
	}
	e := env(t, nil)
	b := newFileBackend(e.AuthPath())
	if err := b.Set("tok"); err != nil {
		t.Fatal(err)
	}
	info, err := os.Stat(e.AuthPath())
	if err != nil {
		t.Fatal(err)
	}
	if perm := info.Mode().Perm(); perm != 0o600 {
		t.Fatalf("auth store mode = %#o, want 0600", perm)
	}
}

func TestOpenHonoursTheFileBackendOverride(t *testing.T) {
	e := env(t, map[string]string{config.EnvBackend: "file"})
	b, err := Open(e, "")
	if err != nil {
		t.Fatal(err)
	}
	if b.Name() != "file" {
		t.Fatalf("Open() chose the %q backend, want %q", b.Name(), "file")
	}
}

func TestOpenPrefersTheFlagOverTheEnvOverride(t *testing.T) {
	e := env(t, map[string]string{config.EnvBackend: "keyring"})
	b, err := Open(e, "file")
	if err != nil {
		t.Fatal(err)
	}
	if b.Name() != "file" {
		t.Fatalf("Open() chose the %q backend, want the flag's %q", b.Name(), "file")
	}
}

func TestOpenRejectsAnUnknownBackend(t *testing.T) {
	e := env(t, nil)
	if _, err := Open(e, "vault"); err == nil {
		t.Fatal("Open() accepted an unknown backend, want an error")
	}
}

func TestResolvePrefersTheStoredCredentialOverTheEnvironment(t *testing.T) {
	e := env(t, map[string]string{config.EnvToken: "from-env"})
	b := newFileBackend(e.AuthPath())
	if err := b.Set("from-store"); err != nil {
		t.Fatal(err)
	}
	tok, src, err := Resolve(b, e)
	if err != nil {
		t.Fatal(err)
	}
	if tok != "from-store" {
		t.Fatalf("Resolve() token = %q, want the stored credential", tok)
	}
	if src != "file" {
		t.Fatalf("Resolve() source = %q, want %q", src, "file")
	}
}

func TestResolveFallsBackToTheEnvironment(t *testing.T) {
	e := env(t, map[string]string{config.EnvToken: "from-env"})
	b := newFileBackend(e.AuthPath())
	tok, src, err := Resolve(b, e)
	if err != nil {
		t.Fatal(err)
	}
	if tok != "from-env" {
		t.Fatalf("Resolve() token = %q, want the env fallback", tok)
	}
	if src != config.EnvToken {
		t.Fatalf("Resolve() source = %q, want %q", src, config.EnvToken)
	}
}

func TestResolveWithNothingStoredOrInEnvReportsNotFound(t *testing.T) {
	e := env(t, nil)
	b := newFileBackend(e.AuthPath())
	if _, _, err := Resolve(b, e); !errors.Is(err, ErrNoCredential) {
		t.Fatalf("Resolve() returned %v, want ErrNoCredential", err)
	}
}
