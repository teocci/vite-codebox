package command

import (
	"bytes"
	"context"
	"strings"
	"testing"

	"github.com/teocci/vite-codebox/clients/codeblox/internal/config"
	"github.com/teocci/vite-codebox/clients/codeblox/internal/creds"
)

func deps(t *testing.T, stdin string) (Deps, *bytes.Buffer) {
	t.Helper()
	out := &bytes.Buffer{}
	return Deps{
		Env: config.Env{
			Home:   t.TempDir(),
			Cwd:    t.TempDir(),
			Getenv: func(string) string { return "" },
		},
		Stdin:  strings.NewReader(stdin),
		Stdout: out,
		Stderr: &bytes.Buffer{},
	}, out
}

func TestDispatchRejectsAnUnknownCommand(t *testing.T) {
	d, _ := deps(t, "")
	err := Dispatch(context.Background(), d, []string{"teleport"})
	if err == nil {
		t.Fatal("Dispatch accepted an unknown command, want an error")
	}
	if !strings.Contains(err.Error(), "teleport") {
		t.Fatalf("error %q does not name the unknown command", err)
	}
}

func TestDispatchWithNoArgumentsPrintsUsage(t *testing.T) {
	d, out := deps(t, "")
	if err := Dispatch(context.Background(), d, nil); err != nil {
		t.Fatalf("Dispatch with no args = %v, want nil", err)
	}
	if !strings.Contains(out.String(), "auth") {
		t.Fatalf("usage output %q does not list the auth command", out.String())
	}
}

func TestDispatchRejectsAuthWithoutASubcommand(t *testing.T) {
	d, _ := deps(t, "")
	if err := Dispatch(context.Background(), d, []string{"auth"}); err == nil {
		t.Fatal("Dispatch accepted bare `auth`, want an error")
	}
}

func TestDispatchRoutesAuthLoginAndHonoursTheBackendFlag(t *testing.T) {
	d, out := deps(t, "tok-abcdefghijkl\n")
	err := Dispatch(context.Background(), d,
		[]string{"auth", "login", "--with-token", "--backend", "file"})
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(out.String(), "file") {
		t.Fatalf("output %q does not mention the file backend", out.String())
	}

	store, err := creds.Open(d.Env, "file")
	if err != nil {
		t.Fatal(err)
	}
	got, err := store.Get()
	if err != nil {
		t.Fatal(err)
	}
	if got != "tok-abcdefghijkl" {
		t.Fatalf("stored token = %q, want the piped value", got)
	}
}

func TestDispatchRoutesAuthListAsJSON(t *testing.T) {
	d, out := deps(t, "")
	err := Dispatch(context.Background(), d,
		[]string{"auth", "list", "--backend", "file", "--json"})
	if err != nil {
		t.Fatal(err)
	}
	if !strings.HasPrefix(strings.TrimSpace(out.String()), "{") {
		t.Fatalf("auth list --json emitted %q, want a JSON object", out.String())
	}
}

func TestDispatchVersionPrintsTheVersion(t *testing.T) {
	d, out := deps(t, "")
	if err := Dispatch(context.Background(), d, []string{"version"}); err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(out.String(), Version) {
		t.Fatalf("version output %q does not contain %q", out.String(), Version)
	}
}

func TestDispatchRejectsAnUnknownAuthSubcommand(t *testing.T) {
	d, _ := deps(t, "")
	if err := Dispatch(context.Background(), d, []string{"auth", "renew"}); err == nil {
		t.Fatal("Dispatch accepted an unknown auth subcommand, want an error")
	}
}
