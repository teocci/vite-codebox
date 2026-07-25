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

// batchServer greets a client, then replies to a `commands` frame with the given
// frames in order.
func batchServer(t *testing.T, replies ...string) *httptest.Server {
	t.Helper()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		c, err := websocket.Accept(w, r, nil)
		if err != nil {
			return
		}
		defer c.CloseNow()
		ctx, cancel := context.WithTimeout(r.Context(), 5*time.Second)
		defer cancel()

		if _, _, err := c.Read(ctx); err != nil { // hello
			return
		}
		if err := c.Write(ctx, websocket.MessageText,
			[]byte(`{"type":"welcome","contract":{},"parts":[]}`)); err != nil {
			return
		}
		if _, _, err := c.Read(ctx); err != nil { // commands
			return
		}
		for _, frame := range replies {
			if err := c.Write(ctx, websocket.MessageText, []byte(frame)); err != nil {
				return
			}
		}
		for {
			if _, _, err := c.Read(ctx); err != nil {
				return
			}
		}
	}))
	t.Cleanup(srv.Close)
	return srv
}

func connect(t *testing.T, srv *httptest.Server) *Conn {
	t.Helper()
	conn, err := Dialer{Endpoint: wsURL(srv.URL), Token: "tok"}.Connect(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { conn.Close() })
	return conn
}

func TestSendBatchReadsPastTheBroadcastDiffToTheAck(t *testing.T) {
	// The real server broadcasts the diff to every client first, then acks the
	// sender. A client that took the first frame as its ack would misreport.
	srv := batchServer(t,
		`{"type":"diff","added":[{"id":7}],"removed":[],"cleared":false}`,
		`{"type":"ack","addedIds":[7],"removed":[],"cleared":false,"errors":[]}`,
	)
	conn := connect(t, srv)

	ack, err := conn.SendBatch(context.Background(), []any{
		map[string]any{"op": "box", "at": []int{0, 0, 0}, "size": []int{1, 1, 1}, "mat": "granite"},
	})
	if err != nil {
		t.Fatal(err)
	}
	if len(ack.AddedIDs) != 1 || ack.AddedIDs[0] != 7 {
		t.Fatalf("ack.AddedIDs = %v, want [7]", ack.AddedIDs)
	}
}

func TestSendBatchSendsACommandsFrameCarryingTheBatch(t *testing.T) {
	var seen struct {
		Type  string           `json:"type"`
		Batch []map[string]any `json:"batch"`
	}
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		c, _ := websocket.Accept(w, r, nil)
		defer c.CloseNow()
		ctx, cancel := context.WithTimeout(r.Context(), 5*time.Second)
		defer cancel()
		_, _, _ = c.Read(ctx)
		_ = c.Write(ctx, websocket.MessageText, []byte(`{"type":"welcome"}`))
		_, raw, err := c.Read(ctx)
		if err != nil {
			return
		}
		_ = json.Unmarshal(raw, &seen)
		_ = c.Write(ctx, websocket.MessageText, []byte(`{"type":"ack","addedIds":[]}`))
		for {
			if _, _, err := c.Read(ctx); err != nil {
				return
			}
		}
	}))
	t.Cleanup(srv.Close)

	conn := connect(t, srv)
	if _, err := conn.SendBatch(context.Background(), []any{
		map[string]any{"op": "clear"},
	}); err != nil {
		t.Fatal(err)
	}

	if seen.Type != "commands" {
		t.Fatalf("server saw frame type %q, want %q", seen.Type, "commands")
	}
	if len(seen.Batch) != 1 || seen.Batch[0]["op"] != "clear" {
		t.Fatalf("server saw batch %v, want one clear command", seen.Batch)
	}
}

func TestSendBatchSurfacesServerSideCommandErrors(t *testing.T) {
	srv := batchServer(t,
		`{"type":"ack","addedIds":[],"removed":[],"cleared":false,
		  "errors":[{"cmd":{"op":"box"},"errors":["part is out of world bounds"]}]}`,
	)
	conn := connect(t, srv)

	ack, err := conn.SendBatch(context.Background(), []any{map[string]any{"op": "box"}})
	if err != nil {
		t.Fatal(err)
	}
	if len(ack.Errors) != 1 {
		t.Fatalf("ack.Errors = %v, want one entry", ack.Errors)
	}
	if !strings.Contains(strings.Join(ack.Errors[0].Errors, " "), "out of world bounds") {
		t.Fatalf("ack error %v does not carry the server's message", ack.Errors[0])
	}
}

func TestSendBatchReportsAClearedWorld(t *testing.T) {
	srv := batchServer(t, `{"type":"ack","addedIds":[],"removed":[],"cleared":true,"errors":[]}`)
	conn := connect(t, srv)

	ack, err := conn.SendBatch(context.Background(), []any{map[string]any{"op": "clear"}})
	if err != nil {
		t.Fatal(err)
	}
	if !ack.Cleared {
		t.Fatal("ack.Cleared = false, want true")
	}
}
