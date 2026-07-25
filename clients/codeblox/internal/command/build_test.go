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

const contractJSON = `{
  "config": {"blockSize":0.02,"blockLabel":"2 cm","extent":32,"gridStep":1,
             "boundBlocks":1600,"heightBlocks":3200},
  "palette": {
    "granite": {"color":14210508,"family":"opaque"},
    "glass":   {"color":14346478,"family":"glass"},
    "gold":    {"color":15253076,"family":"metal"}
  },
  "ops": [
    {"op":"box","fields":{"at":"int3","size":"int3+","mat":"material"}},
    {"op":"sphere","fields":{"at":"int3","r":"int+","mat":"material"}},
    {"op":"cylinder","fields":{"at":"int3","r":"int+","h":"int+","mat":"material"}},
    {"op":"remove","fields":{"id":"id"}},
    {"op":"clear","fields":{}}
  ]
}`

// fakeSession records what was sent and replies with a canned ack.
type fakeSession struct {
	sent []any
	ack  transport.Ack
}

func (f *fakeSession) Contract() json.RawMessage { return json.RawMessage(contractJSON) }
func (f *fakeSession) Close() error              { return nil }
func (f *fakeSession) SendBatch(_ context.Context, batch []any) (transport.Ack, error) {
	f.sent = append(f.sent, batch...)
	return f.ack, nil
}

func buildApp(t *testing.T, stdin string) (*App, *bytes.Buffer, *fakeSession) {
	t.Helper()
	e := config.Env{
		Home:   t.TempDir(),
		Cwd:    t.TempDir(),
		Getenv: func(string) string { return "" },
	}
	store, err := creds.Open(e, "file")
	if err != nil {
		t.Fatal(err)
	}
	if err := store.Set("tok-for-build-tests"); err != nil {
		t.Fatal(err)
	}
	session := &fakeSession{ack: transport.Ack{AddedIDs: []int{1}}}
	out := &bytes.Buffer{}
	return &App{
		Env:    e,
		Store:  store,
		Stdin:  strings.NewReader(stdin),
		Stdout: out,
		Stderr: &bytes.Buffer{},
		Dial: func(context.Context, transport.Dialer) (Session, error) {
			return session, nil
		},
	}, out, session
}

// ── batch parsing ───────────────────────────────────────────────────────────

func TestParseBatchReadsAJSONArray(t *testing.T) {
	got, err := ParseBatch(strings.NewReader(`[{"op":"clear"},{"op":"remove","id":3}]`))
	if err != nil {
		t.Fatal(err)
	}
	if len(got) != 2 || got[0]["op"] != "clear" || got[1]["op"] != "remove" {
		t.Fatalf("ParseBatch = %v, want the two commands in order", got)
	}
}

func TestParseBatchReadsASingleObject(t *testing.T) {
	got, err := ParseBatch(strings.NewReader(`{"op":"clear"}`))
	if err != nil {
		t.Fatal(err)
	}
	if len(got) != 1 || got[0]["op"] != "clear" {
		t.Fatalf("ParseBatch = %v, want one clear command", got)
	}
}

func TestParseBatchReadsNDJSON(t *testing.T) {
	got, err := ParseBatch(strings.NewReader("{\"op\":\"clear\"}\n{\"op\":\"remove\",\"id\":1}\n"))
	if err != nil {
		t.Fatal(err)
	}
	if len(got) != 2 {
		t.Fatalf("ParseBatch returned %d commands, want 2", len(got))
	}
}

func TestParseBatchSkipsBlankLinesInNDJSON(t *testing.T) {
	got, err := ParseBatch(strings.NewReader("{\"op\":\"clear\"}\n\n\n{\"op\":\"remove\",\"id\":1}\n"))
	if err != nil {
		t.Fatal(err)
	}
	if len(got) != 2 {
		t.Fatalf("ParseBatch returned %d commands, want 2", len(got))
	}
}

func TestParseBatchRejectsMalformedInput(t *testing.T) {
	if _, err := ParseBatch(strings.NewReader(`{"op":`)); err == nil {
		t.Fatal("ParseBatch accepted malformed JSON")
	}
}

func TestParseBatchRejectsEmptyInput(t *testing.T) {
	if _, err := ParseBatch(strings.NewReader("   \n")); err == nil {
		t.Fatal("ParseBatch accepted empty input")
	}
}

// ── exec ────────────────────────────────────────────────────────────────────

func TestExecSendsAValidBatchAndReportsTheAck(t *testing.T) {
	a, out, session := buildApp(t, `[{"op":"box","at":[0,0,0],"size":[4,4,4],"mat":"granite"}]`)

	if err := a.Exec(context.Background(), ExecOptions{JSON: true}); err != nil {
		t.Fatal(err)
	}
	if len(session.sent) != 1 {
		t.Fatalf("server received %d commands, want 1", len(session.sent))
	}
	var report map[string]any
	if err := json.Unmarshal(out.Bytes(), &report); err != nil {
		t.Fatalf("exec --json emitted %q: %v", out.String(), err)
	}
	if report["ok"] != true {
		t.Fatalf("report = %v, want ok true", report)
	}
}

func TestExecRejectsAnUnknownMaterialWithoutSendingAnything(t *testing.T) {
	a, _, session := buildApp(t, `[{"op":"box","at":[0,0,0],"size":[4,4,4],"mat":"unobtanium"}]`)

	err := a.Exec(context.Background(), ExecOptions{})
	if err == nil {
		t.Fatal("Exec sent a batch with an unknown material, want a client-side rejection")
	}
	if len(session.sent) != 0 {
		t.Fatalf("server received %d commands, want 0 — validation must fail before sending",
			len(session.sent))
	}
	if !strings.Contains(err.Error(), "unobtanium") {
		t.Fatalf("error %q does not name the bad material", err)
	}
}

func TestExecRejectsAnUnknownOpWithoutSendingAnything(t *testing.T) {
	a, _, session := buildApp(t, `[{"op":"teleport"}]`)

	if err := a.Exec(context.Background(), ExecOptions{}); err == nil {
		t.Fatal("Exec sent an unknown op, want a client-side rejection")
	}
	if len(session.sent) != 0 {
		t.Fatalf("server received %d commands, want 0", len(session.sent))
	}
}

func TestExecDryRunValidatesWithoutSending(t *testing.T) {
	a, out, session := buildApp(t, `[{"op":"box","at":[0,0,0],"size":[4,4,4],"mat":"granite"}]`)

	if err := a.Exec(context.Background(), ExecOptions{DryRun: true}); err != nil {
		t.Fatal(err)
	}
	if len(session.sent) != 0 {
		t.Fatalf("dry run sent %d commands, want 0", len(session.sent))
	}
	if !strings.Contains(out.String(), "valid") {
		t.Fatalf("dry-run output %q does not report validity", out.String())
	}
}

func TestExecSurfacesServerSideErrorsAsAFailure(t *testing.T) {
	a, _, session := buildApp(t, `[{"op":"box","at":[0,0,0],"size":[4,4,4],"mat":"granite"}]`)
	session.ack = transport.Ack{Errors: []transport.CommandError{
		{Errors: []string{"part is out of world bounds"}},
	}}

	err := a.Exec(context.Background(), ExecOptions{})
	if err == nil {
		t.Fatal("Exec reported success despite server-side errors")
	}
	if !strings.Contains(err.Error(), "out of world bounds") {
		t.Fatalf("error %q does not carry the server's reason", err)
	}
}

// ── ergonomic forms ─────────────────────────────────────────────────────────

func TestBoxFormSendsTheEquivalentCommand(t *testing.T) {
	a, _, session := buildApp(t, "")

	err := a.RunOne(context.Background(), map[string]any{
		"op": "box", "at": []any{0.0, 0.0, 0.0}, "size": []any{2.0, 3.0, 4.0}, "mat": "gold",
	}, ExecOptions{})
	if err != nil {
		t.Fatal(err)
	}
	if len(session.sent) != 1 {
		t.Fatalf("server received %d commands, want 1", len(session.sent))
	}
	sent, _ := session.sent[0].(map[string]any)
	if sent["op"] != "box" || sent["mat"] != "gold" {
		t.Fatalf("sent command = %v, want a gold box", sent)
	}
}

func TestParseInt3AcceptsCommaSeparatedValues(t *testing.T) {
	got, err := ParseInt3("1,-2,3")
	if err != nil {
		t.Fatal(err)
	}
	if len(got) != 3 || got[0] != 1.0 || got[1] != -2.0 || got[2] != 3.0 {
		t.Fatalf("ParseInt3 = %v, want [1 -2 3]", got)
	}
}

func TestParseInt3RejectsTheWrongArity(t *testing.T) {
	if _, err := ParseInt3("1,2"); err == nil {
		t.Fatal("ParseInt3 accepted two components")
	}
}

func TestParseInt3RejectsANonInteger(t *testing.T) {
	if _, err := ParseInt3("1,x,3"); err == nil {
		t.Fatal("ParseInt3 accepted a non-numeric component")
	}
}

// ── info and materials ──────────────────────────────────────────────────────

func TestInfoCachesTheContract(t *testing.T) {
	a, _, _ := buildApp(t, "")

	if err := a.Info(context.Background(), InfoOptions{JSON: true}); err != nil {
		t.Fatal(err)
	}
	if _, err := readFile(a.Env.ContractPath()); err != nil {
		t.Fatalf("info did not cache the contract: %v", err)
	}
}

func TestMaterialsListsNamesFromTheCacheWithoutConnecting(t *testing.T) {
	a, out, _ := buildApp(t, "")
	if err := a.Info(context.Background(), InfoOptions{JSON: true}); err != nil {
		t.Fatal(err)
	}
	out.Reset()
	// Any dial from here on is a failure: the cache must serve this.
	a.Dial = func(context.Context, transport.Dialer) (Session, error) {
		t.Fatal("materials dialled the server despite a cached contract")
		return nil, nil
	}

	if err := a.Materials(context.Background(), MaterialsOptions{}); err != nil {
		t.Fatal(err)
	}
	for _, name := range []string{"granite", "glass", "gold"} {
		if !strings.Contains(out.String(), name) {
			t.Fatalf("materials output %q is missing %q", out.String(), name)
		}
	}
}

func TestMaterialsFiltersByFamily(t *testing.T) {
	a, out, _ := buildApp(t, "")
	if err := a.Info(context.Background(), InfoOptions{JSON: true}); err != nil {
		t.Fatal(err)
	}
	out.Reset()

	if err := a.Materials(context.Background(), MaterialsOptions{Family: "metal"}); err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(out.String(), "gold") {
		t.Fatalf("output %q is missing the metal material", out.String())
	}
	if strings.Contains(out.String(), "granite") {
		t.Fatalf("output %q leaked an opaque material into the metal family", out.String())
	}
}
