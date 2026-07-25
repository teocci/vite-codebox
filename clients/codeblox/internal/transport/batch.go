package transport

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/coder/websocket"
)

// batchTimeout bounds one command round trip.
const batchTimeout = 30 * time.Second

// CommandError is one command the server refused, with its reasons.
type CommandError struct {
	Cmd    json.RawMessage `json:"cmd"`
	Errors []string        `json:"errors"`
}

// Ack is the server's reply to a command batch, addressed to the sender only.
type Ack struct {
	Type     string         `json:"type"`
	AddedIDs []int          `json:"addedIds"`
	Removed  []int          `json:"removed"`
	Cleared  bool           `json:"cleared"`
	Errors   []CommandError `json:"errors"`
}

// frameType peeks at a frame's discriminator without committing to a shape.
type frameType struct {
	Type    string `json:"type"`
	Message string `json:"message"`
}

// SendBatch sends a command batch and returns the server's ack.
//
// The server broadcasts the resulting diff to every subscriber *before* acking
// the sender, so this reads past any non-ack frame rather than treating the
// first reply as the answer.
func (c *Conn) SendBatch(ctx context.Context, batch []any) (Ack, error) {
	ctx, cancel := context.WithTimeout(ctx, batchTimeout)
	defer cancel()

	payload, err := json.Marshal(map[string]any{"type": "commands", "batch": batch})
	if err != nil {
		return Ack{}, fmt.Errorf("encode command batch: %w", err)
	}
	if err := c.ws.Write(ctx, websocket.MessageText, payload); err != nil {
		return Ack{}, fmt.Errorf("send command batch: %w", err)
	}
	return c.awaitAck(ctx)
}

// awaitAck reads frames until the sender's ack arrives.
func (c *Conn) awaitAck(ctx context.Context) (Ack, error) {
	for {
		_, raw, err := c.ws.Read(ctx)
		if err != nil {
			return Ack{}, fmt.Errorf("read ack: %w", rejectionReason(err))
		}

		var probe frameType
		if err := json.Unmarshal(raw, &probe); err != nil {
			return Ack{}, fmt.Errorf("parse server frame: %w", err)
		}

		switch probe.Type {
		case "ack":
			var ack Ack
			if err := json.Unmarshal(raw, &ack); err != nil {
				return Ack{}, fmt.Errorf("parse ack: %w", err)
			}
			return ack, nil
		case "error":
			return Ack{}, fmt.Errorf("server error: %s", probe.Message)
		default:
			// diff broadcasts and anything else the server adds later: skip.
			continue
		}
	}
}
