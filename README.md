# python-check-updates

Check and upgrade Python dependency versions against PyPI.

## Install

```bash
pip install python-check-updates
```

## Usage

```bash
pcu          # check all dependencies for updates
pcu -u       # upgrade pinned versions and sync
```

## What it checks

- `pyproject.toml` — dependencies, optional-dependencies, dependency-groups
- `requirements.txt` — fallback if no pyproject.toml

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
