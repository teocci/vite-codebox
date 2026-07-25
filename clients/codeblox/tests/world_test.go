//go:build integration

package tests

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

// These drive a live world. They skip when the ws server is not listening, so
// `go test -tags=integration ./tests/` is still meaningful without `npm start`.

func TestInfoFetchesTheContractAsParseableJSON(t *testing.T) {
	requireServer(t)

	got := run(t, invocation{args: []string{"info", "--json"}, env: serverEnv()})
	if got.code != 0 {
		t.Fatalf("exit %d, want 0; stderr=%q", got.code, got.stderr)
	}

	// The point of --json is that a wrapper can parse it without knowing the
	// schema in advance; P-5's world.py does exactly this.
	var contract map[string]any
	if err := json.Unmarshal([]byte(got.stdout), &contract); err != nil {
		t.Fatalf("info --json is not valid JSON: %v\nstdout=%q", err, got.stdout)
	}
	if len(contract) == 0 {
		t.Error("contract is empty")
	}
}

func TestExecBuildsABatchReadFromStdin(t *testing.T) {
	requireServer(t)

	batch, err := os.ReadFile(filepath.Join("testdata", "bridge.ndjson"))
	if err != nil {
		t.Fatal(err)
	}

	got := run(t, invocation{
		args:  []string{"exec", "--json"},
		env:   serverEnv(),
		stdin: string(batch),
	})
	if got.code != 0 {
		t.Fatalf("exit %d, want 0; stderr=%q", got.code, got.stderr)
	}

	var report struct {
		OK       bool     `json:"ok"`
		Sent     int      `json:"sent"`
		AddedIDs []int    `json:"addedIds"`
		Errors   []string `json:"errors"`
	}
	if err := json.Unmarshal([]byte(got.stdout), &report); err != nil {
		t.Fatalf("exec --json is not valid JSON: %v\nstdout=%q", err, got.stdout)
	}
	if !report.OK {
		t.Fatalf("server rejected the batch: %v", report.Errors)
	}
	if want := 5; report.Sent != want {
		t.Errorf("sent %d commands, want %d", report.Sent, want)
	}
	if len(report.AddedIDs) != 5 {
		t.Errorf("addedIds = %v, want 5 ids", report.AddedIDs)
	}

	t.Cleanup(func() {
		run(t, invocation{args: []string{"clear"}, env: serverEnv()})
	})
}

func TestUnpublishedMaterialIsRejectedBeforeAnythingIsSent(t *testing.T) {
	requireServer(t)

	// Client-side: rejected against the published palette before anything is
	// sent, which is a different remedy (re-plan) than a server refusal.
	run(t, invocation{
		args:  []string{"exec", "--json"},
		env:   serverEnv(),
		stdin: `{"op":"box","at":[0,0,0],"size":[2,2,2],"mat":"unobtanium"}`,
	}).requireEnvelope(t, exitContract, "contract_rejected")
}

func TestOutOfBoundsIsAServerRejectionNotAContractOne(t *testing.T) {
	requireServer(t)

	// Bounds are deliberately server-side only — the published schema types
	// fields, it does not describe geometry — so this must surface as a server
	// rejection even though the material and shape are perfectly valid.
	run(t, invocation{
		args:  []string{"exec", "--json"},
		env:   serverEnv(),
		stdin: `{"op":"box","at":[0,-99,0],"size":[2,2,2],"mat":"oak"}`,
	}).requireEnvelope(t, exitServer, "server_rejected")
}

func TestDryRunEmitsJSONRatherThanProse(t *testing.T) {
	requireServer(t)

	got := run(t, invocation{
		args:  []string{"exec", "--dry-run", "--json"},
		env:   serverEnv(),
		stdin: `{"op":"box","at":[0,0,0],"size":[2,2,2],"mat":"oak"}`,
	})
	if got.code != exitOK {
		t.Fatalf("exit %d, want %d; stderr=%q", got.code, exitOK, got.stderr)
	}

	var report struct {
		OK        bool `json:"ok"`
		Validated int  `json:"validated"`
		Sent      int  `json:"sent"`
	}
	if err := json.Unmarshal([]byte(got.stdout), &report); err != nil {
		t.Fatalf("dry-run --json is not valid JSON: %v\nstdout=%q", err, got.stdout)
	}
	if !report.OK || report.Validated != 1 {
		t.Errorf("report = %+v, want ok with 1 validated", report)
	}
	if report.Sent != 0 {
		t.Errorf("dry run reported %d sent, want 0", report.Sent)
	}
}

// TestAnchorConventionMatchesTheServer is the drift guard for the skill's
// shapes.py, which encodes the box-corner / sphere-centre rule locally because
// world_info does not publish it: the contract types fields, it does not
// describe geometry.
//
// The check is behavioural rather than textual. A part placed so that its
// computed AABB sits exactly on the floor must be accepted, and the same part
// one block lower must be refused as out of bounds. If the server ever changed
// how it derives a part's extent from `at`, one of those two would flip.
func TestAnchorConventionMatchesTheServer(t *testing.T) {
	requireServer(t)

	cases := []struct {
		name     string
		resting  string // AABB bottom exactly at y=0
		oneBelow string // the same shape one block lower
	}{
		{
			name:     "box anchors at its minimum corner",
			resting:  `{"op":"box","at":[0,0,0],"size":[2,2,2],"mat":"oak"}`,
			oneBelow: `{"op":"box","at":[0,-1,0],"size":[2,2,2],"mat":"oak"}`,
		},
		{
			name:     "sphere anchors at its centre",
			resting:  `{"op":"sphere","at":[0,5,0],"r":5,"mat":"oak"}`,
			oneBelow: `{"op":"sphere","at":[0,4,0],"r":5,"mat":"oak"}`,
		},
		{
			name:     "cylinder centres its height on at",
			resting:  `{"op":"cylinder","at":[0,4,0],"r":2,"h":8,"mat":"oak"}`,
			oneBelow: `{"op":"cylinder","at":[0,3,0],"r":2,"h":8,"mat":"oak"}`,
		},
	}

	// These must be sent for real, not dry-run: --dry-run validates against the
	// published schema, which types fields and says nothing about geometry, so
	// bounds are only evaluated once the server sees the batch.
	t.Cleanup(func() {
		run(t, invocation{args: []string{"clear"}, env: serverEnv()})
	})

	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			got := run(t, invocation{
				args: []string{"exec", "--json"}, env: serverEnv(), stdin: c.resting,
			})
			if got.code != exitOK {
				t.Fatalf("a part resting on the floor was refused (exit %d): %s\n"+
					"shapes.py's anchoring no longer matches the server", got.code, got.stderr)
			}

			// One block lower: its AABB now dips below y=0, so the server must
			// refuse it. If this is accepted, the server derives a part's extent
			// from `at` differently than shapes.py does, and every generated
			// structure is placed wrong.
			run(t, invocation{
				args: []string{"exec", "--json"}, env: serverEnv(), stdin: c.oneBelow,
			}).requireEnvelope(t, exitServer, "server_rejected")
		})
	}
}
