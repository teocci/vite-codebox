package command

import (
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"strings"
)

// Exit codes. The CLI's caller is a script: it has to decide what to do next —
// re-authenticate, retry with backoff, or re-plan the build — and it cannot do
// that by matching English prose that may be reworded at any time. These codes
// are the contract; the message is for the human reading the transcript.
const (
	ExitOK      = 0
	ExitFailure = 1 // unclassified — a bug in this table, not a category
	ExitUsage   = 2 // argv: unknown verb or flag, missing or malformed value
	ExitAuth    = 3 // no stored credential, or the server refused the token
	ExitNetwork = 4 // could not reach, or could not safely reach, the server
	// ExitContract is a client-side rejection: the batch failed validation
	// against the contract the server published, so nothing was sent.
	ExitContract = 5
	// ExitServer is a server-side rejection: the connection was fine and the
	// work was refused — world bounds, for instance, which the published schema
	// deliberately does not describe.
	ExitServer = 6
)

// Failure carries an error's machine-readable classification: the process exit
// code, and a stable token for the --json envelope. Only the classification is
// contractual — wrapping an error never changes its message.
type Failure struct {
	Exit int
	Code string
	err  error
}

func (f *Failure) Error() string { return f.err.Error() }
func (f *Failure) Unwrap() error { return f.err }

// fail classifies err. A nil error stays nil so call sites can wrap
// unconditionally, and an already-classified error keeps its first (innermost,
// most specific) classification.
func fail(exit int, code string, err error) error {
	if err == nil {
		return nil
	}
	var already *Failure
	if errors.As(err, &already) {
		return err
	}
	return &Failure{Exit: exit, Code: code, err: err}
}

func usagef(format string, a ...any) error {
	return fail(ExitUsage, "usage", fmt.Errorf(format, a...))
}

// ExitCodeFor maps an error to its process exit code. An unclassified error is
// ExitFailure, which is a gap in the table rather than a category of its own.
func ExitCodeFor(err error) int {
	if err == nil {
		return ExitOK
	}
	var f *Failure
	if errors.As(err, &f) {
		return f.Exit
	}
	return ExitFailure
}

// failureEnvelope is the machine-readable shape of a failure. It carries the
// exit code too, so a caller that captured only the streams still learns the
// category without inspecting the process status.
type failureEnvelope struct {
	OK     bool   `json:"ok"`
	Code   string `json:"code"`
	Exit   int    `json:"exit"`
	Detail string `json:"detail"`
}

// WantsJSON reports whether argv asked for machine-readable output.
//
// The rule is deliberately "--json anywhere in argv" rather than "the verb
// parsed --json": a usage error happens *before* parsing succeeds, and those are
// exactly the failures a script is most likely to hit. Honouring the request the
// caller visibly made is more useful than insisting it was parsed first.
func WantsJSON(args []string) bool {
	for _, a := range args {
		if a == "--json" || a == "-json" ||
			strings.HasPrefix(a, "--json=") || strings.HasPrefix(a, "-json=") {
			return true
		}
	}
	return false
}

// RenderFailure writes err to w — a JSON envelope when the caller asked for one,
// otherwise the prose line. Failures always go to stderr so that stdout carries
// only results, and a caller parsing stdout never mistakes an error for one.
func RenderFailure(w io.Writer, err error, asJSON bool) {
	if err == nil {
		return
	}
	if !asJSON {
		fmt.Fprintf(w, "codeblox: %v\n", err)
		return
	}

	envelope := failureEnvelope{Code: "error", Exit: ExitCodeFor(err), Detail: err.Error()}
	var f *Failure
	if errors.As(err, &f) {
		envelope.Code = f.Code
	}
	raw, marshalErr := json.Marshal(envelope)
	if marshalErr != nil {
		// The envelope must never be the reason a failure goes unreported.
		fmt.Fprintf(w, "codeblox: %v\n", err)
		return
	}
	fmt.Fprintln(w, string(raw))
}
