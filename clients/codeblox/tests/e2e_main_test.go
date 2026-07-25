//go:build integration

package tests

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"net"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
	"time"
)

// The exit-code taxonomy a wrapper branches on, duplicated from
// internal/command/exit.go on purpose: this suite is black-box, and a test that
// imports the constants it is checking cannot catch them being renumbered.
const (
	exitOK       = 0
	exitFailure  = 1
	exitUsage    = 2
	exitAuth     = 3
	exitNetwork  = 4
	exitContract = 5
	exitServer   = 6
)

// serverAddr mirrors ws.host/ws.port in config.yaml. It is duplicated rather
// than compiled from the YAML because this suite deliberately knows nothing
// about the packages under test; CODEBLOX_TEST_ADDR overrides it.
const defaultServerAddr = "127.0.0.1:7799"

// binPath is the freshly built binary under test, set by TestMain.
var binPath string

func TestMain(m *testing.M) { os.Exit(runSuite(m)) }

// runSuite builds the binary from current source and runs the suite. Building
// here rather than reusing bin/codeblox means the suite can never pass against a
// stale artifact.
func runSuite(m *testing.M) int {
	dir, err := os.MkdirTemp("", "codeblox-e2e-")
	if err != nil {
		fmt.Fprintln(os.Stderr, "e2e: create temp dir:", err)
		return 1
	}
	defer os.RemoveAll(dir)

	binPath = filepath.Join(dir, "codeblox")
	if runtime.GOOS == "windows" {
		binPath += ".exe"
	}

	build := exec.Command("go", "build", "-o", binPath, ".")
	build.Dir = ".." // the module root, one level up from tests/
	build.Stderr = os.Stderr
	if err := build.Run(); err != nil {
		fmt.Fprintln(os.Stderr, "e2e: build codeblox:", err)
		return 1
	}
	return m.Run()
}

// invocation is one run of the binary.
type invocation struct {
	args  []string
	env   map[string]string
	stdin string
}

// result is what the caller of a CLI actually observes.
type result struct {
	stdout string
	stderr string
	code   int
}

// run executes the binary in a hermetic environment: an empty home so the real
// ~/.codeblox is neither read nor written, and the file credential backend so no
// test can block on or mutate the OS keyring.
func run(t *testing.T, in invocation) result {
	t.Helper()

	home := t.TempDir()
	cmd := exec.Command(binPath, in.args...)
	cmd.Env = append(os.Environ(),
		"USERPROFILE="+home, // Go resolves the home dir from this on Windows
		"HOME="+home,        // ...and from this elsewhere
		"CODEBLOX_AUTH_BACKEND=file",
	)
	for k, v := range in.env {
		cmd.Env = append(cmd.Env, k+"="+v)
	}
	if in.stdin != "" {
		cmd.Stdin = strings.NewReader(in.stdin)
	}

	var stdout, stderr bytes.Buffer
	cmd.Stdout, cmd.Stderr = &stdout, &stderr

	var exitErr *exec.ExitError
	if err := cmd.Run(); err != nil && !errors.As(err, &exitErr) {
		t.Fatalf("running %v: %v", in.args, err)
	}
	return result{stdout: stdout.String(), stderr: stderr.String(), code: cmd.ProcessState.ExitCode()}
}

// requireFailure asserts the invocation failed the way a wrapper detects: the
// expected exit code, the reason on stderr, and nothing on stdout for a caller
// to mistake for a result.
func (r result) requireFailure(t *testing.T, wantCode int, wantIn ...string) {
	t.Helper()
	if r.code != wantCode {
		t.Fatalf("exit code %d, want %d; stderr=%q stdout=%q", r.code, wantCode, r.stderr, r.stdout)
	}
	if strings.TrimSpace(r.stdout) != "" {
		t.Errorf("failure wrote %q to stdout; a wrapper parsing stdout would read it as a result", r.stdout)
	}
	for _, want := range wantIn {
		if !strings.Contains(r.stderr, want) {
			t.Errorf("stderr %q does not contain %q", r.stderr, want)
		}
	}
}

// envelope is the --json failure shape a wrapper parses off stderr.
type envelope struct {
	OK     bool   `json:"ok"`
	Code   string `json:"code"`
	Exit   int    `json:"exit"`
	Detail string `json:"detail"`
}

// requireEnvelope asserts the failure was reported as a parseable JSON envelope
// rather than prose, which is what lets a wrapper use one parser for both paths.
func (r result) requireEnvelope(t *testing.T, wantCode int, wantToken string) envelope {
	t.Helper()
	if r.code != wantCode {
		t.Fatalf("exit code %d, want %d; stderr=%q", r.code, wantCode, r.stderr)
	}
	var env envelope
	if err := json.Unmarshal([]byte(strings.TrimSpace(r.stderr)), &env); err != nil {
		t.Fatalf("stderr is not a JSON envelope: %v\nstderr=%q", err, r.stderr)
	}
	if env.OK {
		t.Error("envelope reports ok=true for a failure")
	}
	if env.Exit != wantCode {
		t.Errorf("envelope exit = %d, want %d", env.Exit, wantCode)
	}
	if wantToken != "" && env.Code != wantToken {
		t.Errorf("envelope code = %q, want %q", env.Code, wantToken)
	}
	return env
}

func serverAddr() string {
	if v := os.Getenv("CODEBLOX_TEST_ADDR"); v != "" {
		return v
	}
	return defaultServerAddr
}

// requireServer skips unless the ws server is listening. Only the tests that
// genuinely need a world are skipped, so the rest of the suite runs without
// `npm start`.
func requireServer(t *testing.T) {
	t.Helper()
	addr := serverAddr()
	conn, err := net.DialTimeout("tcp", addr, 500*time.Millisecond)
	if err != nil {
		t.Skipf("no codeblox server on %s — run `npm start` to include this test", addr)
	}
	conn.Close()
}

// serverEnv points the CLI at the local server. config.yaml ships with
// ws.auth.required = false, so any token satisfies the client-side check that
// would otherwise stop the call before it dials.
func serverEnv() map[string]string {
	return map[string]string{
		"CODEBLOX_ENDPOINT": "ws://" + serverAddr(),
		"CODEBLOX_TOKEN":    "e2e-token-not-a-real-secret",
	}
}
