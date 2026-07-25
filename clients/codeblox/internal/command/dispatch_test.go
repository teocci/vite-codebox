package command

import (
	"bytes"
	"context"
	"strings"
	"testing"

	"github.com/teocci/vite-codebox/clients/codeblox/internal/config"
	"github.com/teocci/vite-codebox/clients/codeblox/internal/creds"
)

// deps builds an isolated Deps plus its stdout and stderr buffers. Both streams
// are returned because which one carries a message is part of the CLI's
// contract, not an implementation detail: results go to stdout, failures to
// stderr, and a caller parsing stdout must never find an error there.
func deps(t *testing.T, stdin string) (Deps, *bytes.Buffer, *bytes.Buffer) {
	t.Helper()
	out, errOut := &bytes.Buffer{}, &bytes.Buffer{}
	return Deps{
		Env: config.Env{
			Home:   t.TempDir(),
			Cwd:    t.TempDir(),
			Getenv: func(string) string { return "" },
		},
		Stdin:  strings.NewReader(stdin),
		Stdout: out,
		Stderr: errOut,
	}, out, errOut
}

func TestDispatchRejectsAnUnknownCommand(t *testing.T) {
	d, _, _ := deps(t, "")
	err := Dispatch(context.Background(), d, []string{"teleport"})
	if err == nil {
		t.Fatal("Dispatch accepted an unknown command, want an error")
	}
	if !strings.Contains(err.Error(), "teleport") {
		t.Fatalf("error %q does not name the unknown command", err)
	}
}

func TestDispatchWithNoArgumentsFailsWithUsageOnStderr(t *testing.T) {
	// A wrapper that computes an empty argv must not read success. Usage goes to
	// stderr and the exit code is ExitUsage, so an empty invocation is
	// indistinguishable from any other argv error to the caller.
	d, out, errOut := deps(t, "")

	err := Dispatch(context.Background(), d, nil)
	if err == nil {
		t.Fatal("Dispatch with no args succeeded, want a usage failure")
	}
	if got := ExitCodeFor(err); got != ExitUsage {
		t.Errorf("exit code %d, want %d", got, ExitUsage)
	}
	if !strings.Contains(errOut.String(), "auth") {
		t.Errorf("usage went to stderr as %q, which does not list the auth command", errOut.String())
	}
	if strings.TrimSpace(out.String()) != "" {
		t.Errorf("wrote %q to stdout; a caller parsing stdout would read it as a result", out.String())
	}
}

func TestDispatchHelpStillSucceedsOnStdout(t *testing.T) {
	// `help` is a request, not a mistake: it succeeds, and its output is the
	// result, so it belongs on stdout.
	d, out, _ := deps(t, "")
	if err := Dispatch(context.Background(), d, []string{"help"}); err != nil {
		t.Fatalf("help = %v, want nil", err)
	}
	if !strings.Contains(out.String(), "auth") {
		t.Errorf("help output %q does not list the auth command", out.String())
	}
}

func TestDispatchRejectsAuthWithoutASubcommand(t *testing.T) {
	d, _, _ := deps(t, "")
	if err := Dispatch(context.Background(), d, []string{"auth"}); err == nil {
		t.Fatal("Dispatch accepted bare `auth`, want an error")
	}
}

func TestDispatchRoutesAuthLoginAndHonoursTheBackendFlag(t *testing.T) {
	d, out, _ := deps(t, "tok-abcdefghijkl\n")
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
	d, out, _ := deps(t, "")
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
	d, out, _ := deps(t, "")
	if err := Dispatch(context.Background(), d, []string{"version"}); err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(out.String(), Version) {
		t.Fatalf("version output %q does not contain %q", out.String(), Version)
	}
}

func TestDispatchRejectsAnUnknownAuthSubcommand(t *testing.T) {
	d, _, _ := deps(t, "")
	if err := Dispatch(context.Background(), d, []string{"auth", "renew"}); err == nil {
		t.Fatal("Dispatch accepted an unknown auth subcommand, want an error")
	}
}
