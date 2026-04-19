# Safe Upgrade Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add transactional rollback, severity filters, and a `--drop` exclusion flag to `pcu -u`.

**Architecture:** Before writing any file changes, snapshot `pyproject.toml`, `uv.lock`, and `requirements.txt` into `.pcu/`. If the install fails, auto-restore and print a hint pointing at `--drop`. On success, delete `.pcu/`. New CLI flags filter the upgrade set by semver severity and exclude named packages.

**Tech Stack:** Python 3.11+, argparse, stdlib only (no new deps).

**Design reference:** `docs/plans/2026-04-19-safe-upgrade-design.md`

**Testing approach:** Manual verification per task. The tool has no pytest harness; its behavior is mostly subprocess and filesystem I/O best verified by running the real command against real fixtures. Each task includes concrete commands and expected output.

---

## Task 1: Add CLI flags

**Files:**
- Modify: `src/pcu/cli.py`

**Step 1: Update argparse**

Replace the body of `main()` in `src/pcu/cli.py` with:

```python
def main() -> None:
    parser = argparse.ArgumentParser(prog="pcu", description="Python Check Updates")
    parser.add_argument("-u", "--upgrade", action="store_true", help="upgrade pinned versions to latest")
    parser.add_argument("--major", action="store_true", help="include major bumps (use with -u)")
    parser.add_argument("--minor", action="store_true", help="include minor bumps (use with -u)")
    parser.add_argument("--patch", action="store_true", help="include patch bumps (use with -u)")
    parser.add_argument("--pin", action="store_true", help="include pin-only bumps (use with -u)")
    parser.add_argument("--drop", nargs="+", default=[], metavar="PKG", help="exclude named packages from upgrade (use with -u)")
    args = parser.parse_args()

    upgrade_only_flags = args.major or args.minor or args.patch or args.pin or args.drop
    if upgrade_only_flags and not args.upgrade:
        parser.error("--major/--minor/--patch/--pin/--drop require -u")

    if args.upgrade:
        severities: set[str] = set()
        if args.major:
            severities.add("major")
        if args.minor:
            severities.add("minor")
        if args.patch:
            severities.add("patch")
        if args.pin:
            severities.add("pin")
        cmd_upgrade(severities=severities, drops=args.drop)
    else:
        cmd_check()

    sys.exit(0)
```

**Step 2: Verify argparse**

Run: `uv run pcu --help`
Expected: help output listing `--major`, `--minor`, `--patch`, `--pin`, `--drop`.

Run: `uv run pcu --major`
Expected: error "--major/--minor/--patch/--pin/--drop require -u", exit non-zero.

Run: `uv run pcu --drop foo bar`
Expected: same error.

**Step 3: Commit**

```bash
git add src/pcu/cli.py
git commit -m "feat(cli): add --major/--minor/--patch/--pin/--drop flags"
```

Note: `cmd_upgrade` does not accept these arguments yet — the CLI will fail at runtime until Task 2. That's fine; the commit is an isolated interface change.

---

## Task 2: Apply filters inside `cmd_upgrade`

**Files:**
- Modify: `src/pcu/upgrade.py`

**Step 1: Add filter helper**

Add near the top of `src/pcu/upgrade.py` (after imports):

```python
def _normalize(name: str) -> str:
    return name.lower().replace("_", "-")


def _classify_with_pin(dep: dict[str, str], installed: dict[str, str]) -> str:
    """Return 'major'|'minor'|'patch'|'pin'|'none' for this dep."""
    severity = classify_update(dep["version"], dep["latest"])
    if severity == "none":
        return "none"
    inst = installed.get(dep["name"].lower(), "")
    if inst and not is_outdated(inst, dep["latest"]):
        return "pin"
    return severity


def _apply_filters(
    to_update: list[dict[str, str]],
    installed: dict[str, str],
    severities: set[str],
    drops: list[str],
) -> tuple[list[dict[str, str]], list[str]]:
    """Return (filtered, unknown_drops)."""
    drop_set = {_normalize(d) for d in drops}
    known = {_normalize(d["name"]) for d in to_update}
    unknown = sorted(drop_set - known)

    filtered: list[dict[str, str]] = []
    for dep in to_update:
        if _normalize(dep["name"]) in drop_set:
            continue
        if severities:
            sev = _classify_with_pin(dep, installed)
            if sev not in severities:
                continue
        filtered.append(dep)
    return filtered, unknown
```

Note: the existing `to_update` list already excludes "up to date" packages. "pin" severity here means the pinned string is behind but the installed version is already at latest — consistent with the check.py "pin outdated" row.

**Step 2: Rewire `cmd_upgrade` signature and call site**

Change the signature:

```python
def cmd_upgrade(severities: set[str] | None = None, drops: list[str] | None = None) -> None:
```

At the top of the body, normalize defaults:

```python
    severities = severities or set()
    drops = drops or []
```

After the existing line `to_update = [d for d in deps if d["latest"] and is_outdated(d["version"], d["latest"])]` (around line 49), add:

```python
    to_update, unknown_drops = _apply_filters(to_update, installed, severities, drops)
    if unknown_drops:
        print(f"  {YELLOW}Warning: --drop names not in upgrade set: {', '.join(unknown_drops)}{RESET}\n")
```

The existing `if not to_update:` block just below will already handle the empty case, but the message is `"All pinned versions are already up to date!"` — misleading when filters emptied the set. Replace that block with:

```python
    if not to_update:
        if severities or drops:
            print(f"  {DIM}Nothing to upgrade after filters.{RESET}\n")
        else:
            print(f"  {GREEN}All pinned versions are already up to date!{RESET}\n")
            if has_pyproject and has_requirements:
                expected = generate_requirements(load_pyproject())
                if REQUIREMENTS_PATH.read_text() != expected:
                    REQUIREMENTS_PATH.write_text(expected)
                    print("  Synced requirements.txt\n")
        return
```

**Step 3: Manual verification**

Use any project with a pyproject.toml that has outdated deps. From that project directory:

Run: `pcu -u --patch`
Expected: only patch-severity bumps applied; major/minor entries skipped. Sync succeeds.

Run: `pcu -u --drop anthropic pydantic` (against a project where those are in the upgrade set)
Expected: upgrade set excludes anthropic and pydantic; sync proceeds.

Run: `pcu -u --drop doesnotexist`
Expected: "Warning: --drop names not in upgrade set: doesnotexist", upgrade proceeds normally for all packages.

Run: `pcu -u --minor --patch` against a project with only major updates available
Expected: "Nothing to upgrade after filters.", no file changes, exit 0.

**Step 4: Commit**

```bash
git add src/pcu/upgrade.py
git commit -m "feat(upgrade): filter upgrade set by severity and --drop names"
```

---

## Task 3: Snapshot module

**Files:**
- Create: `src/pcu/snapshot.py`

**Step 1: Write the module**

```python
from __future__ import annotations

import shutil
from pathlib import Path

SNAPSHOT_DIR = Path(".pcu")
GITIGNORE_PATH = Path(".gitignore")
GITIGNORE_ENTRY = ".pcu/"


def ensure_gitignore() -> None:
    """Add .pcu/ to .gitignore if not already listed."""
    if GITIGNORE_PATH.exists():
        lines = GITIGNORE_PATH.read_text().splitlines()
        stripped = {line.strip().rstrip("/") for line in lines}
        if ".pcu" in stripped:
            return
        sep = "" if GITIGNORE_PATH.read_text().endswith("\n") else "\n"
        GITIGNORE_PATH.write_text(GITIGNORE_PATH.read_text() + sep + GITIGNORE_ENTRY + "\n")
    else:
        GITIGNORE_PATH.write_text(GITIGNORE_ENTRY + "\n")


def snapshot(files: list[Path]) -> None:
    """Copy existing files into SNAPSHOT_DIR."""
    SNAPSHOT_DIR.mkdir(exist_ok=True)
    for f in files:
        if f.exists():
            shutil.copy2(f, SNAPSHOT_DIR / f.name)


def restore(files: list[Path]) -> None:
    """Copy snapshot files back to their original paths."""
    for f in files:
        snap = SNAPSHOT_DIR / f.name
        if snap.exists():
            shutil.copy2(snap, f)


def cleanup() -> None:
    """Remove the snapshot directory."""
    if SNAPSHOT_DIR.exists():
        shutil.rmtree(SNAPSHOT_DIR)
```

**Step 2: Manual verification**

From a Python REPL in the project root (or a scratch test directory):

```python
from pathlib import Path
from pcu.snapshot import ensure_gitignore, snapshot, restore, cleanup

# 1. gitignore handling
ensure_gitignore()
assert ".pcu" in Path(".gitignore").read_text()
ensure_gitignore()  # idempotent
assert Path(".gitignore").read_text().count(".pcu") == 1

# 2. snapshot + restore round-trip
p = Path("pyproject.toml")
original = p.read_text()
snapshot([p])
p.write_text("broken")
restore([p])
assert p.read_text() == original

cleanup()
assert not Path(".pcu").exists()
```

Expected: all assertions pass, no exceptions.

**Step 3: Commit**

```bash
git add src/pcu/snapshot.py
git commit -m "feat(snapshot): add .pcu/ snapshot, restore, and .gitignore helper"
```

---

## Task 4: Wire snapshot + rollback into `cmd_upgrade`

**Files:**
- Modify: `src/pcu/upgrade.py`

**Step 1: Add imports**

At the top of `src/pcu/upgrade.py`:

```python
from pcu.snapshot import cleanup, ensure_gitignore, restore, snapshot
```

**Step 2: Build the set of files we touch**

Add near the top of `cmd_upgrade`, after `has_pyproject, has_requirements = detect_sources()`:

```python
    managed_files: list[Path] = []
    if has_pyproject:
        managed_files.append(PYPROJECT_PATH)
        if Path("uv.lock").exists():
            managed_files.append(Path("uv.lock"))
    if has_requirements:
        managed_files.append(REQUIREMENTS_PATH)
```

Add `from pathlib import Path` to the imports if not already present.

**Step 3: Snapshot before writing**

Locate the line `print(f"  {BOLD}Updating pinned versions:{RESET}\n")` (currently around line 60). Immediately before it, insert:

```python
    ensure_gitignore()
    snapshot(managed_files)
```

**Step 4: Restore on sync failure**

Locate:

```python
    if result.returncode != 0:
        print(f"\n  {RED}Sync failed.{RESET}")
        sys.exit(1)
```

Replace with:

```python
    if result.returncode != 0:
        print(f"\n  {RED}Sync failed. Reverting changes...{RESET}")
        restore(managed_files)
        cleanup()
        attempted = " ".join(d["name"] for d in to_update)
        print(f"\n  {DIM}To retry excluding specific packages:{RESET}")
        print(f"  {BOLD}pcu -u --drop <package>{RESET}  (attempted: {attempted})\n")
        sys.exit(1)
```

**Step 5: Cleanup on success**

Locate the `if all_good:` / `else:` block at the end. After the final `print` of either branch, add `cleanup()`:

```python
    print()
    if all_good:
        print(f"  {GREEN}Upgrade complete!{RESET}\n")
    else:
        print(f"  {YELLOW}Some packages may not have updated to the exact latest version.{RESET}\n")
    cleanup()
```

**Step 6: Manual verification — success path**

In a project with a clean upgrade available:

Run: `pcu -u`
Expected: upgrade succeeds, `.pcu/` does not exist at the end, `.gitignore` contains `.pcu/`.

**Step 7: Manual verification — failure path**

In a project you can intentionally break (e.g., the rfnry-rag case the user hit):

Run: `pcu -u`
Expected:
- uv's error output streams to the terminal unchanged.
- "Sync failed. Reverting changes..." is printed.
- `pyproject.toml`, `uv.lock`, `requirements.txt` match their pre-run content (verify with `git diff` — should show no changes).
- `.pcu/` is removed.
- Recovery hint appears: `pcu -u --drop <package>  (attempted: openai anthropic pydantic cohere baml-py lxml ruff mypy)`.
- Exit code is non-zero.

Run: `pcu -u --drop anthropic pydantic`
Expected: remaining packages upgrade successfully; `.pcu/` cleaned up.

**Step 8: Commit**

```bash
git add src/pcu/upgrade.py
git commit -m "feat(upgrade): snapshot and auto-revert on sync failure"
```

---

## Task 5: README documentation

**Files:**
- Modify: `README.md`

**Step 1: Document the new flags and snapshot behavior**

Add a new section under the usage area (exact location depends on current README layout — place it after the basic `pcu -u` description):

```markdown
## Filtering upgrades

Combine these flags with `-u` to restrict which bumps are applied:

- `--major` — include major version bumps
- `--minor` — include minor version bumps
- `--patch` — include patch version bumps
- `--pin` — include pin-only bumps (installed is already at latest, pin string is stale)
- `--drop pkg1 pkg2 ...` — exclude named packages from the upgrade set

Flags combine as a union:

```sh
pcu -u --minor --patch            # minor + patch only, skip major
pcu -u --drop anthropic pydantic  # everything except these two
pcu -u --minor --drop cohere      # minor bumps, minus cohere
```

## Safe upgrades

Before touching `pyproject.toml`, `uv.lock`, or `requirements.txt`, `pcu`
snapshots the current contents into `.pcu/` (which is auto-added to
`.gitignore`). If `uv sync` or `pip install` fails, the snapshot is restored
and a hint is printed suggesting `--drop` to exclude suspect packages on
retry. On success, `.pcu/` is cleaned up.
```

**Step 2: Verify**

Read the README.md top-to-bottom and confirm the new section flows with surrounding content.

**Step 3: Commit**

```bash
git add README.md
git commit -m "docs: document filter flags and snapshot rollback"
```

---

## Final integration check

After all tasks:

1. `uv run pcu` in a fresh checkout — output unchanged from before (the check command is untouched).
2. `uv run pcu -u --help` — help text lists all new flags.
3. Run the full upgrade-succeeds path on a project with outdated deps.
4. Run the full upgrade-fails path on the rfnry-rag project. Confirm full revert.
5. `git status` shows a clean working tree between runs (snapshot cleaned up).
6. `ruff check src/` and `mypy src/` are clean.
