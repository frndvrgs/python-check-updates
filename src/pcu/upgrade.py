from __future__ import annotations

import subprocess
import sys
import tomllib

from pcu.deps import (
    PYPROJECT_PATH,
    REQUIREMENTS_PATH,
    classify_update,
    detect_sources,
    fetch_latest_version,
    generate_requirements,
    get_all_dependencies,
    get_deps_from_requirements,
    get_installed_versions,
    is_outdated,
    load_pyproject,
    update_file_content,
)
from pcu.styles import BOLD, DIM, GREEN, RED, RESET, UPDATE_STYLE, YELLOW


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


def cmd_upgrade(severities: set[str] | None = None, drops: list[str] | None = None) -> None:
    severities = severities or set()
    drops = drops or []

    print(f"\n{BOLD}Python Check Updates{RESET}")
    print(f"{DIM}Upgrading dependencies...{RESET}\n")

    has_pyproject, has_requirements = detect_sources()
    if not has_pyproject and not has_requirements:
        print(f"\n  {RED}No pyproject.toml or requirements.txt found.{RESET}\n")
        sys.exit(1)

    if has_pyproject:
        deps = get_all_dependencies(load_pyproject())
    else:
        deps = get_deps_from_requirements()

    if not deps:
        print("No dependencies found.")
        return

    installed = get_installed_versions()

    print(f"{DIM}Fetching latest versions...{RESET}\n")
    for dep in deps:
        dep["latest"] = fetch_latest_version(dep["name"]) or ""
        dep["installed"] = installed.get(dep["name"].lower(), "")

    to_update = [d for d in deps if d["latest"] and is_outdated(d["version"], d["latest"])]

    to_update, unknown_drops = _apply_filters(to_update, installed, severities, drops)
    if unknown_drops:
        print(f"  {YELLOW}Warning: --drop names not in upgrade set: {', '.join(unknown_drops)}{RESET}\n")

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

    print(f"  {BOLD}Updating pinned versions:{RESET}\n")
    name_w = max(len(d["name"] + d["extras"]) for d in to_update) + 2

    if has_pyproject:
        content = PYPROJECT_PATH.read_text()
        for dep in to_update:
            name_display = dep["name"] + dep["extras"]
            old_v = dep["operator"] + dep["version"] if dep["version"] else "any"
            new_v = dep["operator"] + dep["latest"] if dep["operator"] else ">=" + dep["latest"]
            severity = classify_update(dep["version"], dep["latest"])
            color, _ = UPDATE_STYLE.get(severity, (YELLOW, ""))
            content = update_file_content(content, dep, dep["latest"], quoted=True)
            print(f"  {name_display:<{name_w}} {color}{old_v}{RESET} -> {GREEN}{new_v}{RESET}")
        PYPROJECT_PATH.write_text(content)
        print(f"\n  Updated {BOLD}pyproject.toml{RESET}")

        if has_requirements:
            updated_pyproject = tomllib.loads(content)
            REQUIREMENTS_PATH.write_text(generate_requirements(updated_pyproject))
            print(f"  Updated {BOLD}requirements.txt{RESET}")
    else:
        content = REQUIREMENTS_PATH.read_text()
        for dep in to_update:
            name_display = dep["name"] + dep["extras"]
            old_v = dep["operator"] + dep["version"] if dep["version"] else "any"
            new_v = dep["operator"] + dep["latest"] if dep["operator"] else ">=" + dep["latest"]
            severity = classify_update(dep["version"], dep["latest"])
            color, _ = UPDATE_STYLE.get(severity, (YELLOW, ""))
            content = update_file_content(content, dep, dep["latest"], quoted=False)
            print(f"  {name_display:<{name_w}} {color}{old_v}{RESET} -> {GREEN}{new_v}{RESET}")
        REQUIREMENTS_PATH.write_text(content)
        print(f"\n  Updated {BOLD}requirements.txt{RESET}")

    if has_pyproject:
        print(f"\n{DIM}Running uv sync --all-extras...{RESET}\n")
        result = subprocess.run("uv sync --all-extras", shell=True)
    else:
        print(f"\n{DIM}Running pip install -r requirements.txt...{RESET}\n")
        result = subprocess.run("pip install -r requirements.txt", shell=True)

    if result.returncode != 0:
        print(f"\n  {RED}Sync failed.{RESET}")
        sys.exit(1)

    print(f"\n{DIM}Verifying...{RESET}\n")
    new_installed = get_installed_versions()

    all_good = True
    for dep in to_update:
        name_display = dep["name"] + dep["extras"]
        new_inst = new_installed.get(dep["name"].lower(), "?")
        if is_outdated(new_inst, dep["latest"]):
            print(f"  {RED}!{RESET} {name_display}: installed {new_inst}, expected {dep['latest']}")
            all_good = False
        else:
            print(f"  {GREEN}+{RESET} {name_display}: {new_inst}")

    print()
    if all_good:
        print(f"  {GREEN}Upgrade complete!{RESET}\n")
    else:
        print(f"  {YELLOW}Some packages may not have updated to the exact latest version.{RESET}\n")
