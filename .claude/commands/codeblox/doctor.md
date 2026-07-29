---
description: Preflight the codeblox binary, credential, and server in one pass
allowed-tools: Bash(.venv/Scripts/python .claude/skills/codeblox-builder/scripts/doctor.py:*)
---

!`.venv/Scripts/python .claude/skills/codeblox-builder/scripts/doctor.py`

Report the rows as they came back. Three `[ok  ]` lines means everything is working.

A `FAIL` row already names the remedy — relay it and stop, rather than starting a troubleshooting
sequence of your own. The exit code says which rung broke:

| exit | meaning | remedy |
|---|---|---|
| 2 | no working binary | `npm run build:cli`, or `install_codeblox.py` |
| 3 | no credential the server accepts | `codeblox auth login` |
| 4 | the server is unreachable | `npm start` — it runs the ws server and Vite together |
