import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import urlopen

try:
    from semantic_version import Version
except ImportError:
    Version = None


class SetupError(Exception):
    pass


PATCH_ADVISORY = (
    "A security patch is available for Teleport. Please upgrade your "
    "Cluster to v15.5.4 or newer."
)


def show_warnings(stderr):
    remaining = "\n".join(
        line for line in stderr.splitlines() if line.strip() != PATCH_ADVISORY
    ).strip()
    if remaining:
        print(remaining, file=sys.stderr)


def run_capture(command, timeout=15, *, include_stderr=False):
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise SetupError(
            f"Could not complete {command[0]}: {error}"
        ) from error
    if result.returncode != 0:
        raise SetupError(
            f"{command[0]} exited with status {result.returncode}; "
            "output withheld."
        )
    if (
        len(result.stdout.encode()) > 1_000_000
        or len(result.stderr.encode()) > 100_000
    ):
        raise SetupError(
            f"{command[0]} output exceeded the configured local limit."
        )
    if include_stderr:
        return result.stdout + "\n" + result.stderr
    show_warnings(result.stderr)
    return result.stdout


def run_interactive(command):
    try:
        result = subprocess.run(command, check=False)
    except OSError as error:
        raise SetupError(f"Could not start {command[0]}: {error}") from error
    if result.returncode != 0:
        raise SetupError(
            f"{command[0]} exited with status {result.returncode}; stopping."
        )


def establish_login(proxy, username, cluster=None):
    if cluster and cluster.startswith("-"):
        raise SetupError("Cluster name must not begin with '-'.")
    login_command = [
        "tsh", f"--proxy={proxy}", f"--user={username}",
        "login", "--request-roles=no",
    ]
    if cluster:
        login_command.append(cluster)
    print("Complete login and any password/MFA prompts in this terminal.")
    run_interactive(login_command)


def require_tsh_features():
    errors = []
    for subcommand in ("version", "status", "ls", "login", "ssh"):
        try:
            help_text = run_capture(
                ["tsh", subcommand, "--help"], include_stderr=True
            )
        except SetupError as error:
            errors.append(f"tsh {subcommand} help: {error}")
            continue
        if subcommand in ("version", "status", "ls") and (
            "--format" not in help_text or "json" not in help_text.lower()
        ):
            errors.append(
                f"Installed tsh {subcommand} does not advertise JSON output."
            )
        if subcommand == "version" and not any(
            flag in help_text for flag in ("--client", "--[no-]client")
        ):
            errors.append(
                "Installed tsh version does not advertise --client."
            )
        required = {
            "ls": ("--cluster",),
            "login": ("--proxy", "--user", "--request-roles"),
            "ssh": ("--request-mode",),
        }.get(subcommand, ())
        for flag in required:
            if flag not in help_text:
                errors.append(f"Installed tsh {subcommand} needs {flag}.")
    if errors:
        raise SetupError("\n".join(errors))


def find_named_string(document, accepted_names):
    matches = []

    def visit(value):
        if isinstance(value, dict):
            for key, child in value.items():
                normalized = re.sub(r"[^a-z]", "", key.lower())
                if normalized in accepted_names and isinstance(child, str):
                    matches.append(child)
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(document)
    matches = list(dict.fromkeys(matches))
    if len(matches) != 1:
        raise SetupError(
            "tsh version JSON has an unsupported client-version schema."
        )
    return matches[0]


def client_version():
    output = run_capture(
        ["tsh", "version", "--format=json", "--client"]
    )
    try:
        document = json.loads(output)
    except json.JSONDecodeError as error:
        raise SetupError("tsh version did not return valid JSON.") from error
    if isinstance(document, dict) and isinstance(document.get("version"), str):
        return document["version"]
    return find_named_string(
        document, {"client", "clientversion", "clientver"}
    )


def require_semantic_version():
    if Version is None:
        raise SetupError(
            "Missing semantic-version dependency. Run this script normally "
            "to bootstrap its dedicated virtual environment."
        )


def ensure_environment(directory):
    directory = directory.expanduser().absolute()
    if directory.is_symlink():
        raise SetupError("The dedicated venv must not be a symbolic link.")
    if not (directory / "pyvenv.cfg").is_file():
        if directory.exists() and any(directory.iterdir()):
            raise SetupError("The venv destination is not an empty directory.")
        print(f"Creating setup virtual environment at {directory}")
        try:
            run_capture(
                [sys.executable, "-m", "venv", str(directory)], timeout=120
            )
        except SetupError as error:
            raise SetupError(
                "Could not create the setup venv. Install venv support for "
                "this Python (python3-venv on Debian/Ubuntu), then rerun. "
                "No system packages were installed."
            ) from error
    python = directory / (
        "Scripts/python.exe" if os.name == "nt" else "bin/python"
    )
    probe = [
        str(python), "-c",
        "from importlib.metadata import version; "
        "from semantic_version import Version; "
        "assert Version('2.10.0') <= Version(version('semantic-version')) "
        "< Version('3.0.0')",
    ]
    try:
        run_capture(probe)
    except SetupError:
        print("Installing Python requirements into the setup venv.")
        try:
            run_capture([
                str(python), "-m", "pip", "install", "-r",
                str(Path(__file__).resolve().with_name("requirements.txt")),
            ], timeout=180)
            run_capture(probe)
        except SetupError as error:
            raise SetupError(
                "Could not install or verify venv dependencies. Check package "
                "index/network access and venv pip support, then rerun. "
                "System Python was not modified."
            ) from error
    return python


def check_local_prerequisites():
    errors = []
    if shutil.which("git") is None:
        errors.append(
            "Missing git executable, required for output safety checks."
        )
    for check in (require_semantic_version, require_tsh_features):
        try:
            check()
        except SetupError as error:
            errors.append(str(error))
    try:
        local = client_version()
        if Version is not None:
            Version(normalized_version(local))
    except (SetupError, ValueError) as error:
        errors.append(f"Could not verify local client version: {error}")
    if errors:
        raise SetupError(
            "Local preflight failed before requesting any details:\n- "
            + "\n- ".join(errors)
        )
    print(f"Local prerequisites verified; tsh client {local}.")
    return local


def validate_proxy(proxy):
    proxy = proxy.strip()
    try:
        parsed = urlsplit(proxy if "://" in proxy else f"https://{proxy}")
        hostname = parsed.hostname
        if (
            parsed.scheme != "https" or not hostname
            or parsed.path not in ("", "/")
            or any(character in proxy for character in "?#@\\")
            or any(character.isspace() for character in proxy)
            or parsed.netloc.endswith(":")
        ):
            raise ValueError
        if ":" not in hostname and not all(
            re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
            for label in hostname.split(".")
        ):
            raise ValueError
        port = parsed.port if parsed.port is not None else 443
        if port == 0:
            raise ValueError
    except ValueError as error:
        raise SetupError(
            "Use a hostname or HTTPS URL, e.g. teleport.example.com "
            "or https://teleport.example.com:443, without credentials, "
            "paths, queries, or fragments. The default HTTPS port is 443."
        ) from error
    host = f"[{hostname}]" if ":" in hostname else hostname
    return f"{host}:{port}"


def ask_proxy(default=None):
    while True:
        try:
            proxy = input(
                "Approved Teleport proxy (e.g. teleport.example.com or "
                "https://teleport.example.com:443; default port 443)"
                + (f" [{default}]" if default else "") + ": "
            ).strip() or default or ""
            return validate_proxy(proxy)
        except SetupError as error:
            print(f"Invalid proxy: {error}")


def get_proxy_versions(proxy):
    endpoint = f"https://{proxy}/webapi/find"
    try:
        with urlopen(endpoint, timeout=15) as response:
            if response.geturl() != endpoint:
                raise SetupError(
                    "Proxy version metadata redirected; stopping."
                )
            payload = response.read(1_000_001)
            if len(payload) > 1_000_000:
                raise SetupError(
                    "Proxy version metadata exceeded the size limit."
                )
            document = json.loads(payload)
    except (OSError, URLError, json.JSONDecodeError) as error:
        raise SetupError(
            "Could not securely retrieve valid proxy version metadata; "
            "stopping."
        ) from error
    if not isinstance(document, dict):
        raise SetupError("Proxy version metadata is not a JSON object.")
    server = document.get("server_version")
    minimum = document.get("min_client_version")
    if not isinstance(server, str) or not isinstance(minimum, str):
        raise SetupError(
            "Proxy version metadata is missing required version fields."
        )
    return server, minimum


def normalized_version(value):
    return value[1:] if value.startswith("v") else value


def check_version_gate(local, server, minimum):
    require_semantic_version()
    local_normalized = normalized_version(local)
    server_normalized = normalized_version(server)
    minimum_normalized = normalized_version(minimum)
    try:
        local_parsed = Version(local_normalized)
        server_parsed = Version(server_normalized)
        minimum_parsed = Version(minimum_normalized)
    except ValueError as error:
        raise SetupError(
            "A Teleport version is not valid semantic version data."
        ) from error
    if minimum_parsed > server_parsed:
        raise SetupError(
            "Proxy version metadata is inconsistent: minimum exceeds server."
        )
    if local_parsed < minimum_parsed:
        raise SetupError(
            f"Version gate failed: client {local} is below minimum {minimum}."
        )
    local_major = int(local_normalized.split(".")[0])
    server_major = int(server_normalized.split(".")[0])
    if local_major not in (server_major, server_major - 1):
        raise SetupError(
            "Unsupported major version: tsh must match the proxy's major "
            "version or be one major behind, and meet the minimum."
        )


def parse_json_command(command):
    output = run_capture(command)
    try:
        return json.loads(output)
    except json.JSONDecodeError as error:
        raise SetupError(
            f"{command[0]} {command[-1]} returned invalid JSON."
        ) from error


def extract_logins(document):
    logins = document.get("logins") if isinstance(document, dict) else None
    if not isinstance(logins, list) or not all(
        isinstance(login, str) for login in logins
    ):
        raise SetupError(
            "tsh status JSON has an unsupported allowed-logins schema."
        )
    return sorted({login for login in logins if login})


def active_session(document):
    profile = document.get("active") if isinstance(document, dict) else None
    if not isinstance(profile, dict):
        return None
    try:
        expires = datetime.fromisoformat(
            profile["valid_until"].replace("Z", "+00:00")
        )
        if expires.tzinfo is None or expires <= datetime.now(timezone.utc):
            return None
        proxy = validate_proxy(profile["profile_url"])
        username = profile["username"]
        cluster = profile["cluster"]
        if not all(isinstance(value, str) and value for value in (
            username, cluster,
        )):
            return None
        return {
            "proxy": proxy, "teleportUser": username, "cluster": cluster,
            "valid_until": expires.astimezone(timezone.utc).isoformat(),
            "logins": extract_logins({"logins": profile.get("logins", [])}),
        }
    except (KeyError, ValueError, TypeError, AttributeError, SetupError):
        return None


def read_session():
    try:
        result = subprocess.run(
            ["tsh", "status", "--format=json"], check=False,
            capture_output=True, text=True, timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise SetupError(
            "Could not check tsh status; no login attempted."
        ) from error
    if (
        len(result.stdout.encode()) > 1_000_000
        or len(result.stderr.encode()) > 100_000
    ):
        raise SetupError("tsh status output exceeded the local limit.")
    if result.returncode != 0:
        if any(message in result.stderr for message in (
            "Not logged in.", "Active profile expired.",
        )):
            return None
        raise SetupError(
            f"tsh status failed with status {result.returncode}; "
            "resolve the status error in your terminal before retrying."
        )
    show_warnings(result.stderr)
    try:
        return active_session(json.loads(result.stdout))
    except json.JSONDecodeError as error:
        raise SetupError("tsh status did not return valid JSON.") from error


def read_preferences(path):
    if path.is_symlink():
        raise SetupError("Private preferences must not be a symbolic link.")
    if not path.exists():
        return {}
    if path.stat().st_size > 100_000:
        raise SetupError("Private preferences exceed the size limit.")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError) as error:
        raise SetupError("Private preferences must be valid JSON.") from error
    if not isinstance(document, dict):
        raise SetupError("Private preferences must be a JSON object.")
    if "environments" in document:
        print("Legacy environment inventory preserved but no longer required.")
        return {}
    return {
        key: document[key] for key in ("proxy", "teleportUser")
        if isinstance(document.get(key), str) and document[key]
    }


def list_nodes(session):
    nodes = parse_json_command([
        "tsh", f"--proxy={session['proxy']}", "ls",
        f"--cluster={session['cluster']}", "--format=json",
    ])
    if not isinstance(nodes, list):
        raise SetupError("tsh ls returned an unsupported node-list schema.")
    discovered_at = datetime.now(timezone.utc).isoformat()
    print(
        f"\nVisible SSH nodes discovered at {discovered_at} "
        "(access is enforced by Teleport):"
    )
    for node in nodes:
        if not isinstance(node, dict):
            raise SetupError("tsh ls returned an invalid node entry.")
        metadata = node.get("metadata", {})
        spec = node.get("spec", {})
        if not isinstance(metadata, dict) or not isinstance(spec, dict):
            raise SetupError("tsh ls returned invalid node metadata.")
        name = spec.get("hostname") or metadata.get("name")
        node_id = metadata.get("id") or metadata.get("name")
        labels = metadata.get("labels", {})
        if not isinstance(name, str) or not isinstance(labels, dict):
            raise SetupError("tsh ls returned invalid node names or labels.")
        print(
            f"  {json.dumps(name)}  {json.dumps(node_id)}  "
            f"{json.dumps(labels, sort_keys=True)}"
        )
    if not nodes:
        print("  No nodes visible in the selected cluster.")
    return nodes


def ask_yes_no(prompt):
    while True:
        answer = input(f"{prompt} [y/n]: ").strip().lower()
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no"}:
            return False
        print("Enter y or n.")


def default_skills_directory():
    if os.name != "nt" and (
        os.environ.get("WSL_DISTRO_NAME") or os.environ.get("WSL_INTEROP")
    ):
        try:
            profile = run_capture(
                ["cmd.exe", "/d", "/c", "echo", "%USERPROFILE%"]
            ).strip()
            if (
                not PureWindowsPath(profile).is_absolute()
                or "\n" in profile or "\r" in profile
            ):
                raise SetupError("Invalid Windows profile path.")
            home = Path(run_capture(["wslpath", "-u", profile]).strip())
            if not home.is_absolute():
                raise SetupError("Invalid translated Windows profile path.")
        except SetupError as error:
            raise SetupError(
                "Could not locate the Windows host skills folder. "
                "Pass --skills-dir with its WSL path explicitly."
            ) from error
    else:
        home = Path.home()
    return home / ".copilot" / "skills"


def install_skill(source, skills_directory):
    source = source.resolve()
    skills_directory = skills_directory.expanduser().absolute()
    destination = skills_directory / source.name
    for parent in (destination, *destination.parents):
        if parent.is_symlink():
            raise SetupError(f"Symbolic installation path refused: {parent}")
    destination = destination.resolve()
    if destination == source:
        return destination
    if source in destination.parents or destination in source.parents:
        raise SetupError("Source and installation directories overlap.")

    def excluded(directory, names):
        ignored = {
            name for name in names
            if name in {"__pycache__", ".venv"}
            or name.endswith((".pyc", ".pyo"))
        }
        if Path(directory) == source / "assets":
            ignored.add("environment.json")
        return ignored

    for directory, directories, filenames in os.walk(source):
        ignored = excluded(directory, directories + filenames)
        directories[:] = [name for name in directories if name not in ignored]
        for name in directories + filenames:
            if name in ignored:
                continue
            path = Path(directory) / name
            target = destination / path.relative_to(source)
            if path.is_symlink() or target.is_symlink():
                raise SetupError(f"Symbolic skill path refused: {path}")
    shutil.copytree(
        source, destination, dirs_exist_ok=True, ignore=excluded
    )
    print(f"Installed skill files to {destination}")
    return destination


def find_git_root(directory):
    directory = directory.expanduser().resolve()
    while not directory.exists():
        directory = directory.parent
    result = subprocess.run(
        ["git", "-C", str(directory), "rev-parse", "--show-toplevel"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip()).resolve()


def validate_output_path(output, git_root):
    resolved = output.expanduser().resolve()
    if resolved.exists():
        raise SetupError(f"Refusing to overwrite existing file: {resolved}")
    if git_root is None:
        return resolved
    try:
        relative = resolved.relative_to(git_root)
    except ValueError:
        return resolved
    result = subprocess.run(
        [
            "git",
            "-C",
            str(git_root),
            "check-ignore",
            "--quiet",
            "--",
            str(relative),
        ],
        check=False,
    )
    if result.returncode != 0:
        raise SetupError("Output inside the workspace must be Git-ignored.")
    return resolved


def write_private_json(output, document):
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        descriptor = os.open(
            output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
        )
    except FileExistsError as error:
        raise SetupError(
            f"Refusing to overwrite existing file: {output}"
        ) from error
    with os.fdopen(descriptor, "w", encoding="utf-8") as file:
        json.dump(document, file, indent=2)
        file.write("\n")
        file.flush()
        os.fsync(file.fileno())


def run_setup(output_argument, skills_directory=None):
    if not sys.stdin.isatty():
        raise SetupError(
            "Run this setup interactively from the prepared clean Bash "
            "terminal."
        )
    local = check_local_prerequisites()
    installed = install_skill(
        Path(__file__).resolve().parents[1],
        Path(skills_directory)
        if skills_directory else default_skills_directory(),
    )
    output = (
        Path(output_argument)
        if output_argument
        else installed / "assets/environment.json"
    )
    preferences = read_preferences(output)
    if not output.exists():
        output = validate_output_path(output, find_git_root(output.parent))
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.TemporaryFile(dir=output.parent) as probe:
        probe.write(b"\0")
        probe.flush()

    session = read_session()
    reuse = False
    if session:
        print("Current session: " + json.dumps({
            key: session[key] for key in (
                "proxy", "teleportUser", "cluster", "valid_until",
            )
        }))
        reuse = ask_yes_no("Use this session for setup and node discovery?")
    if reuse:
        proxy = session["proxy"]
        username = session["teleportUser"]
    else:
        proxy = ask_proxy(preferences.get("proxy"))
        default_user = preferences.get("teleportUser", "")
        username = ""
        while not username:
            username = input(
                "Teleport username"
                + (f" [{default_user}]" if default_user else "")
                + ": "
            ).strip() or default_user

    server, minimum = get_proxy_versions(proxy)
    print(f"Client: {local}; server: {server}; minimum client: {minimum}")
    check_version_gate(local, server, minimum)
    print("Client/proxy compatibility checks passed.")
    if not reuse:
        establish_login(proxy, username)
        session = read_session()
        if (
            not session or session["proxy"] != proxy
            or session["teleportUser"] != username
        ):
            raise SetupError(
                "Login did not establish the requested valid session."
            )
    print("Session details: " + json.dumps({
        key: session[key] for key in ("valid_until", "logins")
    }))
    list_nodes(session)
    if not output.exists() and ask_yes_no(
        "Remember proxy and username as optional connection preferences?"
    ):
        write_private_json(output, {"proxy": proxy, "teleportUser": username})
        print(f"Saved connection preferences to {output}")
    print(
        "Setup complete. Permissions remain in Teleport; no SSH was executed."
    )


def main():
    parser = argparse.ArgumentParser(
        description="Install the Teleport skill and set up interactive login."
    )
    parser.add_argument(
        "--skills-dir",
        help="Personal skills root (default: ~/.copilot/skills on the host; "
        "WSL uses the Windows user profile).",
    )
    parser.add_argument(
        "--output",
        help="Optional preferences path (default: installed skill's "
        "assets/environment.json); existing files are preserved.",
    )
    parser.add_argument(
        "--venv-dir", type=Path,
        default=Path.home() / ".local/share/teleport-tsh/.venv",
        help="Dedicated setup venv in the current Python/WSL environment.",
    )
    arguments = parser.parse_args()
    try:
        if not sys.stdin.isatty():
            raise SetupError(
                "Run setup interactively in the prepared terminal."
            )
        missing = [
            name for name in ("tsh", "git") if shutil.which(name) is None
        ]
        if missing:
            raise SetupError(
                "Missing system prerequisites: " + ", ".join(missing)
                + ". Install them using official guidance, then rerun."
            )
        require_tsh_features()
        python = ensure_environment(arguments.venv_dir)
        if (
            Path(sys.prefix).resolve()
            != arguments.venv_dir.expanduser().resolve()
            or Version is None
        ):
            return subprocess.run([
                str(python), str(Path(__file__).resolve()), *sys.argv[1:],
            ], check=False).returncode
        run_setup(arguments.output, arguments.skills_dir)
    except (SetupError, OSError, shutil.Error) as error:
        print(f"Stopped: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
