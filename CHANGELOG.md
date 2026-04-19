# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-04-19

### Added

- Transactional rollback for `pcu -u`. Before writing any changes, the tool
  snapshots `pyproject.toml`, `uv.lock`, and `requirements.txt` into `.pcu/`
  (auto-added to `.gitignore`). If `uv sync` or `pip install` fails, the
  snapshot is restored and a hint is printed suggesting `--drop` to exclude
  suspect packages on retry. `.pcu/` is cleaned up on success.
- `--drop pkg1 pkg2 ...` flag to exclude named packages from the upgrade set.
- `--major`, `--minor`, `--patch`, `--pin` filter flags for `pcu -u`
  (combinable as a union).
- Recovery hint after a failed upgrade listing the attempted package names.

### Changed

- The "nothing to upgrade" message now distinguishes between "all up to date"
  and "nothing after filters" when filter flags are used.

## [0.1.1] - 2026-04-06

### Fixed

- Documentation uses `uv tool install` for installation.
- `uv.lock` is now tracked.

## [0.1.0] - 2026-04-05

Initial release.
