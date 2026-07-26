'''Validate a batch, send it, and report the result — one call, one contract.

    ... | $VENV/python .../submit.py [--dry-run] [--json] [--bin PATH]

Reads commands on stdin as NDJSON or a JSON array, then:

    1. checks every part against the world bounds read from the contract
    2. runs `codeblox exec --dry-run` so the schema and palette are checked
       before anything is sent
    3. sends, and parses the ack into addedIds

Step 1 exists because bounds are enforced server-side ONLY: the published schema
types fields, it does not describe geometry, so the CLI cannot check them. That
made "stay inside the extent" a rule the model had to remember. Here it is a
gate, checked against the extent the server itself published.

Exit codes are the CLI's own (internal/command/exit.go): 2 usage, 4 network,
5 rejected here, 6 rejected by the server.
'''

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import resolve_codeblox as rc  # noqa: E402
import world  # noqa: E402

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_NETWORK = 4
EXIT_CONTRACT = 5
EXIT_SERVER = 6

EXEC_TIMEOUT = 120


class SubmitError(Exception):
    '''A failure with an exit code the caller can branch on.'''

    def __init__(self, message: str, code: int = EXIT_USAGE):
        super().__init__(message)
        self.code = code


def read_batch(stream) -> list[dict]:
    '''Parse NDJSON or a JSON array from stdin, mirroring what the CLI accepts.'''
    text = stream.read().strip()
    if not text:
        raise SubmitError('empty batch on stdin — pipe commands from shapes.py, '
                          'or write NDJSON directly')

    if text.startswith('['):
        try:
            batch = json.loads(text)
        except json.JSONDecodeError as exc:
            raise SubmitError(f'batch is not valid JSON: {exc}') from exc
    else:
        batch = []
        for number, line in enumerate(text.splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            try:
                batch.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise SubmitError(f'line {number} is not valid JSON: {exc}') from exc

    if not batch:
        raise SubmitError('batch contained no commands')
    return batch


def check_bounds(batch: list[dict], bounds: dict) -> None:
    '''Refuse a batch that leaves the world, naming the command and the axis.

    The server would refuse it anyway; catching it here saves a round trip and
    reports which command is wrong rather than how many.
    '''
    problems = []
    for index, command in enumerate(batch):
        for reason in world.out_of_bounds(command, bounds):
            problems.append(f'  command {index} ({command.get("op")}): {reason}')
    if problems:
        raise SubmitError(
            'batch leaves the world; nothing sent:\n' + '\n'.join(problems),
            EXIT_CONTRACT,
        )


def run_exec(binary: str, batch: list[dict], dry_run: bool, run=None) -> dict:
    '''Hand the batch to `codeblox exec --json` and return its report.'''
    run = run or subprocess.run
    argv = [binary, 'exec', '--json']
    if dry_run:
        argv.append('--dry-run')

    payload = '\n'.join(json.dumps(command) for command in batch)
    try:
        done = run(argv, input=payload, capture_output=True, text=True,
                   timeout=EXEC_TIMEOUT, env=os.environ.copy())
    except subprocess.TimeoutExpired as exc:
        raise SubmitError(f'`codeblox exec` did not answer in {EXEC_TIMEOUT}s',
                          EXIT_NETWORK) from exc

    if done.returncode != EXIT_OK:
        raise SubmitError(failure_detail(done), done.returncode)
    try:
        return json.loads(done.stdout)
    except json.JSONDecodeError as exc:
        raise SubmitError(f'`codeblox exec` did not emit JSON: {exc}\n{done.stdout}',
                          EXIT_USAGE) from exc


def failure_detail(done) -> str:
    '''Pull the reason out of the CLI's failure, envelope or prose.

    I-2 made every failure a JSON envelope under --json, so this reads the
    structured form first and falls back to the raw text.
    '''
    text = (done.stderr or done.stdout).strip()
    try:
        envelope = json.loads(text)
    except json.JSONDecodeError:
        return text
    return envelope.get('detail', text)


def submit(batch: list[dict], binary: str, bounds: dict, dry_run: bool, run=None) -> dict:
    '''Gate, validate, and send. Returns the report the caller prints.'''
    check_bounds(batch, bounds)

    validated = run_exec(binary, batch, dry_run=True, run=run)
    if dry_run:
        return {'ok': True, 'dryRun': True, 'validated': validated.get('validated', len(batch)),
                'sent': 0, 'addedIds': []}

    report = run_exec(binary, batch, dry_run=False, run=run)
    return {
        'ok': report.get('ok', False),
        'dryRun': False,
        'validated': len(batch),
        'sent': report.get('sent', 0),
        'addedIds': report.get('addedIds') or [],
        'removed': report.get('removed') or [],
        'cleared': report.get('cleared', False),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description='Bounds-check, validate, and send a batch of build commands.',
        epilog='Reads NDJSON or a JSON array on stdin:  shapes.py bridge --mat oak | submit.py',
    )
    parser.add_argument('--bin', help='path to the codeblox binary')
    parser.add_argument('--dry-run', action='store_true',
                        help='validate everything and send nothing')
    parser.add_argument('--json', action='store_true', help='emit the report as JSON')
    args = parser.parse_args(argv)

    try:
        binary = rc.resolve(args.bin, os.environ.copy(), Path.cwd())['path']
        batch = read_batch(sys.stdin)
        bounds = world.bounds_of(world.fetch(binary))
        report = submit(batch, binary, bounds, args.dry_run)
    except rc.ResolutionError as exc:
        print(f'submit: {exc}', file=sys.stderr)
        return EXIT_USAGE
    # Before WorldError, which it subclasses: an unmeasurable op is a command
    # rejected here (5), not a server that would not answer (4).
    except world.AnchorError as exc:
        print(f'submit: {exc}', file=sys.stderr)
        return EXIT_CONTRACT
    except world.WorldError as exc:
        print(f'submit: {exc}', file=sys.stderr)
        return EXIT_NETWORK
    except SubmitError as exc:
        print(f'submit: {exc}', file=sys.stderr)
        return exc.code

    print(json.dumps(report) if args.json else render(report))
    return EXIT_OK


def render(report: dict) -> str:
    if report['dryRun']:
        return f"dry run: {report['validated']} command(s) valid, nothing sent"
    line = f"sent {report['sent']} command(s)"
    if report['addedIds']:
        line += f", added ids {report['addedIds']}"
    if report.get('removed'):
        line += f", removed {report['removed']}"
    if report.get('cleared'):
        line += ', world cleared'
    return line


if __name__ == '__main__':
    sys.exit(main())
