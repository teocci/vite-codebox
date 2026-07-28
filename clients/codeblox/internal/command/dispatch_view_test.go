package command

import (
	"bytes"
	"context"
	"encoding/json"
	"strings"
	"testing"

	"github.com/teocci/vite-codebox/clients/codeblox/internal/config"
	"github.com/teocci/vite-codebox/clients/codeblox/internal/creds"
	"github.com/teocci/vite-codebox/clients/codeblox/internal/transport"
)

// viewContractJSON is the build contract plus the viewer ops, so these tests
// validate against the same published shapes the server sends.
const viewContractJSON = `{
  "config": {"blockSize":0.02,"blockLabel":"2 cm","extent":32,"gridStep":1,
             "boundBlocks":1600,"heightBlocks":3200},
  "palette": {"granite": {"color":14210508,"family":"opaque"}},
  "ops": [
    {"op":"box","fields":{"at":"int3","size":"int3+","mat":"material"}},
    {"op":"clear","fields":{}},
    {"op":"view","fields":{"n":"int+"}},
    {"op":"reframe","fields":{}},
    {"op":"rotate","fields":{"on":"bool"}},
    {"op":"grid","fields":{"on":"bool"}},
    {"op":"hud","fields":{"on":"bool"}}
  ]
}`

type viewSession struct {
	sent []any
}

func (s *viewSession) Contract() json.RawMessage { return json.RawMessage(viewContractJSON) }
func (s *viewSession) Close() error              { return nil }
func (s *viewSession) SendBatch(_ context.Context, batch []any) (transport.Ack, error) {
	s.sent = append(s.sent, batch...)
	return transport.Ack{}, nil
}

// viewDeps wires a full Deps around a fake session, so these exercise the real
// Dispatch path rather than the internals.
func viewDeps(t *testing.T) (Deps, *bytes.Buffer, *viewSession) {
	t.Helper()
	e := config.Env{Home: t.TempDir(), Cwd: t.TempDir(), Getenv: func(string) string { return "" }}
	store, err := creds.Open(e, "file")
	if err != nil {
		t.Fatal(err)
	}
	if err := store.Set("tok-for-view-tests"); err != nil {
		t.Fatal(err)
	}
	session := &viewSession{}
	out := &bytes.Buffer{}
	return Deps{
		Env:    e,
		Stdin:  strings.NewReader(""),
		Stdout: out,
		Stderr: &bytes.Buffer{},
		Dial: func(context.Context, transport.Dialer) (Session, error) {
			return session, nil
		},
		OpenStore: func(config.Env, string) (creds.Backend, error) { return store, nil },
	}, out, session
}

func run(t *testing.T, args ...string) (*viewSession, error) {
	t.Helper()
	d, _, session := viewDeps(t)
	return session, Dispatch(context.Background(), d, args)
}

// sole returns the one command the session was sent, failing otherwise.
func sole(t *testing.T, s *viewSession) map[string]any {
	t.Helper()
	if len(s.sent) != 1 {
		t.Fatalf("sent %d command(s), want exactly 1: %v", len(s.sent), s.sent)
	}
	cmd, ok := s.sent[0].(map[string]any)
	if !ok {
		t.Fatalf("sent %T, want a command object", s.sent[0])
	}
	return cmd
}

func TestViewSendsAPresetFromANumericArgument(t *testing.T) {
	session, err := run(t, "view", "4")
	if err != nil {
		t.Fatal(err)
	}
	cmd := sole(t, session)
	if cmd["op"] != "view" || cmd["n"] != float64(4) {
		t.Fatalf("sent %v, want {op:view n:4}", cmd)
	}
}

func TestViewSendsReframe(t *testing.T) {
	session, err := run(t, "view", "reframe")
	if err != nil {
		t.Fatal(err)
	}
	if cmd := sole(t, session); cmd["op"] != "reframe" {
		t.Fatalf("sent %v, want {op:reframe}", cmd)
	}
}

func TestViewSendsEachFlagOpAsARealBoolean(t *testing.T) {
	// The wire value must be a JSON boolean, not the string "on": the server's
	// schema publishes `on` as bool and would reject anything else.
	for _, tt := range []struct {
		sub   string
		arg   string
		wantY bool
	}{
		{"rotate", "on", true},
		{"rotate", "off", false},
		{"grid", "on", true},
		{"grid", "off", false},
		{"hud", "on", true},
		{"hud", "off", false},
	} {
		t.Run(tt.sub+" "+tt.arg, func(t *testing.T) {
			session, err := run(t, "view", tt.sub, tt.arg)
			if err != nil {
				t.Fatal(err)
			}
			cmd := sole(t, session)
			if cmd["op"] != tt.sub {
				t.Fatalf("op = %v, want %s", cmd["op"], tt.sub)
			}
			on, ok := cmd["on"].(bool)
			if !ok {
				t.Fatalf("on = %T(%v), want a bool", cmd["on"], cmd["on"])
			}
			if on != tt.wantY {
				t.Fatalf("on = %v, want %v", on, tt.wantY)
			}
		})
	}
}

func TestViewRejectsAnUnknownSubcommand(t *testing.T) {
	session, err := run(t, "view", "zoom")
	if err == nil {
		t.Fatal("view zoom succeeded, want a usage failure")
	}
	if got := ExitCodeFor(err); got != ExitUsage {
		t.Errorf("exit code %d, want %d", got, ExitUsage)
	}
	if !strings.Contains(err.Error(), "zoom") || !strings.Contains(err.Error(), "reframe") {
		t.Errorf("error %q should name the bad token and the valid set", err)
	}
	if len(session.sent) != 0 {
		t.Errorf("sent %v; nothing may reach the wire after a usage failure", session.sent)
	}
}

func TestViewRejectsAFlagOpWithoutOnOrOff(t *testing.T) {
	if _, err := run(t, "view", "rotate"); err == nil {
		t.Fatal("view rotate with no argument succeeded, want a usage failure")
	}
	_, err := run(t, "view", "grid", "yes")
	if err == nil {
		t.Fatal("view grid yes succeeded, want a usage failure")
	}
	if !strings.Contains(err.Error(), "on or off") {
		t.Errorf("error %q does not name the valid set", err)
	}
}

func TestViewRejectsBareView(t *testing.T) {
	if _, err := run(t, "view"); err == nil {
		t.Fatal("bare `view` succeeded, want a usage failure")
	}
}

func TestViewRejectsAStrayArgumentAfterTheSubcommand(t *testing.T) {
	// I-1's rule: a token the verb cannot act on is an error, never a silent
	// discard. `view 4 5` must not quietly send view 4.
	session, err := run(t, "view", "4", "5")
	if err == nil {
		t.Fatal("view 4 5 succeeded, want a usage failure")
	}
	if len(session.sent) != 0 {
		t.Errorf("sent %v, want nothing", session.sent)
	}
}

func TestViewHonoursDryRunAndSendsNothing(t *testing.T) {
	d, out, session := viewDeps(t)
	if err := Dispatch(context.Background(), d, []string{"view", "2", "--dry-run"}); err != nil {
		t.Fatal(err)
	}
	if len(session.sent) != 0 {
		t.Errorf("sent %v with --dry-run, want nothing", session.sent)
	}
	if !strings.Contains(out.String(), "nothing sent") {
		t.Errorf("output %q does not report that nothing was sent", out.String())
	}
}

func TestViewHonoursJSON(t *testing.T) {
	d, out, _ := viewDeps(t)
	if err := Dispatch(context.Background(), d, []string{"view", "reframe", "--json"}); err != nil {
		t.Fatal(err)
	}
	var report map[string]any
	if err := json.Unmarshal(out.Bytes(), &report); err != nil {
		t.Fatalf("output %q is not JSON: %v", out.String(), err)
	}
	if report["ok"] != true {
		t.Errorf("report = %v, want ok:true", report)
	}
}

func TestViewDoesNotCompileInThePresetCount(t *testing.T) {
	// `n` is published as int+, so an out-of-range preset must pass client-side
	// validation and be refused by the server — the only place that knows how
	// many presets exist. Nobody should "fix" this by hardcoding the count.
	session, err := run(t, "view", "7")
	if err != nil {
		t.Fatalf("view 7 = %v, want it accepted here and left to the server", err)
	}
	if cmd := sole(t, session); cmd["n"] != float64(7) {
		t.Fatalf("sent %v, want n:7 forwarded unchanged", cmd)
	}
}

func TestViewRejectsANonPositivePresetAgainstTheContract(t *testing.T) {
	// This one the contract does describe: int+ means positive, so it fails
	// before anything is sent — exit 5, not exit 6.
	session, err := run(t, "view", "0")
	if err == nil {
		t.Fatal("view 0 succeeded, want a contract rejection")
	}
	if got := ExitCodeFor(err); got != ExitContract {
		t.Errorf("exit code %d, want %d", got, ExitContract)
	}
	if len(session.sent) != 0 {
		t.Errorf("sent %v, want nothing", session.sent)
	}
}

func TestUsageListsThePresentationGroup(t *testing.T) {
	d, out, _ := viewDeps(t)
	if err := Dispatch(context.Background(), d, []string{"help"}); err != nil {
		t.Fatal(err)
	}
	for _, want := range []string{"presentation:", "codeblox view"} {
		if !strings.Contains(out.String(), want) {
			t.Errorf("usage does not mention %q", want)
		}
	}
}
