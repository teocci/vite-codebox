// Package transport dials the codeblox ws server and performs the hello handshake.
//
// Wire protocol (server/createServer.js):
//
//	client -> {"type":"hello","token":"…"}
//	server -> {"type":"welcome","contract":{…},"parts":[…]}
//	server -> {"type":"error","message":"unauthorized"}  then close 4001
package transport

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net"
	"net/url"
	"time"

	"github.com/coder/websocket"

	"github.com/teocci/vite-codebox/clients/codeblox/internal/config"
)

// handshakeTimeout bounds the hello/welcome exchange so a silent server does not
// hang the CLI indefinitely.
const handshakeTimeout = 10 * time.Second

// Welcome is the server's post-handshake payload. Contract and Parts stay raw:
// the CLI is schema-driven and must not compile the server's vocabulary in.
type Welcome struct {
	Type     string          `json:"type"`
	Contract json.RawMessage `json:"contract"`
	Parts    json.RawMessage `json:"parts"`
}

// serverError is the rejection frame the server sends before closing.
type serverError struct {
	Type    string `json:"type"`
	Message string `json:"message"`
}

// Dialer opens an authenticated connection to a codeblox server.
type Dialer struct {
	Endpoint string
	Token    string
	// Insecure permits sending the token over plain ws:// to a non-loopback
	// host. Off by default — see CheckTransportSecurity.
	Insecure bool
}

// Conn is a live, authenticated connection plus the welcome it was greeted with.
type Conn struct {
	Welcome Welcome

	ws *websocket.Conn
}

// Contract returns the server's published world_info, still raw so the CLI stays
// schema-driven.
func (c *Conn) Contract() json.RawMessage { return c.Welcome.Contract }

// Close tears the connection down.
func (c *Conn) Close() error {
	if c.ws == nil {
		return nil
	}
	return c.ws.Close(websocket.StatusNormalClosure, "")
}

// CheckTransportSecurity refuses to put a bearer token on an unencrypted link to
// anywhere but the local machine. Loopback is exempt because the traffic never
// reaches a network interface.
func CheckTransportSecurity(endpoint string, insecure bool) error {
	if err := config.ValidateEndpoint(endpoint); err != nil {
		return err
	}
	u, err := url.Parse(endpoint)
	if err != nil {
		return fmt.Errorf("parse endpoint %q: %w", endpoint, err)
	}
	if u.Scheme == "wss" || insecure || isLoopback(u.Hostname()) {
		return nil
	}
	return fmt.Errorf(
		"refusing to send the token to %s over plain ws:// — use wss://, "+
			"or pass --insecure if you accept an unencrypted credential on the wire",
		u.Host)
}

// isLoopback reports whether host resolves to the local machine without leaving it.
func isLoopback(host string) bool {
	if host == "localhost" {
		return true
	}
	ip := net.ParseIP(host)
	return ip != nil && ip.IsLoopback()
}

// Connect dials the server, sends the hello, and reads the welcome. It returns an
// error carrying the server's message when the handshake is rejected.
func (d Dialer) Connect(ctx context.Context) (*Conn, error) {
	if err := CheckTransportSecurity(d.Endpoint, d.Insecure); err != nil {
		return nil, err
	}

	ctx, cancel := context.WithTimeout(ctx, handshakeTimeout)
	defer cancel()

	ws, _, err := websocket.Dial(ctx, d.Endpoint, nil)
	if err != nil {
		return nil, fmt.Errorf("connect to %s: %w", d.Endpoint, err)
	}

	// The welcome frame carries the whole world snapshot, so its size grows with
	// the build — roughly 80 bytes per part on top of a ~5 KB contract. The
	// library's 32 KiB default read limit would therefore cap the world at ~330
	// parts, after which *every* command fails at the handshake, including the
	// clear that would recover it. The server is trusted and local, so the frame
	// is not a hostile-input surface: lift the limit entirely.
	ws.SetReadLimit(-1)

	welcome, err := handshake(ctx, ws, d.Token)
	if err != nil {
		ws.CloseNow()
		return nil, err
	}
	return &Conn{Welcome: welcome, ws: ws}, nil
}

// handshake performs the hello/welcome exchange on an already-dialled socket.
func handshake(ctx context.Context, ws *websocket.Conn, token string) (Welcome, error) {
	hello, err := json.Marshal(map[string]string{"type": "hello", "token": token})
	if err != nil {
		return Welcome{}, fmt.Errorf("encode hello: %w", err)
	}
	if err := ws.Write(ctx, websocket.MessageText, hello); err != nil {
		return Welcome{}, fmt.Errorf("send hello: %w", err)
	}

	_, raw, err := ws.Read(ctx)
	if err != nil {
		return Welcome{}, fmt.Errorf("read welcome: %w", rejectionReason(err))
	}

	var welcome Welcome
	if err := json.Unmarshal(raw, &welcome); err != nil {
		return Welcome{}, fmt.Errorf("parse welcome: %w", err)
	}
	if welcome.Type == "welcome" {
		return welcome, nil
	}

	var srvErr serverError
	if err := json.Unmarshal(raw, &srvErr); err == nil && srvErr.Message != "" {
		return Welcome{}, fmt.Errorf("server rejected the connection: %s", srvErr.Message)
	}
	return Welcome{}, fmt.Errorf("unexpected first frame of type %q, want %q", welcome.Type, "welcome")
}

// ErrUnauthorized means the server closed with 4001: it answered, and refused
// this token. Exported as a sentinel so the caller can tell "your credential is
// wrong" (re-authenticate) from "the server is unreachable" (retry) without
// matching the message text.
var ErrUnauthorized = errors.New("unauthorized — the server rejected this token")

// rejectionReason turns the server's close code into something actionable. The
// server closes 4001 when the token does not match.
func rejectionReason(err error) error {
	var closeErr websocket.CloseError
	if errors.As(err, &closeErr) && closeErr.Code == 4001 {
		return ErrUnauthorized
	}
	return err
}
