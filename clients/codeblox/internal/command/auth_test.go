package command

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"os"
	"strings"
	"testing"

	"github.com/teocci/vite-codebox/clients/codeblox/internal/config"
	"github.com/teocci/vite-codebox/clients/codeblox/internal/creds"
	"github.com/teocci/vite-codebox/clients/codeblox/internal/transport"
)

// app wires an App onto temp dirs, a file credential store, and buffers.
func app(t *testing.T, stdin string, vars map[string]string) (*App, *bytes.Buffer) {
	t.Helper()
	e := config.Env{
		Home:   t.TempDir(),
		Cwd:    t.TempDir(),
		Getenv: func(k string) string { return vars[k] },
	}
	store, err := creds.Open(e, "file")
	if err != nil {
		t.Fatal(err)
	}
	out := &bytes.Buffer{}
	return &App{
		Env:    e,
		Store:  store,
		Stdin:  strings.NewReader(stdin),
		Stdout: out,
		Stderr: &bytes.Buffer{},
	}, out
}

// readFile is a test-only helper for asserting on file contents.
func readFile(path string) (string, error) {
	raw, err := os.ReadFile(path)
	return string(raw), err
}

func TestLoginWithTokenReadsStdinAndStoresIt(t *testing.T) {
	a, out := app(t, "tok-from-stdin\n", nil)

	if err := a.Login(LoginOptions{FromStdin: true}); err != nil {
		t.Fatal(err)
	}

	stored, err := a.Store.Get()
	if err != nil {
		t.Fatal(err)
	}
	if stored != "tok-from-stdin" {
		t.Fatalf("stored token = %q, want the stdin value with whitespace trimmed", stored)
	}
	if strings.Contains(out.String(), "tok-from-stdin") {
		t.Fatalf("login output leaked the raw token: %q", out.String())
	}
}

func TestLoginRejectsAnEmptyToken(t *testing.T) {
	a, _ := app(t, "   \n", nil)
	if err := a.Login(LoginOptions{FromStdin: true}); err == nil {
		t.Fatal("Login() accepted an empty token, want an error")
	}
}

func TestLoginRecordsANonDefaultEndpointInTheConfigFile(t *testing.T) {
	a, _ := app(t, "tok\n", nil)

	if err := a.Login(LoginOptions{FromStdin: true, Endpoint: "wss://build.example.com"}); err != nil {
		t.Fatal(err)
	}

	cfg, err := a.Env.Load("")
	if err != nil {
		t.Fatal(err)
	}
	if cfg.Endpoint != "wss://build.example.com" {
		t.Fatalf("saved endpoint = %q, want the login endpoint", cfg.Endpoint)
	}
}

func TestLoginNeverWritesTheTokenToTheConfigFile(t *testing.T) {
	a, _ := app(t, "super-secret-token\n", nil)
	if err := a.Login(LoginOptions{FromStdin: true, Endpoint: "wss://build.example.com"}); err != nil {
		t.Fatal(err)
	}

	raw, err := readFile(a.Env.ConfigPath(""))
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(raw, "super-secret-token") {
		t.Fatalf("config file contains the token: %s", raw)
	}
}

func TestLogoutRemovesTheStoredCredential(t *testing.T) {
	a, _ := app(t, "tok\n", nil)
	if err := a.Login(LoginOptions{FromStdin: true}); err != nil {
		t.Fatal(err)
	}
	if err := a.Logout(); err != nil {
		t.Fatal(err)
	}
	if _, err := a.Store.Get(); !errors.Is(err, creds.ErrNoCredential) {
		t.Fatalf("credential survived logout: %v", err)
	}
}

func TestLogoutWithNothingStoredIsNotAnError(t *testing.T) {
	a, out := app(t, "", nil)
	if err := a.Logout(); err != nil {
		t.Fatalf("Logout() with no credential = %v, want nil", err)
	}
	if !strings.Contains(out.String(), "no stored credential") {
		t.Fatalf("output %q does not say there was nothing to remove", out.String())
	}
}

func TestListMasksTheToken(t *testing.T) {
	a, out := app(t, "abcdefghijklmnop\n", nil)
	if err := a.Login(LoginOptions{FromStdin: true}); err != nil {
		t.Fatal(err)
	}
	out.Reset()

	if err := a.List(false); err != nil {
		t.Fatal(err)
	}
	if strings.Contains(out.String(), "abcdefghijklmnop") {
		t.Fatalf("list leaked the raw token: %q", out.String())
	}
	if !strings.Contains(out.String(), creds.Mask("abcdefghijklmnop")) {
		t.Fatalf("list output %q does not contain the masked token", out.String())
	}
}

func TestListAsJSONIsParseableAndMasked(t *testing.T) {
	a, out := app(t, "abcdefghijklmnop\n", nil)
	if err := a.Login(LoginOptions{FromStdin: true}); err != nil {
		t.Fatal(err)
	}
	out.Reset()

	if err := a.List(true); err != nil {
		t.Fatal(err)
	}
	var got map[string]any
	if err := json.Unmarshal(out.Bytes(), &got); err != nil {
		t.Fatalf("list --json emitted unparseable output %q: %v", out.String(), err)
	}
	if got["token"] != creds.Mask("abcdefghijklmnop") {
		t.Fatalf("json token field = %v, want the masked token", got["token"])
	}
	if got["backend"] != "file" {
		t.Fatalf("json backend field = %v, want %q", got["backend"], "file")
	}
}

func TestStatusWithoutACredentialSaysSoAndFails(t *testing.T) {
	a, out := app(t, "", nil)
	err := a.Status(context.Background(), StatusOptions{})
	if err == nil {
		t.Fatal("Status() with no credential succeeded, want an error")
	}
	if !strings.Contains(out.String()+err.Error(), "auth login") {
		t.Fatalf("output %q / error %q does not point the user at `auth login`", out.String(), err)
	}
}

func TestStatusReportsAReachableServer(t *testing.T) {
	a, out := app(t, "tok\n", nil)
	if err := a.Login(LoginOptions{FromStdin: true}); err != nil {
		t.Fatal(err)
	}
	out.Reset()
	a.Dial = func(context.Context, transport.Dialer) (Session, error) {
		return &transport.Conn{Welcome: transport.Welcome{
			Type:     "welcome",
			Contract: json.RawMessage(`{"ops":["box"]}`),
		}}, nil
	}

	if err := a.Status(context.Background(), StatusOptions{}); err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(out.String(), "connected") {
		t.Fatalf("status output %q does not report a successful connection", out.String())
	}
}

func TestStatusSurfacesARejectedToken(t *testing.T) {
	a, _ := app(t, "tok\n", nil)
	if err := a.Login(LoginOptions{FromStdin: true}); err != nil {
		t.Fatal(err)
	}
	a.Dial = func(context.Context, transport.Dialer) (Session, error) {
		return nil, errors.New("unauthorized — the server rejected this token")
	}

	err := a.Status(context.Background(), StatusOptions{})
	if err == nil {
		t.Fatal("Status() succeeded against a rejecting server, want an error")
	}
	if !strings.Contains(err.Error(), "unauthorized") {
		t.Fatalf("error %q does not carry the rejection", err)
	}
}

func TestStatusAsJSONNeverCarriesTheRawToken(t *testing.T) {
	a, out := app(t, "abcdefghijklmnop\n", nil)
	if err := a.Login(LoginOptions{FromStdin: true}); err != nil {
		t.Fatal(err)
	}
	out.Reset()
	a.Dial = func(context.Context, transport.Dialer) (Session, error) {
		return &transport.Conn{Welcome: transport.Welcome{Type: "welcome"}}, nil
	}

	if err := a.Status(context.Background(), StatusOptions{JSON: true}); err != nil {
		t.Fatal(err)
	}
	if strings.Contains(out.String(), "abcdefghijklmnop") {
		t.Fatalf("status --json leaked the raw token: %q", out.String())
	}
	var got map[string]any
	if err := json.Unmarshal(out.Bytes(), &got); err != nil {
		t.Fatalf("status --json emitted unparseable output %q: %v", out.String(), err)
	}
	if got["connected"] != true {
		t.Fatalf("json connected field = %v, want true", got["connected"])
	}
}

func TestStatusRefusesToSendTheTokenOverPlainWSToARemoteHost(t *testing.T) {
	a, _ := app(t, "tok\n", map[string]string{config.EnvEndpoint: "ws://build.example.com:7799"})
	if err := a.Login(LoginOptions{FromStdin: true}); err != nil {
		t.Fatal(err)
	}
	// Dial is left nil: the guard must fire before any connection is attempted.
	err := a.Status(context.Background(), StatusOptions{})
	if err == nil {
		t.Fatal("Status() proceeded over plain ws:// to a remote host, want a refusal")
	}
	if !strings.Contains(err.Error(), "wss://") {
		t.Fatalf("error %q does not point the user at wss://", err)
	}
}
