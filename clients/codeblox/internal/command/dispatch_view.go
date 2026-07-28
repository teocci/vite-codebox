package command

import (
	"context"
	"strconv"
)

// dispatchView routes the presentation verbs.
//
// Presentation gets its own group because it is not building. `exec` is the
// batch runner — it parses a JSON array, object or NDJSON from stdin and
// validates the whole batch before sending — and routing camera and HUD
// direction through it is a category error. The CLI already draws this line
// elsewhere: `clear` is both an op and a verb, as are box, sphere, cylinder and
// remove.
//
// The argv shape follows dispatchAuth: the subcommand and its own arguments are
// consumed here, and everything after them is the flag surface. flagSurface
// rejects positionals, so the split has to happen before parse.
func dispatchView(ctx context.Context, d Deps, args []string) error {
	if len(args) == 0 {
		return usagef("`view` needs a preset number or a subcommand: <N>, reframe, rotate, grid, or hud")
	}

	cmd, rest, err := viewCommand(args)
	if err != nil {
		return err
	}

	f := &buildFlags{flagSurface: newFlagSurface("view " + args[0]), id: -1}
	f.registerCommon()
	f.registerDryRun()
	if err := f.parse(rest); err != nil {
		return err
	}

	app, err := d.buildApp(f.backend)
	if err != nil {
		return err
	}
	return app.RunOne(ctx, cmd, f.exec())
}

// viewCommand turns the leading arguments into one command, returning the
// arguments left over for the flag surface.
//
// A numeric argument is a preset; a word is a subcommand. The preset count is
// deliberately NOT compiled in — `n` is published as `int+`, so this client
// checks only that it is a positive integer and the server refuses one that is
// out of range. Compiling in "there are six presets" is exactly the server
// knowledge internal/contract exists to avoid holding.
func viewCommand(args []string) (map[string]any, []string, error) {
	sub := args[0]
	if n, err := strconv.Atoi(sub); err == nil {
		return map[string]any{"op": "view", "n": float64(n)}, args[1:], nil
	}

	switch sub {
	case "reframe":
		return map[string]any{"op": "reframe"}, args[1:], nil
	case "rotate", "grid", "hud":
		if len(args) < 2 {
			return nil, nil, usagef("view %s needs on or off", sub)
		}
		on, err := parseOnOff(sub, args[1])
		if err != nil {
			return nil, nil, err
		}
		return map[string]any{"op": sub, "on": on}, args[2:], nil
	default:
		return nil, nil, usagef(
			"unknown view subcommand %q: want a preset number, reframe, rotate, grid, or hud", sub)
	}
}

// parseOnOff reads the flag ops' single argument. Only the two words are
// accepted: `true`/`1` would be a second spelling of the same state, and the
// error has to name the valid set because the caller is a script.
func parseOnOff(sub, value string) (bool, error) {
	switch value {
	case "on":
		return true, nil
	case "off":
		return false, nil
	default:
		return false, usagef("view %s: want on or off, got %q", sub, value)
	}
}
