#!/usr/bin/env python3
"""Preview or synchronize repository skills to personal skill roots."""

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
import tempfile


REPOSITORY = Path(__file__).resolve().parents[1]
STATE_DIRECTORY = ".skill-sync-state"
EXCLUDED_DIRECTORIES = {"__pycache__", "node_modules", "dist", "coverage"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".pem", ".key", ".p12", ".pfx", ".skill"}


class SyncError(Exception):
    pass


def validate_source(source):
    validator_path = (
        REPOSITORY / "skills" / "skill-creator" / "scripts"
        / "quick_validate.py"
    )
    specification = importlib.util.spec_from_file_location(
        "skill_sync_validator", validator_path
    )
    validator = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(validator)
    valid, message = validator.validate_skill(source)
    if not valid:
        raise SyncError(f"Invalid skill {source.name}: {message}")
    content = (source / "SKILL.md").read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    frontmatter = validator.yaml.safe_load(match.group(1))
    if frontmatter["name"] != source.name:
        raise SyncError(f"Skill name must match directory: {source}")


def excluded(relative):
    return (
        any(
            part.startswith(".") or part in EXCLUDED_DIRECTORIES
            for part in relative.parts
        )
        or relative.suffix.lower() in EXCLUDED_SUFFIXES
        or relative.name in {"id_rsa", "id_ed25519"}
    )


def fail_inventory(error):
    message = f"Cannot inspect source or destination: {error}"
    raise SyncError(message) from error


def inventory(directory, source=False):
    if directory.is_symlink():
        raise SyncError(f"Symbolic links are not supported: {directory}")
    if not directory.exists():
        return {}
    if not directory.is_dir():
        raise SyncError(f"Expected a directory: {directory}")
    files = {}
    folded_names = set()
    entries = os.walk(
        directory, followlinks=False, onerror=fail_inventory
    )
    for current, directories, filenames in entries:
        parent = Path(current)
        for name in list(directories):
            path = parent / name
            relative = path.relative_to(directory)
            if source and excluded(relative):
                directories.remove(name)
            elif path.is_symlink():
                raise SyncError(f"Symbolic links are not supported: {path}")
        for name in sorted(filenames):
            path = parent / name
            relative = path.relative_to(directory)
            if source and excluded(relative):
                continue
            if path.is_symlink() or not path.is_file():
                raise SyncError(
                    "Symbolic links and special files are not supported: "
                    f"{path}"
                )
            key = relative.as_posix()
            if key.casefold() in folded_names:
                raise SyncError(f"Case-insensitive path collision: {path}")
            folded_names.add(key.casefold())
            files[key] = hashlib.sha256(path.read_bytes()).hexdigest()
    return files


def manifest_path(destination_root, name):
    state_root = destination_root / STATE_DIRECTORY
    path = state_root / f"{name}.json"
    if state_root.is_symlink() or path.is_symlink():
        raise SyncError(f"Symbolic state paths are not supported: {path}")
    return path


def load_manifest(path):
    if not path.exists():
        return None
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(state, dict) or state.get("schema_version") != 1:
            raise ValueError("unsupported manifest schema")
        files = state["files"]
        if not isinstance(files, dict) or "SKILL.md" not in files:
            raise ValueError("missing file hashes")
        for name, digest in files.items():
            relative = PurePosixPath(name)
            if (
                relative.is_absolute()
                or ".." in relative.parts
                or "\\" in name
            ):
                raise ValueError("invalid manifest path")
            if not isinstance(digest, str) or not re.fullmatch(
                r"[a-f0-9]{64}", digest
            ):
                raise ValueError("invalid file hash")
        return state
    except (ValueError, KeyError, TypeError) as error:
        raise SyncError(f"Invalid manifest {path}: {error}") from error


def differing_paths(first, second):
    return sorted(
        name for name in first.keys() | second.keys()
        if first.get(name) != second.get(name)
    )


def make_plan(source, destination_root):
    if destination_root.is_symlink():
        raise SyncError(
            f"Symbolic destination roots are not supported: {destination_root}"
        )
    destination = destination_root / source.name
    if destination.is_symlink():
        raise SyncError(
            f"Symbolic destination skills are not supported: {destination}"
        )
    resolved_source = source.resolve()
    resolved_destination = destination.resolve()
    if (
        resolved_source == resolved_destination
        or resolved_source in resolved_destination.parents
        or resolved_destination in resolved_source.parents
    ):
        raise SyncError(
            f"Source and destination overlap: {source}, {destination}"
        )
    desired = inventory(source, source=True)
    installed = inventory(destination)
    state_path = manifest_path(destination_root, source.name)
    previous = load_manifest(state_path)
    if previous is None:
        if destination.exists() and installed != desired:
            differences = ", ".join(differing_paths(installed, desired))
            raise SyncError(
                f"Refusing unmanaged differing installation {destination}: "
                f"{differences}"
            )
        action = "ADOPT" if destination.exists() else "INSTALL"
    else:
        if installed != previous["files"] and installed != desired:
            differences = ", ".join(
                differing_paths(installed, previous["files"])
            )
            raise SyncError(f"Local changes in {destination}: {differences}")
        action = (
            "CURRENT"
            if installed == desired and previous["files"] == desired
            else "UPDATE"
        )
    return {
        "source": source,
        "destination": destination,
        "state_path": state_path,
        "previous": previous,
        "desired": desired,
        "installed": installed,
        "action": action,
    }


def write_manifest(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".manifest-", dir=path.parent
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(content, stream, indent=2, sort_keys=True)
            stream.write("\n")
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def apply_plan(plan):
    if plan["action"] == "CURRENT":
        return
    source = plan["source"]
    destination = plan["destination"]
    state_path = plan["state_path"]
    if (
        inventory(source, source=True) != plan["desired"]
        or inventory(destination) != plan["installed"]
        or load_manifest(state_path) != plan["previous"]
    ):
        raise SyncError(
            f"Files changed after preview; retry preview: {destination}"
        )
    state = {
        "schema_version": 1,
        "source": str(source.resolve()),
        "files": plan["desired"],
    }
    if plan["action"] == "ADOPT":
        write_manifest(state_path, state)
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging_directory = tempfile.TemporaryDirectory(
        prefix=".skill-sync-", dir=destination.parent
    )
    with staging_directory as staging_name:
        staging = Path(staging_name)
        replacement = staging / "replacement"
        replacement.mkdir()
        for relative in plan["desired"]:
            target = replacement / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / relative, target)
        if inventory(replacement) != plan["desired"]:
            raise SyncError(f"Source changed during copy: {source}")
        backup = staging / "previous"
        had_destination = destination.exists()
        if had_destination:
            destination.rename(backup)
        try:
            replacement.rename(destination)
            write_manifest(state_path, state)
        except OSError:
            if destination.exists():
                shutil.rmtree(destination)
            if had_destination:
                backup.rename(destination)
            raise


def sync_skills(source_root, names, destinations, apply=False):
    source_root = Path(source_root)
    sources = []
    for name in sorted(set(names)):
        if len(name) > 64 or not re.fullmatch(
            r"[a-z0-9]+(?:-[a-z0-9]+)*", name
        ):
            raise SyncError(f"Invalid skill name: {name}")
        source = source_root / name
        inventory(source, source=True)
        validate_source(source)
        sources.append(source)
    roots = list(dict.fromkeys(
        Path(root).expanduser().absolute() for root in destinations
    ))
    plans = [make_plan(source, root) for root in roots for source in sources]
    messages = []
    for plan in plans:
        changed = differing_paths(plan["installed"], plan["desired"])
        details = f" ({', '.join(changed)})" if changed else ""
        messages.append(f"{plan['action']} {plan['destination']}{details}")
    if apply:
        for plan in plans:
            apply_plan(plan)
    return messages


def main(arguments=None):
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument(
        "--skill", action="append",
        help="Skill directory name; repeat for several skills",
    )
    selection.add_argument(
        "--all", action="store_true",
        help="Select every top-level source skill",
    )
    parser.add_argument(
        "--source-root", type=Path, default=REPOSITORY / "skills"
    )
    parser.add_argument(
        "--destination", action="append", type=Path,
        help="Skills root; repeat for Windows/WSL installs",
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="Apply the plan; default is read-only preview",
    )
    options = parser.parse_args(arguments)
    try:
        names = options.skill
        if options.all:
            names = sorted(
                path.name for path in options.source_root.iterdir()
                if (path / "SKILL.md").is_file()
            )
        if not names:
            raise SyncError("No source skills selected")
        messages = sync_skills(
            options.source_root,
            names,
            options.destination or [Path.home() / ".copilot" / "skills"],
            apply=options.apply,
        )
        print("\n".join(messages))
        print(
            "Applied. Start a new Copilot chat to load updated skills."
            if options.apply
            else "Preview only. Add --apply to write changes."
        )
        return 0
    except (SyncError, OSError, ImportError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
