// Package config resolves the codeblox CLI's non-secret settings and the
// per-user base directory they live in.
//
// Every filename and CODEBLOX_* environment-variable name in the CLI is declared
// here, so no other package hardcodes a path. Secrets never appear in this
// package's files — the token lives in the credential store (see internal/creds).
package config

import (
	"encoding/json"
	"errors"
	"fmt"
	"net/url"
	"os"
	"path/filepath"
)

// Names of the files and directories the CLI owns, and of the environment
// variables that override them. Centralised per the file-locations rule.
const (
	// DirName is the per-user base dir, resolved once by Env.BaseDir.
	DirName = ".codeblox"
	// FileName holds non-secret settings only.
	FileName = "config.json"
	// AuthFileName is the credential store's file backend. It may contain a
	// secret, so it is created 0600 and is never this package's concern.
	AuthFileName = "auth.json"

	EnvConfig   = "CODEBLOX_CONFIG"
	EnvEndpoint = "CODEBLOX_ENDPOINT"
	EnvToken    = "CODEBLOX_TOKEN"
	EnvBackend  = "CODEBLOX_AUTH_BACKEND"

	// DefaultEndpoint matches the ws server's default bind in config.yaml
	// (127.0.0.1:7799). It is the client's own default, overridable at every
	// level — the CLI cannot read the server's config.yaml across a network.
	DefaultEndpoint = "ws://127.0.0.1:7799"
)

// Config is the non-secret settings file. Adding a credential field here is a bug.
type Config struct {
	Endpoint string `json:"endpoint,omitempty"`
}

// Env is the injected view of the host: home dir, working dir, and environment.
// Injecting these keeps path resolution testable and keeps the CLI from ever
// resolving user data relative to the executable.
type Env struct {
	Home   string
	Cwd    string
	Getenv func(string) string
}

// OSEnv binds Env to the real host.
func OSEnv() (Env, error) {
	home, err := os.UserHomeDir()
	if err != nil {
		return Env{}, fmt.Errorf("resolve home dir: %w", err)
	}
	cwd, err := os.Getwd()
	if err != nil {
		return Env{}, fmt.Errorf("resolve working dir: %w", err)
	}
	return Env{Home: home, Cwd: cwd, Getenv: os.Getenv}, nil
}

// BaseDir is the single per-user base dir. It never varies with how the binary
// was built or where it was invoked from.
func (e Env) BaseDir() string {
	return filepath.Join(e.Home, DirName)
}

// AuthPath is where the credential store's file backend lives.
func (e Env) AuthPath() string {
	return filepath.Join(e.BaseDir(), AuthFileName)
}

// ConfigPath resolves the settings file by the documented precedence:
// --config flag, then $CODEBLOX_CONFIG, then a project-local config in the
// working dir, then the base dir.
func (e Env) ConfigPath(flagPath string) string {
	if flagPath != "" {
		return flagPath
	}
	if v := e.env(EnvConfig); v != "" {
		return v
	}
	local := filepath.Join(e.Cwd, FileName)
	if _, err := os.Stat(local); err == nil {
		return local
	}
	return filepath.Join(e.BaseDir(), FileName)
}

// Load reads the settings file. A missing file is not an error — it yields the
// zero Config, which every caller treats as "fall back to defaults".
func (e Env) Load(flagPath string) (Config, error) {
	path := e.ConfigPath(flagPath)
	raw, err := os.ReadFile(path)
	if errors.Is(err, os.ErrNotExist) {
		return Config{}, nil
	}
	if err != nil {
		return Config{}, fmt.Errorf("read config %s: %w", path, err)
	}
	var cfg Config
	if err := json.Unmarshal(raw, &cfg); err != nil {
		return Config{}, fmt.Errorf("parse config %s: %w", path, err)
	}
	return cfg, nil
}

// Save writes the settings file, creating the base dir if needed.
func (c Config) Save(path string) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		return fmt.Errorf("create config dir: %w", err)
	}
	raw, err := json.MarshalIndent(c, "", "  ")
	if err != nil {
		return fmt.Errorf("encode config: %w", err)
	}
	if err := os.WriteFile(path, append(raw, '\n'), 0o600); err != nil {
		return fmt.Errorf("write config %s: %w", path, err)
	}
	return nil
}

// Endpoint resolves the server URL: --endpoint flag, then $CODEBLOX_ENDPOINT,
// then the settings file, then DefaultEndpoint. The result is validated so a
// malformed endpoint fails here rather than deep inside the dialer.
func (e Env) Endpoint(flagVal, flagPath string) (string, error) {
	raw := flagVal
	if raw == "" {
		raw = e.env(EnvEndpoint)
	}
	if raw == "" {
		cfg, err := e.Load(flagPath)
		if err != nil {
			return "", err
		}
		raw = cfg.Endpoint
	}
	if raw == "" {
		raw = DefaultEndpoint
	}
	if err := ValidateEndpoint(raw); err != nil {
		return "", err
	}
	return raw, nil
}

// ValidateEndpoint accepts only ws:// and wss:// URLs carrying a host.
func ValidateEndpoint(raw string) error {
	u, err := url.Parse(raw)
	if err != nil {
		return fmt.Errorf("parse endpoint %q: %w", raw, err)
	}
	if u.Scheme != "ws" && u.Scheme != "wss" {
		return fmt.Errorf("endpoint %q: scheme must be ws:// or wss://, got %q", raw, u.Scheme)
	}
	if u.Host == "" {
		return fmt.Errorf("endpoint %q: missing host", raw)
	}
	return nil
}

func (e Env) env(key string) string {
	if e.Getenv == nil {
		return ""
	}
	return e.Getenv(key)
}
