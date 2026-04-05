from __future__ import annotations

import json
import subprocess
import tomllib
import urllib.error
import urllib.request
from pathlib import Path

PYPROJECT_PATH = Path("pyproject.toml")
REQUIREMENTS_PATH = Path("requirements.txt")


def parse_dependency(dep_string: str) -> tuple[str, str, str, str]:
    extras = ""
    name = dep_string.strip()

    if "[" in name:
        bracket_start = name.index("[")
        bracket_end = name.index("]")
        extras = name[bracket_start : bracket_end + 1]
        name = name[:bracket_start] + name[bracket_end + 1 :]

    for op in [">=", "==", "~=", "<=", "!=", "<", ">"]:
        if op in name:
            parts = name.split(op, 1)
            return parts[0].strip(), extras, op, parts[1].strip()

    return name.strip(), extras, "", ""


def _make_dep(dep_str: str, group: str) -> dict[str, str] | None:
    name, extras, op, version = parse_dependency(dep_str)
    if not name:
        return None
    return {
        "name": name,
        "extras": extras,
        "operator": op,
        "version": version,
        "group": group,
        "raw": dep_str.strip(),
    }


def get_all_dependencies(pyproject: dict[str, object]) -> list[dict[str, str]]:
    deps: list[dict[str, str]] = []
    project = pyproject.get("project", {})
    if not isinstance(project, dict):
        return deps

    for dep_str in project.get("dependencies", []):
        if d := _make_dep(str(dep_str), "dependencies"):
            deps.append(d)

    optional_deps = project.get("optional-dependencies", {})
    if isinstance(optional_deps, dict):
        for group_name, group_deps in optional_deps.items():
            if not isinstance(group_deps, list):
                continue
            for dep_str in group_deps:
                if d := _make_dep(str(dep_str), f"optional-dependencies.{group_name}"):
                    deps.append(d)

    dep_groups = pyproject.get("dependency-groups", {})
    if isinstance(dep_groups, dict):
        for group_name, group_deps in dep_groups.items():
            if not isinstance(group_deps, list):
                continue
            for dep_str in group_deps:
                if isinstance(dep_str, str):
                    if d := _make_dep(dep_str, f"dependency-groups.{group_name}"):
                        deps.append(d)

    return deps


def get_deps_from_requirements() -> list[dict[str, str]]:
    deps: list[dict[str, str]] = []
    for line in REQUIREMENTS_PATH.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        name, extras, op, version = parse_dependency(line)
        if d := _make_dep(line, "dependencies"):
            deps.append(d)
    return deps


def load_pyproject() -> dict[str, object]:
    return tomllib.loads(PYPROJECT_PATH.read_text())


def get_installed_versions() -> dict[str, str]:
    result = subprocess.run("uv pip list --format=json", shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        result = subprocess.run("pip list --format=json", shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        return {}
    try:
        packages = json.loads(result.stdout)
        return {p["name"].lower(): p["version"] for p in packages}
    except (json.JSONDecodeError, KeyError):
        return {}


def fetch_latest_version(package_name: str) -> str | None:
    url = f"https://pypi.org/pypi/{package_name}/json"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            return str(data["info"]["version"])
    except (urllib.error.URLError, json.JSONDecodeError, KeyError):
        return None


def version_tuple(v: str) -> tuple[int, ...]:
    parts: list[int] = []
    for p in v.split("."):
        digits = ""
        for ch in p:
            if ch.isdigit():
                digits += ch
            else:
                break
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def is_outdated(pinned: str, latest: str) -> bool:
    if not pinned or not latest:
        return False
    return version_tuple(pinned) < version_tuple(latest)


def classify_update(old: str, new: str) -> str:
    if not old or not new:
        return "none"
    o = version_tuple(old) + (0, 0, 0)
    n = version_tuple(new) + (0, 0, 0)
    if o >= n:
        return "none"
    if o[0] != n[0]:
        return "major"
    if o[1] != n[1]:
        return "minor"
    return "patch"


def detect_sources() -> tuple[bool, bool]:
    return PYPROJECT_PATH.exists(), REQUIREMENTS_PATH.exists()


def generate_requirements(pyproject: dict[str, object]) -> str:
    project = pyproject.get("project")
    if not isinstance(project, dict):
        return ""
    lines: list[str] = []
    for dep_str in project.get("dependencies", []):
        if isinstance(dep_str, str):
            lines.append(dep_str.strip())
    return "\n".join(sorted(lines)) + "\n"


def update_file_content(content: str, dep: dict[str, str], new_version: str, *, quoted: bool = True) -> str:
    old_str = dep["raw"]
    if dep["operator"] and dep["version"]:
        new_str = old_str.replace(f"{dep['operator']}{dep['version']}", f"{dep['operator']}{new_version}")
    else:
        new_str = f"{dep['name']}{dep['extras']}>={new_version}"

    if quoted:
        for quote in ['"', "'"]:
            quoted_old = f"{quote}{old_str}{quote}"
            if quoted_old in content:
                content = content.replace(quoted_old, f"{quote}{new_str}{quote}")
                return content

    return content.replace(old_str, new_str)
