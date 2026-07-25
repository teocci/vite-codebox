package command

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"strings"
	"testing"
)

func TestExitCodeForClassifiedErrors(t *testing.T) {
	tests := []struct {
		name string
		err  error
		want int
	}{
		{"nil is success", nil, ExitOK},
		{"unclassified falls back", errors.New("something"), ExitFailure},
		{"usage", usagef("bad flag"), ExitUsage},
		{"auth", fail(ExitAuth, "not_authenticated", errors.New("no token")), ExitAuth},
		{"network", fail(ExitNetwork, "unreachable", errors.New("dial")), ExitNetwork},
		{"contract", fail(ExitContract, "contract_rejected", errors.New("bad material")), ExitContract},
		{"server", fail(ExitServer, "server_rejected", errors.New("out of bounds")), ExitServer},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := ExitCodeFor(tt.err); got != tt.want {
				t.Errorf("ExitCodeFor(%v) = %d, want %d", tt.err, got, tt.want)
			}
		})
	}
}

func TestClassificationSurvivesWrapping(t *testing.T) {
	// A classified error keeps its code when a caller adds context, otherwise
	// the category would be lost at the first %w up the stack.
	wrapped := fmt.Errorf("while building: %w", fail(ExitServer, "server_rejected", errors.New("bounds")))
	if got := ExitCodeFor(wrapped); got != ExitServer {
		t.Errorf("exit code %d after wrapping, want %d", got, ExitServer)
	}
}

func TestInnermostClassificationWins(t *testing.T) {
	// Re-classifying an already-classified error must not overwrite it: the
	// site closest to the cause knows best. A dial failure that is really an
	// auth rejection stays auth.
	inner := fail(ExitAuth, "unauthorized", errors.New("token refused"))
	outer := fail(ExitNetwork, "unreachable", inner)
	if got := ExitCodeFor(outer); got != ExitAuth {
		t.Errorf("exit code %d, want the inner %d", got, ExitAuth)
	}
}

func TestFailLeavesNilAlone(t *testing.T) {
	if err := fail(ExitServer, "server_rejected", nil); err != nil {
		t.Errorf("fail(nil) = %v, want nil", err)
	}
}

func TestWantsJSONRecognisesEverySpelling(t *testing.T) {
	yes := [][]string{
		{"exec", "--json"},
		{"exec", "-json"},
		{"exec", "--json=true"},
		{"info", "--endpoint", "ws://x", "--json"},
	}
	for _, argv := range yes {
		if !WantsJSON(argv) {
			t.Errorf("WantsJSON(%v) = false, want true", argv)
		}
	}
	no := [][]string{
		{"exec"},
		{"exec", "--dry-run"},
		{"box", "--mat", "json"}, // a value that happens to read as the flag
	}
	for _, argv := range no {
		if WantsJSON(argv) {
			t.Errorf("WantsJSON(%v) = true, want false", argv)
		}
	}
}

func TestRenderFailureAsProse(t *testing.T) {
	var buf bytes.Buffer
	RenderFailure(&buf, usagef("unknown command %q", "teleport"), false)

	got := buf.String()
	if !strings.HasPrefix(got, "codeblox: ") {
		t.Errorf("prose failure %q is not prefixed with the binary name", got)
	}
	if !strings.Contains(got, "teleport") {
		t.Errorf("prose failure %q does not name the offender", got)
	}
}

func TestRenderFailureAsJSONEnvelope(t *testing.T) {
	var buf bytes.Buffer
	RenderFailure(&buf, fail(ExitServer, "server_rejected", errors.New("part is out of world bounds")), true)

	var envelope struct {
		OK     bool   `json:"ok"`
		Code   string `json:"code"`
		Exit   int    `json:"exit"`
		Detail string `json:"detail"`
	}
	if err := json.Unmarshal(buf.Bytes(), &envelope); err != nil {
		t.Fatalf("envelope is not valid JSON: %v\ngot %q", err, buf.String())
	}
	if envelope.OK {
		t.Error("envelope reports ok=true for a failure")
	}
	if envelope.Code != "server_rejected" {
		t.Errorf("code = %q, want %q", envelope.Code, "server_rejected")
	}
	if envelope.Exit != ExitServer {
		t.Errorf("exit = %d, want %d", envelope.Exit, ExitServer)
	}
	if !strings.Contains(envelope.Detail, "out of world bounds") {
		t.Errorf("detail %q lost the reason", envelope.Detail)
	}
}

func TestRenderFailureEnvelopeCarriesAnExitCodeForUnclassifiedErrors(t *testing.T) {
	// An unclassified error must still produce a parseable envelope; a wrapper
	// should never have to handle "sometimes JSON, sometimes not".
	var buf bytes.Buffer
	RenderFailure(&buf, errors.New("something went wrong"), true)

	var envelope map[string]any
	if err := json.Unmarshal(buf.Bytes(), &envelope); err != nil {
		t.Fatalf("envelope is not valid JSON: %v\ngot %q", err, buf.String())
	}
	if envelope["exit"] != float64(ExitFailure) {
		t.Errorf("exit = %v, want %d", envelope["exit"], ExitFailure)
	}
}

func TestRenderFailureIgnoresNil(t *testing.T) {
	var buf bytes.Buffer
	RenderFailure(&buf, nil, true)
	if buf.Len() != 0 {
		t.Errorf("wrote %q for a nil error, want nothing", buf.String())
	}
}
