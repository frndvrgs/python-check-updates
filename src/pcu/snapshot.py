from __future__ import annotations

import shutil
from pathlib import Path

SNAPSHOT_DIR = Path(".pcu")
GITIGNORE_PATH = Path(".gitignore")
GITIGNORE_ENTRY = ".pcu/"


def ensure_gitignore() -> None:
    """Add .pcu/ to .gitignore if not already listed, ensuring a trailing newline."""
    if not GITIGNORE_PATH.exists():
        GITIGNORE_PATH.write_text(GITIGNORE_ENTRY + "\n")
        return
    text = GITIGNORE_PATH.read_text()
    stripped = {line.strip().rstrip("/") for line in text.splitlines()}
    if ".pcu" in stripped:
        return
    if text and not text.endswith("\n"):
        text += "\n"
    GITIGNORE_PATH.write_text(text + GITIGNORE_ENTRY + "\n")


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
