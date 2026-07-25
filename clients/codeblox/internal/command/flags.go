package command

import (
	"flag"
	"io"
	"sort"
	"strings"
)

// flagSurface is one verb's argv contract: the flags it accepts, and nothing
// else. Every verb owns its own FlagSet — a set shared across verbs accepts
// flags the verb then ignores, which reads as success to a caller that cannot
// see the no-op.
//
// The CLI's consumer is a script, so a rejection has to be actionable without a
// human reading help: errors name the verb, the offending token, and the valid
// set, in the shape internal/contract already uses for op and material errors.
type flagSurface struct {
	fs   *flag.FlagSet
	verb string
}

func newFlagSurface(verb string) flagSurface {
	fs := flag.NewFlagSet(verb, flag.ContinueOnError)
	// The caller reports the failure with more context than the FlagSet has.
	// Leaving the default output attached would print the bare message plus a
	// dump of every default, then the caller's error — the same failure three
	// times, with the useful line buried.
	fs.SetOutput(io.Discard)
	return flagSurface{fs: fs, verb: verb}
}

// parse consumes argv and rejects anything the verb does not accept: an unknown
// flag, or a positional argument. No verb takes positionals — batches arrive on
// stdin — and stdlib flag stops parsing at the first non-flag token, so without
// this guard `exec batch.json --json` would silently discard --json.
func (s flagSurface) parse(args []string) error {
	if err := s.fs.Parse(args); err != nil {
		return usagef("%s: %w; valid flags: %s", s.verb, err, s.validFlags())
	}
	if s.fs.NArg() > 0 {
		return usagef("%s: unexpected argument %q — %s takes no positional arguments; valid flags: %s",
			s.verb, s.fs.Arg(0), s.verb, s.validFlags())
	}
	return nil
}

// validFlags lists the verb's flags for an error the caller can act on.
func (s flagSurface) validFlags() string {
	names := make([]string, 0, 8)
	s.fs.VisitAll(func(f *flag.Flag) { names = append(names, "--"+f.Name) })
	sort.Strings(names)
	return strings.Join(names, ", ")
}
