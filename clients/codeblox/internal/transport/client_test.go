package transport

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/coder/websocket"
)

func TestPlainWSToARemoteHostIsRefused(t *testing.T) {
	err := CheckTransportSecurity("ws://build.example.com:7799", false)
	if err == nil {
		t.Fatal("CheckTransportSecurity accepted a token over plain ws:// to a remote host")
	}
	if !strings.Contains(err.Error(), "wss://") {
		t.Fatalf("error %q does not point the user at wss://", err)
	}
}

func TestPlainWSToLoopbackIsAllowed(t *testing.T) {
	for _, ep := range []string{
		"ws://127.0.0.1:7799",
		"ws://localhost:7799",
		"ws://[::1]:7799",
	} {
		if err := CheckTransportSecurity(ep, false); err != nil {
			t.Fatalf("CheckTransportSecurity(%q) = %v, want nil for loopback", ep, err)
		}
	}
}

func TestSecureWSToARemoteHostIsAllowed(t *testing.T) {
	if err := CheckTransportSecurity("wss://build.example.com", false); err != nil {
		t.Fatalf("CheckTransportSecurity on wss:// = %v, want nil", err)
	}
}

func TestInsecureOverrideAllowsPlainWSToARemoteHost(t *testing.T) {
	if err := CheckTransportSecurity("ws://build.example.com:7799", true); err != nil {
		t.Fatalf("CheckTransportSecurity with insecure=true = %v, want nil", err)
	}
}

func TestConnectSendsTheHelloAndReturnsTheWelcome(t *testing.T) {
	var gotHello struct {
		Type  string `json:"type"`
		Token string `json:"token"`
	}
	srv := helloServer(t, func(ctx context.Context, c *websocket.Conn, raw []byte) {
		_ = json.Unmarshal(raw, &gotHello)
		_ = c.Write(ctx, websocket.MessageText,
			[]byte(`{"type":"welcome","contract":{"ops":["box"]},"parts":[]}`))
	})

	d := Dialer{Endpoint: wsURL(srv.URL), Token: "tok-123"}
	conn, err := d.Connect(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	defer conn.Close()

	if gotHello.Type != "hello" {
		t.Fatalf("server saw first message type %q, want %q", gotHello.Type, "hello")
	}
	if gotHello.Token != "tok-123" {
		t.Fatalf("server saw token %q, want %q", gotHello.Token, "tok-123")
	}
	if conn.Welcome.Type != "welcome" {
		t.Fatalf("Welcome.Type = %q, want %q", conn.Welcome.Type, "welcome")
	}
	if len(conn.Welcome.Contract) == 0 {
		t.Fatal("Welcome.Contract is empty, want the server's contract payload")
	}
}

// The welcome frame carries the whole world, so it outgrows the library's 32 KiB
// default read limit at a few hundred parts. Past that every command — including
// the clear that would recover the world — used to fail at the handshake.
func TestConnectReadsAWelcomeLargerThanTheDefaultReadLimit(t *testing.T) {
	const defaultReadLimit = 32768

	welcome := bigWelcome(1000)
	if len(welcome) <= defaultReadLimit {
		t.Fatalf("test fixture is %d bytes, want more than the %d-byte default limit",
			len(welcome), defaultReadLimit)
	}

	srv := helloServer(t, func(ctx context.Context, c *websocket.Conn, _ []byte) {
		_ = c.Write(ctx, websocket.MessageText, welcome)
	})

	d := Dialer{Endpoint: wsURL(srv.URL), Token: "tok"}
	conn, err := d.Connect(context.Background())
	if err != nil {
		t.Fatalf("Connect() on a %d-byte welcome = %v, want nil", len(welcome), err)
	}
	defer conn.Close()

	var parts []json.RawMessage
	if err := json.Unmarshal(conn.Welcome.Parts, &parts); err != nil {
		t.Fatalf("parse Welcome.Parts: %v", err)
	}
	if len(parts) != 1000 {
		t.Fatalf("got %d parts, want 1000 — the frame was truncated", len(parts))
	}
}

// bigWelcome builds a welcome frame shaped like the server's, with n parts.
func bigWelcome(n int) []byte {
	parts := make([]map[string]any, n)
	for i := range parts {
		parts[i] = map[string]any{
			"id": i, "kind": "box",
			"center": []int{i, i + 1, i + 2}, "size": []int{18, 4, 56},
			"material": "silver",
		}
	}
	frame, err := json.Marshal(map[string]any{
		"type":     "welcome",
		"contract": map[string]any{"ops": []string{"box"}},
		"parts":    parts,
	})
	if err != nil {
		panic(err)
	}
	return frame
}

func TestConnectSurfacesAnUnauthorizedRejection(t *testing.T) {
	srv := helloServer(t, func(ctx context.Context, c *websocket.Conn, _ []byte) {
		_ = c.Write(ctx, websocket.MessageText, []byte(`{"type":"error","message":"unauthorized"}`))
		_ = c.Close(websocket.StatusCode(4001), "unauthorized")
	})

	d := Dialer{Endpoint: wsURL(srv.URL), Token: "bad"}
	_, err := d.Connect(context.Background())
	if err == nil {
		t.Fatal("Connect() succeeded against a rejecting server, want an error")
	}
	if !strings.Contains(err.Error(), "unauthorized") {
		t.Fatalf("error %q does not carry the server's rejection message", err)
	}
}

func TestConnectRefusesAnInvalidEndpointBeforeDialling(t *testing.T) {
	d := Dialer{Endpoint: "https://example.com", Token: "tok"}
	if _, err := d.Connect(context.Background()); err == nil {
		t.Fatal("Connect() accepted an https:// endpoint, want an error")
	}
}

// helloServer runs a websocket server that hands the first client message to fn.
func helloServer(t *testing.T, fn func(context.Context, *websocket.Conn, []byte)) *httptest.Server {
	t.Helper()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		c, err := websocket.Accept(w, r, nil)
		if err != nil {
			return
		}
		defer c.CloseNow()
		ctx, cancel := context.WithTimeout(r.Context(), 5*time.Second)
		defer cancel()
		_, raw, err := c.Read(ctx)
		if err != nil {
			return
		}
		fn(ctx, c, raw)
		// Hold the connection open until the client hangs up, so the client
		// always gets its frame; returning immediately would race the close.
		for {
			if _, _, err := c.Read(ctx); err != nil {
				return
			}
		}
	}))
	t.Cleanup(srv.Close)
	return srv
}

func wsURL(httpURL string) string {
	return "ws" + strings.TrimPrefix(httpURL, "http")
}
