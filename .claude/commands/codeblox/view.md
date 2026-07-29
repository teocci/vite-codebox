---
description: Point the codeblox viewer — preset, reframe, or a display toggle
argument-hint: <1-6> | reframe | rotate on|off | grid on|off | hud on|off
allowed-tools: Bash(.venv/Scripts/python .claude/skills/codeblox-builder/scripts/cli.py:*)
---

!`.venv/Scripts/python .claude/skills/codeblox-builder/scripts/cli.py view $ARGUMENTS`

Report in one line what the CLI said. Viewer ops are relayed to every connected viewer and stored
nowhere, so nothing in the world changed.

Arguments pass straight through — the CLI owns the valid set and refuses a bad one with exit 2 and a
message naming it. Report that message as-is rather than guessing a correction. Exit 6 is the
server's refusal, not the client's: only the server knows how many presets exist.

On exit 3 or 4, run `/codeblox:doctor`.
