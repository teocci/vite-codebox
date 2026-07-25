'''Run a staged build plan: validate the whole thing, then land it beat by beat.

    $VENV/python .../build.py [--dry-run] [--from N] [--only NAME] [--pace SPEC] < plan.json

A plan is one JSON object of named stages. Each stage is a list of parts, and a
part is either a *shape call* expanded through shapes.py or a *raw command*
passed through untouched:

    {"name": "castle", "stages": [
      {"name": "mass",   "parts": [{"shape": "shell", "at": [-20,0,-20],
                                    "size": [40,14,40], "mat": "brick"}]},
      {"name": "detail", "parts": [{"op": "box", "at": [-22,22,-22],
                                    "size": [6,1,6], "mat": "copper"}]}]}

Two things justify this over piping shapes.py into submit.py once per stage.

The first is the gate. submit.py dry-runs the batch it was handed and nothing
else, so a bad material in the last stage of a five-stage build is invisible
until the first four have already landed — and there is no partial undo, because
`remove` takes an id, not a region. Here every stage is bounds-checked and
validated by the CLI *before the first block is sent*, so a plan either builds
or nothing moves.

The second is that build order is visible. The viewer drops each new part from
above over DROP_MS, staggered per part, and settled parts never re-animate, so
every submitted batch is one animation beat. Stages are the choreography; pacing
them on the real settle time is what makes the beats legible. A `build_begin`
marker goes out ahead of stage 1 so the viewer knows those beats belong to one
build and can frame it, rather than zooming out to fit everything ever built.
'''

from __future__ import annotations

import argparse
import inspect
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import resolve_codeblox as rc  # noqa: E402
import shapes  # noqa: E402
import submit  # noqa: E402
import world  # noqa: E402

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_NETWORK = 4
EXIT_CONTRACT = 5

# Sent once, ahead of the first stage, so the viewer can tell this build's parts
# from whatever was already in the world — which is what lets its camera follow
# the new thing instead of zooming out to fit everything ever built. It mutates
# nothing; --no-focus omits it.
FOCUS_MARKER = {'op': 'build_begin'}

# Mirrors apps/web/src/engine/DropAnimator.js. Those constants live only in that
# module — they are not in packages/shared and the server does not publish them
# in the contract — so they cannot be read at runtime from here. tests/ reads
# that file and fails if either value drifts.
DROP_MS = 350
STAGGER_MS = 18

# Every generator shapes.py exposes as a subcommand. A test asserts this stays in
# step with shapes.build_parser(), so adding a generator there fails loudly here
# rather than silently being unreachable from a plan.
SHAPES = {
    'shell': shapes.shell,
    'stairs': shapes.stairs,
    'arch': shapes.arch,
    'bridge': shapes.bridge,
}


class PlanError(Exception):
    '''A bad plan, or a build that stopped, with an exit code to branch on.'''

    def __init__(self, message: str, code: int = EXIT_USAGE):
        super().__init__(message)
        self.code = code


# ── reading the plan ────────────────────────────────────────────────────────

def load_plan(stream) -> dict:
    '''Parse the plan and check its shape — not its geometry.'''
    text = stream.read().strip()
    if not text:
        raise PlanError('empty plan on stdin — pipe a JSON plan, or see SKILL.md for the format')
    try:
        plan = json.loads(text)
    except json.JSONDecodeError as exc:
        raise PlanError(f'plan is not valid JSON: {exc}') from exc

    if not isinstance(plan, dict) or not isinstance(plan.get('stages'), list):
        raise PlanError('a plan is an object with a "stages" array')
    if not plan['stages']:
        raise PlanError('plan has no stages')
    for index, stage in enumerate(plan['stages']):
        check_stage(stage, index)
    return plan


def check_stage(stage, index: int) -> None:
    '''Every stage needs a name and at least one part.

    The name is not decoration: it is what progress lines, --only, and the
    "stage 3 failed" message all refer to. An unnamed stage makes a failure
    report unactionable, so it is refused here rather than papered over.
    '''
    where = f'stage {index + 1}'
    if not isinstance(stage, dict):
        raise PlanError(f'{where} is not an object')
    if not isinstance(stage.get('name'), str) or not stage['name'].strip():
        raise PlanError(f'{where} has no "name" — progress and --only refer to it')
    if not isinstance(stage.get('parts'), list) or not stage['parts']:
        raise PlanError(f'{where} ({stage["name"]}) has no parts')


# ── expanding parts into commands ───────────────────────────────────────────

def expand_part(part, where: str) -> list[dict]:
    '''One plan entry to commands. A `shape` is generated; anything else is raw.'''
    if not isinstance(part, dict):
        raise PlanError(f'{where} is not an object')
    if 'shape' not in part:
        if 'op' not in part:
            raise PlanError(f'{where} has neither "shape" nor "op"')
        return [part]
    return expand_shape(part, where)


def expand_shape(part: dict, where: str) -> list[dict]:
    '''Call a shapes.py generator with the part's remaining keys as arguments.

    Arguments are bound through the generator's own signature rather than a
    table kept here, so the accepted keys can never drift from the functions —
    and an unknown key reports what *is* accepted instead of raising TypeError.
    '''
    name = part['shape']
    generator = SHAPES.get(name)
    if generator is None:
        raise PlanError(f'{where}: unknown shape {name!r}; have {", ".join(sorted(SHAPES))}')

    accepted = list(inspect.signature(generator).parameters)
    kwargs = {key.replace('-', '_'): value for key, value in part.items() if key != 'shape'}
    unknown = [key for key in kwargs if key not in accepted]
    if unknown:
        raise PlanError(f'{where}: {name} takes no {unknown[0]!r}; '
                        f'accepts {", ".join(accepted)}')
    try:
        return generator(**kwargs)
    except (TypeError, shapes.ShapeError) as exc:
        raise PlanError(f'{where}: {name}: {exc}') from exc


def expand(stages: list[dict]) -> list[list[dict]]:
    '''Commands per stage, in order. Errors name the stage and the part.'''
    expanded = []
    for index, stage in enumerate(stages):
        commands: list[dict] = []
        for position, part in enumerate(stage['parts']):
            where = f'stage {index + 1} ({stage["name"]}) part {position}'
            commands.extend(expand_part(part, where))
        expanded.append(commands)
    return expanded


# ── pacing ──────────────────────────────────────────────────────────────────

def settle_ms(count: int) -> int:
    '''How long a batch of `count` parts takes to finish falling, in ms.

    The last part starts STAGGER_MS * (count - 1) after the first and then takes
    DROP_MS to land.
    '''
    return DROP_MS + STAGGER_MS * max(0, count - 1)


def pace_ms(spec: str, count: int) -> int:
    '''Resolve --pace against a stage size. `settle` tracks the animation.'''
    if spec == 'none':
        return 0
    if spec == 'settle':
        return settle_ms(count)
    try:
        return max(0, int(spec))
    except ValueError as exc:
        raise PlanError(f'--pace wants settle, none, or milliseconds — got {spec!r}') from exc


# ── selecting which stages to send ──────────────────────────────────────────

def select(stages: list[dict], start: int | None, only: str | None) -> list[int]:
    '''Indices of the stages to send. Validation always covers all of them.'''
    if only is not None:
        chosen = [i for i, stage in enumerate(stages) if stage['name'] == only]
        if not chosen:
            raise PlanError(f'no stage named {only!r}; have '
                            f'{", ".join(stage["name"] for stage in stages)}')
        return chosen
    if start is None:
        return list(range(len(stages)))
    if not 1 <= start <= len(stages):
        raise PlanError(f'--from {start} is outside 1..{len(stages)}')
    return list(range(start - 1, len(stages)))


# ── the build ───────────────────────────────────────────────────────────────

def stage_problems(stage: dict, batch: list[dict], index: int, bounds: dict) -> list[str]:
    '''Every way one stage's commands leave the world, each named in full.'''
    return [f'  stage {index + 1} ({stage["name"]}) '
            f'command {position} ({command.get("op")}): {reason}'
            for position, command in enumerate(batch)
            for reason in world.out_of_bounds(command, bounds)]


def check_bounds(stages: list[dict], batches: list[list[dict]], bounds: dict) -> None:
    '''Refuse a plan that leaves the world, naming the stage and the command.

    submit.check_bounds indexes a single flat batch, which across five stages
    reports "command 32" — true, and useless. The arithmetic is still
    world.out_of_bounds; only the reporting is per-stage.
    '''
    problems = [problem
                for index, (stage, batch) in enumerate(zip(stages, batches))
                for problem in stage_problems(stage, batch, index, bounds)]
    if problems:
        raise PlanError('plan leaves the world; nothing sent:\n' + '\n'.join(problems),
                        EXIT_CONTRACT)


def validate(binary: str, stages: list[dict], batches: list[list[dict]],
             bounds: dict, run=None, prelude: list[dict] = ()) -> None:
    '''Gate the entire plan before anything is sent. This is the whole point.

    The prelude is validated with the stages so a server that does not know the
    focus marker fails here, with nothing built, rather than after the first
    stage has already landed.
    '''
    check_bounds(stages, batches, bounds)
    flat = [*prelude, *(c for batch in batches for c in batch)]
    submit.run_exec(binary, flat, dry_run=True, run=run)


def send_stage(binary: str, commands: list[dict], run=None) -> dict:
    '''Send one stage and reduce the ack to what the report needs.'''
    report = submit.run_exec(binary, commands, dry_run=False, run=run)
    return {
        'count': len(commands),
        'sent': report.get('sent', 0),
        'addedIds': report.get('addedIds') or [],
        'cleared': report.get('cleared', False),
    }


def run_stages(binary, stages, batches, chosen, pace, run=None, sleep=None,
               progress=None, prelude: list[dict] = ()) -> list[dict]:
    '''Send the chosen stages in order, reporting each as it lands.

    The prelude goes as its own batch ahead of stage 1, rather than riding along
    with it, so stage numbering and per-stage counts stay about the build.

    A failure part-way names what already landed, because that is the state the
    world is actually in and the caller has to decide what to do about it.
    '''
    sleep = sleep or time.sleep
    if prelude:
        submit.run_exec(binary, list(prelude), dry_run=False, run=run)
    landed: list[dict] = []
    for position, index in enumerate(chosen):
        entry = {'index': index + 1, 'name': stages[index]['name']}
        try:
            entry.update(send_stage(binary, batches[index], run=run))
        except submit.SubmitError as exc:
            raise PlanError(stopped_detail(entry, landed, exc), exc.code) from exc

        last = position + 1 == len(chosen)
        entry['paceMs'] = 0 if last else pace_ms(pace, entry['count'])
        landed.append(entry)
        if progress:
            # Out of the whole plan, not out of the selection — with --from 4,
            # "stage 4/5" is the truth and "stage 4/2" is nonsense.
            progress(entry, len(stages))
        sleep(entry['paceMs'] / 1000)
    return landed


def stopped_detail(failed: dict, landed: list[dict], exc: Exception) -> str:
    '''What landed, what broke, and how to pick up where it stopped.'''
    if not landed:
        return f"stage {failed['index']} ({failed['name']}) failed, nothing landed: {exc}"
    ids = [i for entry in landed for i in entry['addedIds']]
    span = (f"stage {landed[0]['index']}" if len(landed) == 1
            else f"stages {landed[0]['index']}-{landed[-1]['index']}")
    return (f"{span} landed ({id_range(ids)}); "
            f"stage {failed['index']} ({failed['name']}) failed: {exc}\n"
            f"  the world is half-built — fix the plan and re-run with --from {failed['index']}, "
            f"or start over with a clear stage")


def build(binary, plan, bounds, args, run=None, sleep=None, progress=None) -> dict:
    '''Validate everything, then land the chosen stages.'''
    stages = plan['stages']
    batches = expand(stages)
    chosen = select(stages, args.start, args.only)
    prelude = [] if args.no_focus else [FOCUS_MARKER]
    validate(binary, stages, batches, bounds, run=run, prelude=prelude)

    total = sum(len(batch) for batch in batches)
    if args.dry_run:
        return {'ok': True, 'plan': plan.get('name'), 'dryRun': True,
                'stages': [], 'validated': total, 'sent': 0}

    landed = run_stages(binary, stages, batches, chosen, args.pace,
                        run=run, sleep=sleep, progress=progress, prelude=prelude)
    return {'ok': True, 'plan': plan.get('name'), 'dryRun': False, 'stages': landed,
            'validated': total, 'sent': sum(entry['sent'] for entry in landed)}


# ── rendering ───────────────────────────────────────────────────────────────

def id_range(ids: list) -> str:
    '''`ids 1..22` when contiguous, the list when it is not. Empty stays empty.'''
    if not ids:
        return 'no ids'
    contiguous = (all(isinstance(i, int) for i in ids)
                  and ids == list(range(ids[0], ids[0] + len(ids))))
    return f'ids {ids[0]}..{ids[-1]}' if contiguous and len(ids) > 2 else f'ids {ids}'


def stage_line(entry: dict, total: int) -> str:
    '''One progress line, written to stderr as the stage lands.'''
    noun = 'cmd' if entry['count'] == 1 else 'parts'
    cleared = entry['cleared'] and not entry['addedIds']
    tail = 'world cleared' if cleared else id_range(entry['addedIds'])
    pace = f"{entry['paceMs']}ms" if entry.get('paceMs') else ''
    return (f"stage {entry['index']}/{total}  {entry['name']:<10} "
            f"{entry['count']:>3} {noun:<5}  {tail:<16}{pace}").rstrip()


def render(report: dict) -> str:
    '''The final report. Progress already streamed to stderr while it ran.'''
    name = report.get('plan') or 'plan'
    if report['dryRun']:
        return (f"dry run: {name} — {report['validated']} command(s) across all stages "
                f"are valid and in bounds, nothing sent")
    return f"built {name!r}: {report['sent']} part(s) in {len(report['stages'])} stage(s)"


# ── command line ────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='Validate a staged build plan in full, then land it stage by stage.',
        epilog='Reads a JSON plan on stdin:  build.py --dry-run < castle.json',
    )
    parser.add_argument('--bin', help='path to the codeblox binary')
    parser.add_argument('--dry-run', action='store_true',
                        help='validate every stage and send nothing')
    parser.add_argument('--from', dest='start', type=int, metavar='N',
                        help='start at stage N (1-based); everything is still validated')
    parser.add_argument('--only', metavar='NAME', help='send just this stage')
    parser.add_argument('--pace', default='settle', metavar='SPEC',
                        help='settle (default: wait for the drop to finish), none, or milliseconds')
    parser.add_argument('--no-focus', action='store_true',
                        help="don't mark the build, so the viewer's camera keeps its framing")
    parser.add_argument('--json', action='store_true', help='emit the report as JSON')
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    progress = None if args.json else lambda entry, total: print(
        stage_line(entry, total), file=sys.stderr)

    try:
        binary = rc.resolve(args.bin, os.environ.copy(), Path.cwd())['path']
        plan = load_plan(sys.stdin)
        bounds = world.bounds_of(world.fetch(binary))
        report = build(binary, plan, bounds, args, progress=progress)
    except rc.ResolutionError as exc:
        print(f'build: {exc}', file=sys.stderr)
        return EXIT_USAGE
    except world.WorldError as exc:
        print(f'build: {exc}', file=sys.stderr)
        return EXIT_NETWORK
    except (PlanError, submit.SubmitError) as exc:
        print(f'build: {exc}', file=sys.stderr)
        return exc.code

    print(json.dumps(report) if args.json else render(report))
    return EXIT_OK


if __name__ == '__main__':
    sys.exit(main())
