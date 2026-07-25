package command

import (
	"context"
	"strings"
	"testing"
)

// flagKind tells the table how to spell a flag on a command line: a bool flag
// stands alone, a value flag needs a following token.
type flagKind int

const (
	boolFlag flagKind = iota
	valueFlag
)

// everyFlag is every flag name the CLI defines anywhere. The table below drives
// each verb against all of them, so a flag registered on a verb that ignores it
// fails here rather than silently doing nothing on an operator's machine.
var everyFlag = map[string]flagKind{
	"backend":    valueFlag,
	"config":     valueFlag,
	"endpoint":   valueFlag,
	"insecure":   boolFlag,
	"json":       boolFlag,
	"dry-run":    boolFlag,
	"refresh":    boolFlag,
	"family":     valueFlag,
	"at":         valueFlag,
	"size":       valueFlag,
	"mat":        valueFlag,
	"r":          valueFlag,
	"h":          valueFlag,
	"id":         valueFlag,
	"with-token": boolFlag,
}

// flagContract is the per-verb flag surface, mirroring the usage text. A verb
// accepts exactly these flags and nothing else, and no verb takes a positional
// argument — batches arrive on stdin.
var flagContract = []struct {
	verb    []string
	allowed []string
}{
	{[]string{"info"}, []string{"backend", "config", "endpoint", "insecure", "json"}},
	{[]string{"materials"}, []string{"backend", "config", "endpoint", "insecure", "json", "family", "refresh"}},
	{[]string{"exec"}, []string{"backend", "config", "endpoint", "insecure", "json", "dry-run"}},
	{[]string{"clear"}, []string{"backend", "config", "endpoint", "insecure", "json", "dry-run"}},
	{[]string{"remove"}, []string{"backend", "config", "endpoint", "insecure", "json", "dry-run", "id"}},
	{[]string{"box"}, []string{"backend", "config", "endpoint", "insecure", "json", "dry-run", "at", "size", "mat"}},
	{[]string{"sphere"}, []string{"backend", "config", "endpoint", "insecure", "json", "dry-run", "at", "r", "mat"}},
	{[]string{"cylinder"}, []string{"backend", "config", "endpoint", "insecure", "json", "dry-run", "at", "r", "h", "mat"}},

	{[]string{"auth", "login"}, []string{"backend", "config", "endpoint", "with-token"}},
	{[]string{"auth", "logout"}, []string{"backend"}},
	{[]string{"auth", "list"}, []string{"backend", "json"}},
	{[]string{"auth", "status"}, []string{"backend", "config", "endpoint", "insecure", "json"}},
}

// argvFor spells a verb plus one flag.
func argvFor(verb []string, flagName string, kind flagKind) []string {
	argv := append(append([]string{}, verb...), "--"+flagName)
	if kind == valueFlag {
		argv = append(argv, "1")
	}
	return argv
}

func TestEveryVerbRejectsFlagsItDoesNotUse(t *testing.T) {
	for _, c := range flagContract {
		verb := strings.Join(c.verb, " ")
		allowed := make(map[string]bool, len(c.allowed))
		for _, name := range c.allowed {
			allowed[name] = true
		}

		for flagName, kind := range everyFlag {
			if allowed[flagName] {
				continue
			}
			t.Run(verb+"/--"+flagName, func(t *testing.T) {
				d, _, _ := deps(t, "")
				err := Dispatch(context.Background(), d, argvFor(c.verb, flagName, kind))
				if err == nil {
					t.Fatalf("`codeblox %s --%s` was accepted, want a rejection", verb, flagName)
				}
				if !strings.Contains(err.Error(), flagName) {
					t.Fatalf("error %q does not name the rejected flag --%s", err, flagName)
				}
				if !strings.Contains(err.Error(), "valid flags") {
					t.Fatalf("error %q does not list the valid flags for %s", err, verb)
				}
			})
		}
	}
}

func TestEveryVerbAcceptsTheFlagsItDoesUse(t *testing.T) {
	// Parsing must succeed; the command then fails for its own reasons (no
	// server, missing required values). What must never happen is a parse
	// rejection naming a flag the verb legitimately accepts.
	for _, c := range flagContract {
		verb := strings.Join(c.verb, " ")
		for _, flagName := range c.allowed {
			t.Run(verb+"/--"+flagName, func(t *testing.T) {
				d, _, _ := deps(t, "")
				err := Dispatch(context.Background(), d, argvFor(c.verb, flagName, everyFlag[flagName]))
				if err != nil && strings.Contains(err.Error(), "not defined") {
					t.Fatalf("`codeblox %s --%s` was rejected as undefined: %v", verb, flagName, err)
				}
			})
		}
	}
}

func TestNoVerbAcceptsAPositionalArgument(t *testing.T) {
	// Batches arrive on stdin. A stray path used to stop flag parsing dead, so
	// `codeblox exec batch.json --json` dropped --json and exited 0 — which made
	// a wrapper parse an English sentence as JSON.
	for _, c := range flagContract {
		verb := strings.Join(c.verb, " ")
		t.Run(verb, func(t *testing.T) {
			d, _, _ := deps(t, "")
			argv := append(append([]string{}, c.verb...), "batch.json")
			err := Dispatch(context.Background(), d, argv)
			if err == nil {
				t.Fatalf("`codeblox %s batch.json` was accepted, want a rejection", verb)
			}
			if !strings.Contains(err.Error(), "batch.json") {
				t.Fatalf("error %q does not name the unexpected argument", err)
			}
		})
	}
}

func TestPositionalArgumentDoesNotSwallowALaterFlag(t *testing.T) {
	// The concrete regression: stdlib flag halts at the first non-flag token, so
	// --json landed after it was silently discarded.
	d, _, _ := deps(t, "")
	err := Dispatch(context.Background(), d, []string{"exec", "batch.json", "--json"})
	if err == nil {
		t.Fatal("`codeblox exec batch.json --json` was accepted, want a rejection")
	}
	if !strings.Contains(err.Error(), "batch.json") {
		t.Fatalf("error %q does not name the unexpected argument", err)
	}
}
