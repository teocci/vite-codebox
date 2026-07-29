---
description: Wipe every part from the codeblox world
allowed-tools: Bash(.venv/Scripts/python .claude/skills/codeblox-builder/scripts/cli.py:*)
---

!`.venv/Scripts/python .claude/skills/codeblox-builder/scripts/cli.py clear`

Report in one line what the CLI said. The world is now empty, and `remove` takes an id, so there is
no undo — do not offer to restore anything.

On a non-zero exit, report it and stop. Do not retry, and do not improvise a diagnosis: run
`/codeblox:doctor`, which checks the binary, the credential and the server in one pass. Exit 4 means
the server is unreachable — `npm start` brings up both the ws server and Vite.
