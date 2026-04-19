# Safe Upgrade Design

Date: 2026-04-19

## Problem

`pcu -u` writes all version bumps to `pyproject.toml` (and `requirements.txt`),
then runs `uv sync --all-extras`. If the resolver fails — typically because one
upgraded package has transitive constraints incompatible with another upgraded
package — the file changes stay on disk while the environment is left in a
broken state. Recovery requires the user to manually reconstruct their previous
pins.

## Goals

1. Any failed upgrade leaves the working tree exactly as it was before `pcu -u`
   ran.
2. Users can iterate by excluding suspect packages and retrying, without losing
   the rest of the upgrade set.
3. Users can scope upgrades by severity (major/minor/patch) or to pin-only
   bumps.

## Non-goals

- Pre-flight resolution / dry-run. The install is the source of truth; if it
  fails, we revert and let the user decide what to do next.
- Parsing uv or pip error output to guess which package is at fault. The user
  reads the error (uv prints it directly) and decides.
- Interactive prompts. The tool is non-interactive; `--drop` is the lever.
- Multi-snapshot history. One snapshot per run, cleared on exit.

## CLI

All new flags apply only with `-u`.

```
pcu -u                            # upgrade everything (unchanged default)
pcu -u --major                    # only major bumps
pcu -u --minor                    # only minor bumps
pcu -u --patch                    # only patch bumps
pcu -u --pin                      # only pin-outdated (installed at latest, stale pin string)
pcu -u --minor --patch            # union: minor + patch
pcu -u --drop anthropic pydantic  # exclude named packages
pcu -u --minor --drop cohere      # combine: minor-only, minus cohere
```

- No filter flag → upgrade everything (matches current behavior).
- Filter flags combine as a union.
- `--drop` names are normalized (lower-case, `_`/`-` equivalent) and applied
  after filters.
- Unknown `--drop` names (not in the current upgrade set) emit a warning and
  are otherwise ignored.

## Snapshot & rollback

**Snapshot directory:** `.pcu/` at the project root.

- Created on each `-u` run, immediately before any file modification.
- Contains verbatim copies of whichever of these exist: `pyproject.toml`,
  `uv.lock`, `requirements.txt`.
- Added to `.gitignore` on first run if not already present. If `.gitignore`
  does not exist, it is created with a single `.pcu/` entry.
- Removed on exit, whether the run succeeded or failed (after restore, in the
  failure case). Recovery beyond that is the user's concern — commit history is
  the authoritative history.

**Upgrade flow:**

1. Read sources, fetch latest versions (unchanged).
2. Build the upgrade set.
3. Apply `--major`/`--minor`/`--patch`/`--pin` filter, then `--drop`
   exclusions.
4. If the resulting set is empty, print a message and exit cleanly — no
   snapshot, no sync.
5. Ensure `.pcu/` is in `.gitignore`.
6. Snapshot the relevant files into `.pcu/`.
7. Write updated content to `pyproject.toml` (and `requirements.txt` when
   both are managed).
8. Run `uv sync --all-extras` (or `pip install -r requirements.txt` for
   requirements-only projects). `subprocess.run` streams the tool's output
   directly, so uv/pip errors reach the user unchanged.
9. On non-zero exit:
   - Restore the snapshot files verbatim.
   - Delete `.pcu/`.
   - Print a short recovery hint pointing at `--drop` with the names we just
     attempted, so the user can copy-paste and retry.
   - Exit non-zero.
10. On success: run the existing verification step, delete `.pcu/`, print the
    success message, exit 0.

## Files touched

- `src/pcu/cli.py` — add `--major`, `--minor`, `--patch`, `--pin`, `--drop`.
- `src/pcu/upgrade.py` — filter logic, snapshot/restore, `.gitignore` check,
  recovery message.
- `src/pcu/deps.py` — small helpers (name normalization, snapshot paths) if
  needed; avoid churn.
- `README.md` — document new flags and the snapshot mechanism.

## Edge cases

- `.gitignore` missing → create with `.pcu/`.
- `.gitignore` already lists `.pcu` or `.pcu/` → leave alone.
- Filter flags given without `-u` → argparse-level error (flags are declared
  as requiring `-u`'s presence, or we validate in `main()` and exit with a
  clear message).
- `--drop` with a name not in the upgrade set → warn, continue.
- Filters + `--drop` produce an empty set → print "nothing to upgrade after
  filters" and exit 0.
- Snapshot write fails (disk full, permissions) → abort before touching real
  files; exit non-zero with the OS error.
- Restore fails during rollback → print both the original install error and
  the restore error; leave `.pcu/` in place so the user can recover manually.
