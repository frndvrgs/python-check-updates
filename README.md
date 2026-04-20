# python-check-updates

[![PyPI](https://img.shields.io/pypi/v/python-check-updates)](https://pypi.org/project/python-check-updates/)

Check and upgrade Python dependency versions against PyPI.

## Installation

```bash
uv tool install python-check-updates
```

To upgrade an existing install to the latest version:

```bash
uv tool upgrade python-check-updates
```

Run `pcu -v` to check the installed version.

## Usage

```bash
pcu          # check all dependencies for updates
pcu -u       # upgrade pinned versions and sync
```
It checks uv toml and fallback to requirements:
- `pyproject.toml` — dependencies, optional-dependencies, dependency-groups
- `requirements.txt` — dependencies

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

Before touching `pyproject.toml`, `uv.lock`, or `requirements.txt`, `pcu` snapshots the current contents into `.pcu/` (which is auto-added to `.gitignore`). If `uv sync` or `pip install` fails, the snapshot is restored and a hint is printed suggesting `--drop` to exclude suspect packages on retry. On success, `.pcu/` is cleaned up.

## Output

```
  Package       Pinned    Installed   Latest    Status
  ─────────────────────────────────────────────────────

  [dependencies]
  httpx         >=0.28.1  0.28.1      0.28.3    minor update
  pydantic      >=2.12.5  2.12.5      2.12.5    up to date

  1 package(s) can be updated.
  Run pcu -u to upgrade.
```

Upgrade rewrites version pins in-place, syncs with `uv sync` or `pip install`, and verifies.

## License

MIT
