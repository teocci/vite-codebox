package command

import (
	"bufio"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"strconv"
	"strings"

	"github.com/teocci/vite-codebox/clients/codeblox/internal/contract"
	"github.com/teocci/vite-codebox/clients/codeblox/internal/creds"
	"github.com/teocci/vite-codebox/clients/codeblox/internal/transport"
)

// vectorLen is the arity of a coordinate/extent flag such as --at 0,0,0.
const vectorLen = 3

// ExecOptions configures the command-submitting verbs.
type ExecOptions struct {
	Endpoint   string
	ConfigPath string
	Insecure   bool
	JSON       bool
	// DryRun validates the batch against the contract and stops before sending.
	DryRun bool
}

// InfoOptions configures `codeblox info`.
type InfoOptions struct {
	Endpoint   string
	ConfigPath string
	Insecure   bool
	JSON       bool
}

// MaterialsOptions configures `codeblox materials`.
type MaterialsOptions struct {
	Endpoint   string
	ConfigPath string
	Insecure   bool
	JSON       bool
	// Family narrows the listing to one render family.
	Family string
	// Refresh forces a fetch even when a cached contract exists.
	Refresh bool
}

// execReport is the machine-readable result of a batch submission.
type execReport struct {
	OK       bool     `json:"ok"`
	Sent     int      `json:"sent"`
	AddedIDs []int    `json:"addedIds"`
	Removed  []int    `json:"removed"`
	Cleared  bool     `json:"cleared"`
	Errors   []string `json:"errors,omitempty"`
}

// dryRunReport is the machine-readable result of --dry-run. It is a distinct
// shape from execReport because "nothing was sent" and "sent, and 0 landed" are
// different outcomes a caller must not confuse.
type dryRunReport struct {
	OK        bool `json:"ok"`
	Validated int  `json:"validated"`
	Sent      int  `json:"sent"`
}

// ParseBatch reads a command batch: a JSON array, a single JSON object, or NDJSON
// (one object per line). Blank lines are skipped so a heredoc stays readable.
func ParseBatch(r io.Reader) ([]map[string]any, error) {
	raw, err := io.ReadAll(r)
	if err != nil {
		return nil, fmt.Errorf("read batch: %w", err)
	}
	trimmed := strings.TrimSpace(string(raw))
	if trimmed == "" {
		return nil, errors.New("empty batch — pass commands as a JSON array, one object, or NDJSON")
	}

	if strings.HasPrefix(trimmed, "[") {
		var batch []map[string]any
		if err := json.Unmarshal([]byte(trimmed), &batch); err != nil {
			return nil, fmt.Errorf("parse batch array: %w", err)
		}
		return batch, nil
	}
	return parseNDJSON(trimmed)
}

// parseNDJSON reads one JSON object per non-blank line.
func parseNDJSON(text string) ([]map[string]any, error) {
	var batch []map[string]any
	scanner := bufio.NewScanner(strings.NewReader(text))
	scanner.Buffer(make([]byte, 0, 64*1024), 8*1024*1024)
	for line := 1; scanner.Scan(); line++ {
		item := strings.TrimSpace(scanner.Text())
		if item == "" {
			continue
		}
		var cmd map[string]any
		if err := json.Unmarshal([]byte(item), &cmd); err != nil {
			return nil, fmt.Errorf("parse batch line %d: %w", line, err)
		}
		batch = append(batch, cmd)
	}
	if err := scanner.Err(); err != nil {
		return nil, fmt.Errorf("read batch: %w", err)
	}
	if len(batch) == 0 {
		return nil, errors.New("empty batch — no commands found")
	}
	return batch, nil
}

// ParseInt3 parses an "x,y,z" flag value into JSON-shaped numbers.
func ParseInt3(value string) ([]any, error) {
	parts := strings.Split(value, ",")
	if len(parts) != vectorLen {
		return nil, fmt.Errorf("want %d comma-separated integers, got %q", vectorLen, value)
	}
	out := make([]any, 0, vectorLen)
	for _, part := range parts {
		n, err := strconv.Atoi(strings.TrimSpace(part))
		if err != nil {
			return nil, fmt.Errorf("%q is not an integer in %q", part, value)
		}
		out = append(out, float64(n))
	}
	return out, nil
}

// Exec reads a batch from stdin and submits it.
func (a *App) Exec(ctx context.Context, opts ExecOptions) error {
	batch, err := ParseBatch(a.Stdin)
	if err != nil {
		// Malformed or empty stdin is the caller's input, not a server problem.
		return fail(ExitUsage, "usage", err)
	}
	return a.RunBatch(ctx, batch, opts)
}

// RunOne submits a single command — the ergonomic box/sphere/cylinder forms.
func (a *App) RunOne(ctx context.Context, cmd map[string]any, opts ExecOptions) error {
	return a.RunBatch(ctx, []map[string]any{cmd}, opts)
}

// RunBatch validates a batch against the server's contract and submits it.
//
// Validation is client-side and fails before anything is sent, which saves a
// round trip and keeps a typo from reaching the world. The server still
// re-validates as the authority — notably world bounds, which the published
// schema does not describe.
func (a *App) RunBatch(ctx context.Context, batch []map[string]any, opts ExecOptions) error {
	session, spec, err := a.session(ctx, dialOptions{
		Endpoint: opts.Endpoint, ConfigPath: opts.ConfigPath, Insecure: opts.Insecure,
	})
	if err != nil {
		return err
	}
	defer session.Close()

	if bad := spec.ValidateBatch(batch); len(bad) > 0 {
		return batchRejection(bad)
	}
	if opts.DryRun {
		if opts.JSON {
			return a.emitJSON(dryRunReport{OK: true, Validated: len(batch)})
		}
		fmt.Fprintf(a.Stdout, "%d command(s) valid against the server contract; nothing sent\n",
			len(batch))
		return nil
	}

	ack, err := session.SendBatch(ctx, toAnySlice(batch))
	if err != nil {
		return err
	}
	return a.reportAck(ack, len(batch), opts.JSON)
}

// reportAck renders the server's ack and fails when it carries command errors.
func (a *App) reportAck(ack transport.Ack, sent int, asJSON bool) error {
	var reasons []string
	for _, e := range ack.Errors {
		reasons = append(reasons, strings.Join(e.Errors, "; "))
	}
	report := execReport{
		OK: len(reasons) == 0, Sent: sent, AddedIDs: ack.AddedIDs,
		Removed: ack.Removed, Cleared: ack.Cleared, Errors: reasons,
	}

	if asJSON {
		if err := a.emitJSON(report); err != nil {
			return err
		}
	} else {
		fmt.Fprintf(a.Stdout, "sent %d command(s): %d added, %d removed, cleared=%v\n",
			sent, len(ack.AddedIDs), len(ack.Removed), ack.Cleared)
		if len(ack.AddedIDs) > 0 {
			fmt.Fprintf(a.Stdout, "ids: %v\n", ack.AddedIDs)
		}
	}
	if len(reasons) > 0 {
		return fail(ExitServer, "server_rejected",
			fmt.Errorf("server rejected %d command(s): %s", len(reasons), strings.Join(reasons, " | ")))
	}
	return nil
}

// Info fetches the contract, caches it, and prints it.
func (a *App) Info(ctx context.Context, opts InfoOptions) error {
	session, spec, err := a.session(ctx, dialOptions{
		Endpoint: opts.Endpoint, ConfigPath: opts.ConfigPath, Insecure: opts.Insecure,
	})
	if err != nil {
		return err
	}
	defer session.Close()

	if opts.JSON {
		return a.emitJSON(spec)
	}
	fmt.Fprintf(a.Stdout, "block size: %g m (%s)   world extent: %g m   grid step: %g m\n",
		spec.Config.BlockSize, spec.Config.BlockLabel, spec.Config.Extent, spec.Config.GridStep)
	fmt.Fprintf(a.Stdout, "bounds: ±%d blocks horizontally, %d blocks high\n",
		spec.Config.BoundBlocks, spec.Config.HeightBlocks)
	fmt.Fprintf(a.Stdout, "materials: %d (run `codeblox materials`)\n", len(spec.Palette))
	fmt.Fprintf(a.Stdout, "ops:\n")
	for _, op := range spec.Ops {
		fmt.Fprintf(a.Stdout, "  %-11s %s\n", op.Op, fieldSummary(op))
	}
	return nil
}

// Materials lists the palette, preferring the cache so it needs no server.
func (a *App) Materials(ctx context.Context, opts MaterialsOptions) error {
	spec, err := a.contractFromCache(ctx, opts)
	if err != nil {
		return err
	}

	names := spec.MaterialNames()
	if opts.Family != "" {
		names = spec.MaterialNamesByFamily(opts.Family)
		if len(names) == 0 {
			return fail(ExitContract, "unknown_family",
				fmt.Errorf("no materials in family %q: server publishes %v",
					opts.Family, spec.Families()))
		}
	}

	if opts.JSON {
		return a.emitJSON(names)
	}
	for _, name := range names {
		fmt.Fprintf(a.Stdout, "%s\t%s\n", name, spec.Palette[name].Family)
	}
	fmt.Fprintf(a.Stdout, "%d material(s)\n", len(names))
	return nil
}

// contractFromCache returns the cached contract, fetching only when absent or
// when --refresh was given.
func (a *App) contractFromCache(ctx context.Context, opts MaterialsOptions) (contract.Contract, error) {
	if !opts.Refresh {
		spec, err := contract.Load(a.Env.ContractPath())
		if err == nil {
			return spec, nil
		}
		if !errors.Is(err, contract.ErrNotCached) {
			return contract.Contract{}, err
		}
	}
	session, spec, err := a.session(ctx, dialOptions{
		Endpoint: opts.Endpoint, ConfigPath: opts.ConfigPath, Insecure: opts.Insecure,
	})
	if err != nil {
		return contract.Contract{}, err
	}
	defer session.Close()
	return spec, nil
}

// dialOptions is the connection-shaped subset every verb shares.
type dialOptions struct {
	Endpoint   string
	ConfigPath string
	Insecure   bool
}

// connection is a dialed session plus how it was reached. `auth status` reports
// these facts; the build verbs only need the session.
type connection struct {
	session  Session
	endpoint string
	token    string
	source   string
}

// connect resolves the endpoint and credential, refuses an unsafe transport,
// and dials — classifying every failure on the way.
//
// Both the build verbs and `auth status` go through here. They used to repeat
// these four steps, which is how `auth status` ended up returning an
// unclassified exit 1 for failures the build path already reported as auth or
// network.
func (a *App) connect(ctx context.Context, opts dialOptions) (connection, error) {
	endpoint, err := a.Env.Endpoint(opts.Endpoint, opts.ConfigPath)
	if err != nil {
		// A malformed endpoint came from a flag, an env var, or the settings
		// file — the caller supplied it either way.
		return connection{}, fail(ExitUsage, "usage", err)
	}

	token, source, err := creds.Resolve(a.Store, a.Env)
	if errors.Is(err, creds.ErrNoCredential) {
		return connection{}, fail(ExitAuth, "not_authenticated",
			errors.New("not authenticated — run `codeblox auth login`"))
	}
	if err != nil {
		return connection{}, fail(ExitAuth, "credential_unreadable", err)
	}

	// The guard runs before the dial so a rejected endpoint never puts the
	// token on the wire.
	if err := transport.CheckTransportSecurity(endpoint, opts.Insecure); err != nil {
		return connection{}, fail(ExitNetwork, "insecure_transport", err)
	}

	session, err := a.dial(ctx, transport.Dialer{
		Endpoint: endpoint, Token: token, Insecure: opts.Insecure,
	})
	if err != nil {
		if errors.Is(err, transport.ErrUnauthorized) {
			return connection{}, fail(ExitAuth, "unauthorized", err)
		}
		return connection{}, fail(ExitNetwork, "unreachable", err)
	}
	return connection{session: session, endpoint: endpoint, token: token, source: source}, nil
}

// session authenticates, connects, and returns the live session plus the freshly
// published contract, which it also caches.
func (a *App) session(ctx context.Context, opts dialOptions) (Session, contract.Contract, error) {
	conn, err := a.connect(ctx, opts)
	if err != nil {
		return nil, contract.Contract{}, err
	}
	session := conn.session

	var spec contract.Contract
	if err := json.Unmarshal(session.Contract(), &spec); err != nil {
		session.Close()
		return nil, contract.Contract{}, fmt.Errorf("parse server contract: %w", err)
	}
	// Best-effort: a read-only home must not fail an otherwise good command.
	_ = spec.Save(a.Env.ContractPath())
	return session, spec, nil
}

// batchRejection turns client-side validation failures into one actionable error.
func batchRejection(bad []contract.BadCommand) error {
	var lines []string
	for _, b := range bad {
		lines = append(lines, fmt.Sprintf("command %d: %s", b.Index, strings.Join(b.Errors, "; ")))
	}
	return fail(ExitContract, "contract_rejected",
		fmt.Errorf("%d command(s) rejected before sending:\n  %s",
			len(bad), strings.Join(lines, "\n  ")))
}

// fieldSummary renders an op's fields as `name:type` pairs, in a stable order.
func fieldSummary(op contract.Op) string {
	if len(op.Fields) == 0 {
		return "(no fields)"
	}
	names := make([]string, 0, len(op.Fields))
	for name := range op.Fields {
		names = append(names, name)
	}
	sortStrings(names)
	parts := make([]string, 0, len(names))
	for _, name := range names {
		parts = append(parts, name+":"+op.Fields[name])
	}
	return strings.Join(parts, "  ")
}

func sortStrings(s []string) {
	for i := 1; i < len(s); i++ {
		for j := i; j > 0 && s[j] < s[j-1]; j-- {
			s[j], s[j-1] = s[j-1], s[j]
		}
	}
}

func toAnySlice(batch []map[string]any) []any {
	out := make([]any, 0, len(batch))
	for _, cmd := range batch {
		out = append(out, cmd)
	}
	return out
}
