from __future__ import annotations

import sys

from pcu.deps import (
    classify_update,
    detect_sources,
    fetch_latest_version,
    get_all_dependencies,
    get_deps_from_requirements,
    get_installed_versions,
    is_outdated,
    load_pyproject,
)
from pcu.styles import BOLD, DIM, GREEN, RESET, UPDATE_STYLE, YELLOW


def cmd_check() -> None:
    print(f"\n{BOLD}Python Check Updates{RESET}")

    has_pyproject, has_requirements = detect_sources()
    if not has_pyproject and not has_requirements:
        print(f"\n  {BOLD}No pyproject.toml or requirements.txt found.{RESET}\n")
        sys.exit(1)

    if has_pyproject:
        print(f"{DIM}Checking pyproject.toml...{RESET}\n")
        deps = get_all_dependencies(load_pyproject())
    else:
        print(f"{DIM}Checking requirements.txt...{RESET}\n")
        deps = get_deps_from_requirements()

    if not deps:
        print("No dependencies found.")
        return

    installed = get_installed_versions()

    print(f"{DIM}Fetching latest versions...{RESET}\n")
    for dep in deps:
        dep["latest"] = fetch_latest_version(dep["name"]) or "?"
        dep["installed"] = installed.get(dep["name"].lower(), "—")

    name_w = max(max(len(d["name"] + d["extras"]) for d in deps) + 2, 10)
    pin_w = max(max(len(d["operator"] + d["version"]) for d in deps) + 2, 10)
    inst_w = max(max(len(d["installed"]) for d in deps) + 2, 12)
    lat_w = max(max(len(d["latest"]) for d in deps) + 2, 10)

    header = f"  {'Package':<{name_w}}{'Pinned':<{pin_w}}{'Installed':<{inst_w}}{'Latest':<{lat_w}}{'Status'}"
    print(f"{BOLD}{header}{RESET}")
    print(f"  {'─' * (name_w + pin_w + inst_w + lat_w + 16)}")

    update_count = 0
    pin_count = 0
    current_group: str | None = None

    for dep in deps:
        if dep["group"] != current_group:
            current_group = dep["group"]
            print(f"\n  {DIM}[{current_group}]{RESET}")

        name_display = dep["name"] + dep["extras"]
        pinned_display = dep["operator"] + dep["version"] if dep["version"] else "any"
        pin_behind = is_outdated(dep["version"], dep["latest"])
        inst_known = dep["installed"] not in ("—", "")
        inst_behind = inst_known and is_outdated(dep["installed"], dep["latest"])
        severity = classify_update(dep["version"], dep["latest"])

        if pin_behind and (inst_behind or not inst_known):
            update_count += 1
            color, label = UPDATE_STYLE.get(severity, (YELLOW, "update available"))
            status = f"{color}{label}{RESET}"
            latest_display = f"{color}{dep['latest']}{RESET}"
        elif pin_behind:
            pin_count += 1
            status = f"{DIM}pin outdated{RESET}"
            latest_display = f"{GREEN}{dep['latest']}{RESET}"
        else:
            status = f"{GREEN}up to date{RESET}"
            latest_display = f"{GREEN}{dep['latest']}{RESET}"

        inst_display = dep["installed"]
        if dep["installed"] != "—" and dep["latest"] != "?":
            if is_outdated(dep["installed"], dep["latest"]):
                color_i, _ = UPDATE_STYLE.get(classify_update(dep["installed"], dep["latest"]), (YELLOW, ""))
                inst_display = f"{color_i}{dep['installed']}{RESET}"
            else:
                inst_display = f"{GREEN}{dep['installed']}{RESET}"

        raw_latest = dep["latest"]
        raw_inst = dep["installed"]

        print(
            f"  {name_display:<{name_w}}"
            f"{pinned_display:<{pin_w}}"
            f"{inst_display}{' ' * (inst_w - len(raw_inst))}"
            f"{latest_display}{' ' * (lat_w - len(raw_latest))}"
            f"{status}"
        )

    print()
    if update_count:
        print(f"  {YELLOW}{update_count} package(s) can be updated.{RESET}")
    if pin_count:
        print(f"  {DIM}{pin_count} pin(s) can be bumped.{RESET}")
    if update_count or pin_count:
        print(f"  Run {BOLD}pcu -u{RESET} to upgrade.\n")
    else:
        print(f"  {GREEN}All pinned versions are up to date!{RESET}\n")
