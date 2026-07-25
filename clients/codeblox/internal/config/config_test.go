package config

import (
	"os"
	"path/filepath"
	"testing"
)

// env builds an Env with no environment variables set, rooted at t.TempDir().
func env(t *testing.T, vars map[string]string) Env {
	t.Helper()
	home := t.TempDir()
	cwd := t.TempDir()
	return Env{
		Home: home,
		Cwd:  cwd,
		Getenv: func(k string) string {
			return vars[k]
		},
	}
}

func TestBaseDirIsUnderHome(t *testing.T) {
	e := env(t, nil)
	want := filepath.Join(e.Home, DirName)
	if got := e.BaseDir(); got != want {
		t.Fatalf("BaseDir() = %q, want %q", got, want)
	}
}

func TestConfigPathPrefersFlagOverEverything(t *testing.T) {
	e := env(t, map[string]string{EnvConfig: "/from/env.json"})
	if got := e.ConfigPath("/from/flag.json"); got != "/from/flag.json" {
		t.Fatalf("ConfigPath() = %q, want the flag value", got)
	}
}

func TestConfigPathPrefersEnvOverProjectLocal(t *testing.T) {
	e := env(t, map[string]string{EnvConfig: "/from/env.json"})
	// a project-local config exists but the env var must still win
	local := filepath.Join(e.Cwd, FileName)
	if err := os.WriteFile(local, []byte(`{}`), 0o600); err != nil {
		t.Fatal(err)
	}
	if got := e.ConfigPath(""); got != "/from/env.json" {
		t.Fatalf("ConfigPath() = %q, want the env value", got)
	}
}

func TestConfigPathPrefersProjectLocalOverBaseDir(t *testing.T) {
	e := env(t, nil)
	local := filepath.Join(e.Cwd, FileName)
	if err := os.WriteFile(local, []byte(`{}`), 0o600); err != nil {
		t.Fatal(err)
	}
	if got := e.ConfigPath(""); got != local {
		t.Fatalf("ConfigPath() = %q, want the project-local path %q", got, local)
	}
}

func TestConfigPathFallsBackToBaseDir(t *testing.T) {
	e := env(t, nil)
	want := filepath.Join(e.Home, DirName, FileName)
	if got := e.ConfigPath(""); got != want {
		t.Fatalf("ConfigPath() = %q, want %q", got, want)
	}
}

func TestEndpointFallsBackToDefault(t *testing.T) {
	e := env(t, nil)
	got, err := e.Endpoint("", "")
	if err != nil {
		t.Fatal(err)
	}
	if got != DefaultEndpoint {
		t.Fatalf("Endpoint() = %q, want the default %q", got, DefaultEndpoint)
	}
}

func TestEndpointPrefersFlagOverEnv(t *testing.T) {
	e := env(t, map[string]string{EnvEndpoint: "ws://from-env:1"})
	got, err := e.Endpoint("ws://from-flag:2", "")
	if err != nil {
		t.Fatal(err)
	}
	if got != "ws://from-flag:2" {
		t.Fatalf("Endpoint() = %q, want the flag value", got)
	}
}

func TestEndpointPrefersEnvOverFile(t *testing.T) {
	e := env(t, map[string]string{EnvEndpoint: "ws://from-env:1"})
	writeConfig(t, e, `{"endpoint":"ws://from-file:3"}`)
	got, err := e.Endpoint("", "")
	if err != nil {
		t.Fatal(err)
	}
	if got != "ws://from-env:1" {
		t.Fatalf("Endpoint() = %q, want the env value", got)
	}
}

func TestEndpointReadsTheConfigFile(t *testing.T) {
	e := env(t, nil)
	writeConfig(t, e, `{"endpoint":"ws://from-file:3"}`)
	got, err := e.Endpoint("", "")
	if err != nil {
		t.Fatal(err)
	}
	if got != "ws://from-file:3" {
		t.Fatalf("Endpoint() = %q, want the file value", got)
	}
}

func TestEndpointRejectsANonWebSocketScheme(t *testing.T) {
	e := env(t, nil)
	if _, err := e.Endpoint("https://example.com", ""); err == nil {
		t.Fatal("Endpoint() accepted an https:// endpoint, want an error")
	}
}

func TestLoadReportsMalformedConfig(t *testing.T) {
	e := env(t, nil)
	writeConfig(t, e, `{not json`)
	if _, err := e.Load(""); err == nil {
		t.Fatal("Load() accepted malformed JSON, want an error")
	}
}

func TestLoadOnAMissingFileReturnsAnEmptyConfig(t *testing.T) {
	e := env(t, nil)
	cfg, err := e.Load("")
	if err != nil {
		t.Fatalf("Load() on a missing file returned %v, want no error", err)
	}
	if cfg.Endpoint != "" {
		t.Fatalf("Load() = %+v, want a zero Config", cfg)
	}
}

func TestSaveRoundTripsAndCreatesTheBaseDir(t *testing.T) {
	e := env(t, nil)
	path := e.ConfigPath("")
	if err := (Config{Endpoint: "ws://saved:9"}).Save(path); err != nil {
		t.Fatal(err)
	}
	cfg, err := e.Load("")
	if err != nil {
		t.Fatal(err)
	}
	if cfg.Endpoint != "ws://saved:9" {
		t.Fatalf("round-tripped endpoint = %q, want %q", cfg.Endpoint, "ws://saved:9")
	}
}

// writeConfig plants a config file at the base-dir location.
func writeConfig(t *testing.T, e Env, body string) {
	t.Helper()
	path := filepath.Join(e.Home, DirName, FileName)
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte(body), 0o600); err != nil {
		t.Fatal(err)
	}
}
