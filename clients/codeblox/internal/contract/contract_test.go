package contract

import (
	"encoding/json"
	"errors"
	"path/filepath"
	"strings"
	"testing"
)

// sample mirrors the real server contract (shared/protocol.js contract()), trimmed
// to three materials.
const sample = `{
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
    {"op":"remove","fields":{"id":"id"}},
    {"op":"clear","fields":{}}
  ]
}`

func parse(t *testing.T) Contract {
	t.Helper()
	var c Contract
	if err := json.Unmarshal([]byte(sample), &c); err != nil {
		t.Fatal(err)
	}
	return c
}

func cmd(t *testing.T, body string) map[string]any {
	t.Helper()
	var m map[string]any
	if err := json.Unmarshal([]byte(body), &m); err != nil {
		t.Fatal(err)
	}
	return m
}

func TestParsesConfigPaletteAndOps(t *testing.T) {
	c := parse(t)
	if c.Config.BlockLabel != "2 cm" {
		t.Fatalf("BlockLabel = %q, want %q", c.Config.BlockLabel, "2 cm")
	}
	if c.Config.BoundBlocks != 1600 {
		t.Fatalf("BoundBlocks = %d, want 1600", c.Config.BoundBlocks)
	}
	if len(c.Palette) != 3 {
		t.Fatalf("palette has %d entries, want 3", len(c.Palette))
	}
	if c.Palette["glass"].Family != "glass" {
		t.Fatalf("glass family = %q, want %q", c.Palette["glass"].Family, "glass")
	}
	if len(c.Ops) != 4 {
		t.Fatalf("ops has %d entries, want 4", len(c.Ops))
	}
}

func TestMaterialNamesAreSorted(t *testing.T) {
	got := parse(t).MaterialNames()
	want := []string{"glass", "gold", "granite"}
	if strings.Join(got, ",") != strings.Join(want, ",") {
		t.Fatalf("MaterialNames() = %v, want %v", got, want)
	}
}

func TestMaterialNamesByFamilyFiltersAndSorts(t *testing.T) {
	got := parse(t).MaterialNamesByFamily("glass")
	if len(got) != 1 || got[0] != "glass" {
		t.Fatalf("MaterialNamesByFamily(glass) = %v, want [glass]", got)
	}
}

func TestValidateAcceptsAWellFormedCommand(t *testing.T) {
	c := parse(t)
	errs := c.ValidateCommand(cmd(t, `{"op":"box","at":[0,0,0],"size":[10,20,10],"mat":"granite"}`))
	if len(errs) != 0 {
		t.Fatalf("ValidateCommand = %v, want no errors", errs)
	}
}

func TestValidateRejectsAnUnknownOp(t *testing.T) {
	c := parse(t)
	errs := c.ValidateCommand(cmd(t, `{"op":"teleport"}`))
	if len(errs) == 0 {
		t.Fatal("ValidateCommand accepted an unknown op")
	}
	if !strings.Contains(errs[0], "teleport") {
		t.Fatalf("error %q does not name the unknown op", errs[0])
	}
}

func TestValidateRejectsAnUnknownMaterialAndListsTheCount(t *testing.T) {
	c := parse(t)
	errs := c.ValidateCommand(cmd(t, `{"op":"box","at":[0,0,0],"size":[1,1,1],"mat":"unobtanium"}`))
	if len(errs) == 0 {
		t.Fatal("ValidateCommand accepted an unknown material")
	}
	joined := strings.Join(errs, " ")
	if !strings.Contains(joined, "unobtanium") {
		t.Fatalf("errors %v do not name the bad material", errs)
	}
}

func TestValidateRejectsAMissingField(t *testing.T) {
	c := parse(t)
	errs := c.ValidateCommand(cmd(t, `{"op":"box","at":[0,0,0],"mat":"granite"}`))
	if len(errs) == 0 {
		t.Fatal("ValidateCommand accepted a command missing `size`")
	}
	if !strings.Contains(strings.Join(errs, " "), "size") {
		t.Fatalf("errors %v do not name the missing field", errs)
	}
}

func TestValidateRejectsAWrongLengthVector(t *testing.T) {
	c := parse(t)
	errs := c.ValidateCommand(cmd(t, `{"op":"box","at":[0,0],"size":[1,1,1],"mat":"granite"}`))
	if len(errs) == 0 {
		t.Fatal("ValidateCommand accepted a 2-element int3")
	}
}

func TestValidateRejectsANonIntegerVectorComponent(t *testing.T) {
	c := parse(t)
	errs := c.ValidateCommand(cmd(t, `{"op":"box","at":[0,1.5,0],"size":[1,1,1],"mat":"granite"}`))
	if len(errs) == 0 {
		t.Fatal("ValidateCommand accepted a fractional coordinate")
	}
}

func TestValidateRejectsAZeroSizeComponent(t *testing.T) {
	c := parse(t)
	errs := c.ValidateCommand(cmd(t, `{"op":"box","at":[0,0,0],"size":[1,0,1],"mat":"granite"}`))
	if len(errs) == 0 {
		t.Fatal("ValidateCommand accepted a zero component in an int3+ field")
	}
}

func TestValidateRejectsANonPositiveRadius(t *testing.T) {
	c := parse(t)
	errs := c.ValidateCommand(cmd(t, `{"op":"sphere","at":[0,0,0],"r":0,"mat":"granite"}`))
	if len(errs) == 0 {
		t.Fatal("ValidateCommand accepted r=0 for an int+ field")
	}
}

func TestValidateAcceptsIdZeroButRejectsNegative(t *testing.T) {
	c := parse(t)
	if errs := c.ValidateCommand(cmd(t, `{"op":"remove","id":0}`)); len(errs) != 0 {
		t.Fatalf("ValidateCommand rejected id=0: %v", errs)
	}
	if errs := c.ValidateCommand(cmd(t, `{"op":"remove","id":-1}`)); len(errs) == 0 {
		t.Fatal("ValidateCommand accepted a negative id")
	}
}

func TestValidateAcceptsAnOpWithNoFields(t *testing.T) {
	c := parse(t)
	if errs := c.ValidateCommand(cmd(t, `{"op":"clear"}`)); len(errs) != 0 {
		t.Fatalf("ValidateCommand rejected clear: %v", errs)
	}
}

func TestValidateIgnoresExtraFieldsTheServerWouldIgnore(t *testing.T) {
	c := parse(t)
	errs := c.ValidateCommand(cmd(t, `{"op":"clear","note":"hello"}`))
	if len(errs) != 0 {
		t.Fatalf("ValidateCommand rejected an extra field the server ignores: %v", errs)
	}
}

func TestValidateBatchReportsTheOffendingIndex(t *testing.T) {
	c := parse(t)
	batch := []map[string]any{
		cmd(t, `{"op":"clear"}`),
		cmd(t, `{"op":"box","at":[0,0,0],"size":[1,1,1],"mat":"nope"}`),
	}
	bad := c.ValidateBatch(batch)
	if len(bad) != 1 {
		t.Fatalf("ValidateBatch found %d bad commands, want 1", len(bad))
	}
	if bad[0].Index != 1 {
		t.Fatalf("bad command index = %d, want 1", bad[0].Index)
	}
}

func TestCacheRoundTrips(t *testing.T) {
	path := filepath.Join(t.TempDir(), "world_info.json")
	c := parse(t)

	if err := c.Save(path); err != nil {
		t.Fatal(err)
	}
	got, err := Load(path)
	if err != nil {
		t.Fatal(err)
	}
	if got.Config.BlockLabel != c.Config.BlockLabel || len(got.Palette) != len(c.Palette) {
		t.Fatalf("round-tripped contract = %+v, want a match", got.Config)
	}
}

func TestLoadOnAMissingCacheReportsNotCached(t *testing.T) {
	_, err := Load(filepath.Join(t.TempDir(), "absent.json"))
	if err == nil {
		t.Fatal("Load on a missing cache returned no error")
	}
	if !errors.Is(err, ErrNotCached) {
		t.Fatalf("Load returned %v, want ErrNotCached", err)
	}
}
