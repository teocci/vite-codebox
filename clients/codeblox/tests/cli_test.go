//go:build integration

package tests

import (
	"strings"
	"testing"
)

// These need no server. They lock the properties a wrapper depends on and that
// unit tests cannot observe: which stream carries what, and the exit code.

func TestVersionGoesToStdoutAndSucceeds(t *testing.T) {
	got := run(t, invocation{args: []string{"version"}})
	if got.code != exitOK {
		t.Fatalf("exit %d, want %d; stderr=%q", got.code, exitOK, got.stderr)
	}
	if !strings.HasPrefix(got.stdout, "codeblox ") {
		t.Errorf("stdout %q does not start with the binary name", got.stdout)
	}
	if strings.TrimSpace(got.stderr) != "" {
		t.Errorf("version wrote %q to stderr, want it clean", got.stderr)
	}
}

func TestBareInvocationFailsWithUsageOnStderr(t *testing.T) {
	// A wrapper that computes an empty argv must not read success. This used to
	// print usage to stdout and exit 0.
	got := run(t, invocation{})
	got.requireFailure(t, exitUsage, "auth")
}

func TestHelpSucceedsOnStdout(t *testing.T) {
	// `help` is a request, not a mistake — it is a result, so it belongs on
	// stdout with a success code.
	got := run(t, invocation{args: []string{"help"}})
	if got.code != exitOK {
		t.Fatalf("exit %d, want %d", got.code, exitOK)
	}
	if !strings.Contains(got.stdout, "auth") {
		t.Errorf("help output %q does not list the auth command", got.stdout)
	}
}

func TestUnknownVerbIsRejectedAsUsage(t *testing.T) {
	run(t, invocation{args: []string{"teleport"}}).
		requireFailure(t, exitUsage, "teleport")
}

func TestUnknownAuthSubcommandIsRejectedWithoutOpeningAStore(t *testing.T) {
	run(t, invocation{args: []string{"auth", "renew", "--backend", "file"}}).
		requireFailure(t, exitUsage, "renew", "login, logout, list, or status")
}

func TestUnknownBackendIsRejectedAsUsage(t *testing.T) {
	run(t, invocation{args: []string{"auth", "list", "--backend", "carrier-pigeon"}}).
		requireFailure(t, exitUsage, "carrier-pigeon")
}

func TestMissingCredentialIsAuthNotNetwork(t *testing.T) {
	// The distinction a wrapper acts on: re-authenticate, do not retry.
	run(t, invocation{args: []string{"info"}, env: map[string]string{
		"CODEBLOX_ENDPOINT": "ws://" + serverAddr(),
	}}).requireFailure(t, exitAuth, "not authenticated")
}

func TestUnreachableServerIsNetworkNotAuth(t *testing.T) {
	// Retry with backoff, do not re-authenticate. Port 1 is reserved and never
	// listening, so this is deterministic without a server.
	run(t, invocation{args: []string{"info"}, env: map[string]string{
		"CODEBLOX_ENDPOINT": "ws://127.0.0.1:1",
		"CODEBLOX_TOKEN":    "e2e-token-not-a-real-secret",
	}}).requireFailure(t, exitNetwork)
}

func TestPlainWsToARemoteHostIsRefused(t *testing.T) {
	run(t, invocation{args: []string{"info"}, env: map[string]string{
		"CODEBLOX_ENDPOINT": "ws://example.invalid:7799",
		"CODEBLOX_TOKEN":    "e2e-token-not-a-real-secret",
	}}).requireFailure(t, exitNetwork, "refusing to send the token")
}

// I-1 regressions, asserted at the binary boundary.

func TestForeignFlagIsRejectedAndNamesTheValidSet(t *testing.T) {
	run(t, invocation{args: []string{"clear", "--r", "5", "--id", "9"}}).
		requireFailure(t, exitUsage, "clear", "-r", "valid flags")
}

func TestFlagBelongingToAnotherSubcommandIsRejected(t *testing.T) {
	run(t, invocation{args: []string{"auth", "status", "--with-token"}}).
		requireFailure(t, exitUsage, "with-token", "valid flags")
}

func TestDryRunIsRejectedByVerbsThatDoNotHaveIt(t *testing.T) {
	run(t, invocation{args: []string{"info", "--dry-run"}}).
		requireFailure(t, exitUsage, "dry-run", "valid flags")
}

func TestPositionalArgumentIsRejectedRatherThanSwallowingALaterFlag(t *testing.T) {
	// The regression that mattered most: this used to discard --json, print
	// prose to stdout, and exit 0, so a wrapper parsed an English sentence as
	// JSON and crashed with a traceback that blamed the wrapper.
	run(t, invocation{args: []string{"exec", "batch.json", "--json"}}).
		requireEnvelope(t, exitUsage, "usage")
}

func TestStrayArgumentIsRejectedByAuthSubcommands(t *testing.T) {
	for _, sub := range []string{"logout", "list"} {
		t.Run(sub, func(t *testing.T) {
			run(t, invocation{args: []string{"auth", sub, "batch.json"}}).
				requireFailure(t, exitUsage, "batch.json", "positional")
		})
	}
}

func TestShapeVerbReportsItsMissingFlagWithoutTouchingCredentials(t *testing.T) {
	// No --mat. The failure must come from argv validation, not the credential
	// store, which argv validation now precedes.
	got := run(t, invocation{args: []string{"box", "--at", "0,0,0", "--size", "4,4,4"}})
	got.requireFailure(t, exitUsage, "--mat")
	if strings.Contains(got.stderr, "not authenticated") {
		t.Error("reported a credential problem before reporting the missing flag")
	}
}

// I-2: the --json failure envelope.

func TestFailuresAreJSONWhenTheCallerAsksForIt(t *testing.T) {
	env := run(t, invocation{args: []string{"info", "--json"}, env: map[string]string{
		"CODEBLOX_ENDPOINT": "ws://" + serverAddr(),
	}}).requireEnvelope(t, exitAuth, "not_authenticated")

	if !strings.Contains(env.Detail, "auth login") {
		t.Errorf("detail %q does not tell the caller how to recover", env.Detail)
	}
}

func TestEmptyStdinIsAUsageEnvelope(t *testing.T) {
	run(t, invocation{args: []string{"exec", "--json"}, stdin: "\n"}).
		requireEnvelope(t, exitUsage, "usage")
}
