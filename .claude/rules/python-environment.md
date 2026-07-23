# Python Environment Rules

## Scope (Skills & Non-Python Projects)

These rules govern **every** Python invocation — including a skill's `scripts/` — even when the host
project is Go, a docs/video/TTS project, or otherwise non-Python. If a skill runs Python, create and
use a `.venv` **first**; never the system interpreter. See [15-skills.md](15-skills.md) for how the
other rules apply to skills.

- **Venv location:** the host project root `.venv/` (shared). A standalone/personal skill with no
  host project → the skill's own directory is the root.
- **Gitignore:** ensure `.venv/` and `__pycache__/` are gitignored; **add a `.gitignore` if none
  exists**. This matters most when the host root is non-Python and has no Python `.gitignore` yet.
- **Deps:** prefer declaring a skill's dependencies in `<skill>/requirements.txt` and installing
  with `$VENV/pip install -r <skill>/requirements.txt` (see the venv-path resolution below).

## Required Python Version

- **Windows:** Python 3.11.9
- **Linux:** Python 3.11.9 (or `python3.11` from package manager)
- **macOS:** Python 3.11.9 (or `python3.11` via Homebrew)

## Virtual Environment Setup

Before running any Python command, ensure the virtual environment exists at `.venv/`.

### Creating the environment (if `.venv/` does not exist)

```bash
# Windows
py -3.11 -m venv .venv

# Linux / macOS
python3.11 -m venv .venv
```

## Resolving the venv binary path

Determine the platform once per session and use the venv binary directly.
**Do not activate the environment** — call the binary by its full path instead.

| Platform       | Python binary            | pip / tools              |
|----------------|--------------------------|--------------------------|
| Windows        | `.venv/Scripts/python`   | `.venv/Scripts/pip`      |
| Linux / macOS  | `.venv/bin/python`       | `.venv/bin/pip`          |

Assign the correct prefix to a shell variable at the start of a session:

```bash
# Resolve once — works on any OS
if [ -d ".venv/Scripts" ]; then
  VENV=".venv/Scripts"
else
  VENV=".venv/bin"
fi
```

Then every subsequent command is platform-agnostic:

```bash
$VENV/python -m pytest tests/unit/ -v
$VENV/pip install --upgrade pip
$VENV/pip install some-package
```

## Rules for All Python Execution

1. **Never use the system Python.** Always run Python via the `.venv` binary.
2. **Do not use `source activate`.** Call the venv binary directly (e.g., `$VENV/python`).
   Activation is a human convenience; scripts should invoke the binary by path.
3. **If `.venv/` does not exist**, create it before proceeding. Do not skip this step.
4. **If a package is missing**, install it with `$VENV/pip install <package>`.
5. **Do not add `.venv/` to version control.** It should be in `.gitignore`.
