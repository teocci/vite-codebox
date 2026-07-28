// Package contract models the world_info payload the server publishes and
// validates command batches against it.
//
// The CLI compiles in no op list and no palette: both arrive from the server and
// are cached under the base dir. Validation here is deliberately limited to what
// the published schema actually describes — field presence, field types, and
// material names. Geometric bounds are NOT checked client-side: the `fields` spec
// says `at` is an int3 but not that it means a min corner for `box` and a centre
// for `sphere`, so bounds would require duplicating the server's normalisation —
// exactly the compiled-in knowledge this design avoids. The server remains the
// authority and reports out-of-bounds parts in its ack.
package contract

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"sort"
)

// ErrNotCached means no contract has been fetched yet — run `codeblox info`.
var ErrNotCached = errors.New("no cached contract")

// Field type names used by the server's OP_SCHEMA.
const (
	typeInt3     = "int3"
	typeInt3Pos  = "int3+"
	typeIntPos   = "int+"
	typeID       = "id"
	typeMaterial = "material"
	typeBool     = "bool"

	vectorLen = 3
)

// Config is the server's world configuration, in the server's units.
type Config struct {
	BlockSize    float64 `json:"blockSize"`
	BlockLabel   string  `json:"blockLabel"`
	Extent       float64 `json:"extent"`
	GridStep     float64 `json:"gridStep"`
	BoundBlocks  int     `json:"boundBlocks"`
	HeightBlocks int     `json:"heightBlocks"`
}

// Material is one palette entry.
type Material struct {
	Color  int    `json:"color"`
	Family string `json:"family"`
}

// Op is one published command shape: a name and its field-type map.
type Op struct {
	Op     string            `json:"op"`
	Fields map[string]string `json:"fields"`
}

// Contract is the full world_info payload.
type Contract struct {
	Config  Config              `json:"config"`
	Palette map[string]Material `json:"palette"`
	Ops     []Op                `json:"ops"`
}

// BadCommand is one command that failed client-side validation.
type BadCommand struct {
	Index  int      `json:"index"`
	Errors []string `json:"errors"`
}

// FindOp looks up a published op by name.
func (c Contract) FindOp(name string) (Op, bool) {
	for _, op := range c.Ops {
		if op.Op == name {
			return op, true
		}
	}
	return Op{}, false
}

// OpNames lists the published ops in the order the server declared them.
func (c Contract) OpNames() []string {
	names := make([]string, 0, len(c.Ops))
	for _, op := range c.Ops {
		names = append(names, op.Op)
	}
	return names
}

// MaterialNames lists every material name, sorted.
func (c Contract) MaterialNames() []string {
	names := make([]string, 0, len(c.Palette))
	for name := range c.Palette {
		names = append(names, name)
	}
	sort.Strings(names)
	return names
}

// MaterialNamesByFamily lists the materials in one render family, sorted.
func (c Contract) MaterialNamesByFamily(family string) []string {
	var names []string
	for name, m := range c.Palette {
		if m.Family == family {
			names = append(names, name)
		}
	}
	sort.Strings(names)
	return names
}

// Families lists the distinct render families, sorted.
func (c Contract) Families() []string {
	seen := map[string]bool{}
	for _, m := range c.Palette {
		seen[m.Family] = true
	}
	names := make([]string, 0, len(seen))
	for f := range seen {
		names = append(names, f)
	}
	sort.Strings(names)
	return names
}

// ValidateCommand checks one command against the published schema and palette.
// It returns every problem found, so one round trip reports all of them.
func (c Contract) ValidateCommand(cmd map[string]any) []string {
	name, ok := cmd["op"].(string)
	if !ok {
		return []string{"missing `op` (must be a string)"}
	}
	op, found := c.FindOp(name)
	if !found {
		return []string{fmt.Sprintf("unknown op %q: server publishes %v", name, c.OpNames())}
	}

	var errs []string
	for field, kind := range op.Fields {
		value, present := cmd[field]
		if !present {
			errs = append(errs, fmt.Sprintf("%s: missing field %q (%s)", name, field, kind))
			continue
		}
		if err := c.checkField(field, kind, value); err != nil {
			errs = append(errs, fmt.Sprintf("%s: %v", name, err))
		}
	}
	sort.Strings(errs)
	return errs
}

// ValidateBatch validates every command, reporting each failure with its index.
func (c Contract) ValidateBatch(batch []map[string]any) []BadCommand {
	var bad []BadCommand
	for i, cmd := range batch {
		if errs := c.ValidateCommand(cmd); len(errs) > 0 {
			bad = append(bad, BadCommand{Index: i, Errors: errs})
		}
	}
	return bad
}

// checkField validates one value against one published field type.
func (c Contract) checkField(field, kind string, value any) error {
	switch kind {
	case typeInt3:
		return checkVector(field, value, false)
	case typeInt3Pos:
		return checkVector(field, value, true)
	case typeIntPos:
		n, ok := asInt(value)
		if !ok || n <= 0 {
			return fmt.Errorf("%s must be a positive integer, got %v", field, value)
		}
	case typeID:
		n, ok := asInt(value)
		if !ok || n < 0 {
			return fmt.Errorf("%s must be a non-negative integer, got %v", field, value)
		}
	case typeBool:
		// Implemented rather than deferred, unlike `axis`. The distinction is the
		// value domain: `axis` means x|y|z, which is server data this package
		// refuses to compile in, while `bool` is a structural JSON check fully
		// described by its type name — the same category as int+ and id.
		//
		// It matters because of how the server fails, not for tidiness. applyBatch
		// records a rejected command and continues, so a batch of thirty parts
		// ending in {"op":"rotate","on":"yes"} lands all thirty and silently does
		// not rotate, with the reason buried in an ack this client drops. Checking
		// here kills the batch before anything is sent.
		if _, ok := value.(bool); !ok {
			return fmt.Errorf("%s must be true or false, got %v", field, value)
		}
	case typeMaterial:
		name, ok := value.(string)
		if !ok {
			return fmt.Errorf("%s must be a material name, got %v", field, value)
		}
		if _, known := c.Palette[name]; !known {
			return fmt.Errorf("unknown material %q: run `codeblox materials` for the %d the server accepts",
				name, len(c.Palette))
		}
	default:
		// An unrecognised type means the server published a field kind this
		// build does not know. Defer to the server rather than guessing.
		return nil
	}
	return nil
}

// checkVector validates an int3 / int3+ field.
func checkVector(field string, value any, positive bool) error {
	items, ok := value.([]any)
	if !ok || len(items) != vectorLen {
		return fmt.Errorf("%s must be %d integers, got %v", field, vectorLen, value)
	}
	for i, item := range items {
		n, ok := asInt(item)
		if !ok {
			return fmt.Errorf("%s[%d] must be an integer, got %v", field, i, item)
		}
		if positive && n <= 0 {
			return fmt.Errorf("%s[%d] must be positive, got %v", field, i, n)
		}
	}
	return nil
}

// asInt accepts a JSON number that holds an exact integer.
func asInt(value any) (int, bool) {
	f, ok := value.(float64)
	if !ok || f != float64(int(f)) {
		return 0, false
	}
	return int(f), true
}

// ── cache ───────────────────────────────────────────────────────────────────

// Load reads a cached contract.
func Load(path string) (Contract, error) {
	raw, err := os.ReadFile(path)
	if errors.Is(err, os.ErrNotExist) {
		return Contract{}, ErrNotCached
	}
	if err != nil {
		return Contract{}, fmt.Errorf("read cached contract: %w", err)
	}
	var c Contract
	if err := json.Unmarshal(raw, &c); err != nil {
		return Contract{}, fmt.Errorf("parse cached contract %s: %w", path, err)
	}
	return c, nil
}

// Save writes the contract to the cache, creating the directory if needed.
func (c Contract) Save(path string) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		return fmt.Errorf("create cache dir: %w", err)
	}
	raw, err := json.Marshal(c)
	if err != nil {
		return fmt.Errorf("encode contract: %w", err)
	}
	if err := os.WriteFile(path, raw, 0o600); err != nil {
		return fmt.Errorf("write cached contract %s: %w", path, err)
	}
	return nil
}
