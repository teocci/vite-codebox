// Command codeblox is the operator-PC client for a codeblox build server.
//
// It is the agent's hands: authenticate once, then drive the world over the
// authoritative ws server. The binary is self-contained — no Node, no Python.
package main

import (
	"context"
	"fmt"
	"os"
	"os/signal"

	"github.com/teocci/vite-codebox/clients/codeblox/internal/command"
	"github.com/teocci/vite-codebox/clients/codeblox/internal/config"
)

func main() {
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt)
	defer stop()

	if err := run(ctx); err != nil {
		fmt.Fprintf(os.Stderr, "codeblox: %v\n", err)
		os.Exit(1)
	}
}

func run(ctx context.Context) error {
	env, err := config.OSEnv()
	if err != nil {
		return err
	}
	return command.Dispatch(ctx, command.Deps{
		Env:    env,
		Stdin:  os.Stdin,
		Stdout: os.Stdout,
		Stderr: os.Stderr,
	}, os.Args[1:])
}
