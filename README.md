# python-check-updates

[![PyPI](https://img.shields.io/pypi/v/python-check-updates)](https://pypi.org/project/python-check-updates/)

Check and upgrade Python dependency versions against PyPI.

## Installation

```bash
uv tool install python-check-updates
```

## Usage

```bash
pcu          # check all dependencies for updates
pcu -u       # upgrade pinned versions and sync
```
It checks uv toml and fallback to requirements:
- `pyproject.toml` — dependencies, optional-dependencies, dependency-groups
- `requirements.txt` — dependencies

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
