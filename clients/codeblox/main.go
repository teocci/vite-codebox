// Command codeblox is the operator-PC client for a codeblox build server.
//
// It is the agent's hands: authenticate once, then drive the world over the
// authoritative ws server. The binary is self-contained — no Node, no Python.
package main

import (
	"context"
	"os"
	"os/signal"

	"github.com/teocci/vite-codebox/clients/codeblox/internal/command"
	"github.com/teocci/vite-codebox/clients/codeblox/internal/config"
)

func main() {
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt)
	defer stop()

	if err := run(ctx); err != nil {
		// Failures always go to stderr, rendered as a JSON envelope when the
		// caller asked for one. The exit code is the contract a script branches
		// on; see internal/command/exit.go for the taxonomy.
		command.RenderFailure(os.Stderr, err, command.WantsJSON(os.Args[1:]))
		os.Exit(command.ExitCodeFor(err))
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
