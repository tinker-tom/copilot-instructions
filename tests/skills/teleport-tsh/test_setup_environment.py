import importlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(
    0, str(REPO_ROOT / "skills" / "teleport-tsh" / "scripts")
)

setup_environment = importlib.import_module("setup_environment")


class FakeVersion:
    def __init__(self, value):
        parts = value.split(".")
        if len(parts) != 3 or not all(part.isdigit() for part in parts):
            raise ValueError(value)
        self.parts = tuple(int(part) for part in parts)

    def __lt__(self, other):
        return self.parts < other.parts

    def __gt__(self, other):
        return self.parts > other.parts


class SetupEnvironmentTests(unittest.TestCase):
    def test_patch_advisory_does_not_hide_other_warnings(self):
        with patch("sys.stderr", new_callable=io.StringIO) as stderr:
            setup_environment.show_warnings(
                setup_environment.PATCH_ADVISORY + "\nOther warning\n"
            )
        self.assertEqual(stderr.getvalue(), "Other warning\n")

    def test_patch_advisory_does_not_make_failed_commands_successful(self):
        result = type("Result", (), {
            "returncode": 1, "stdout": "",
            "stderr": setup_environment.PATCH_ADVISORY,
        })()
        with patch.object(
            setup_environment.subprocess, "run", return_value=result
        ):
            with self.assertRaisesRegex(
                setup_environment.SetupError, "status 1"
            ):
                setup_environment.run_capture(["tsh", "ls"])

    def test_cli_relaunches_in_venv_with_original_arguments(self):
        with tempfile.TemporaryDirectory() as directory:
            venv = Path(directory) / ".venv"
            python = venv / "bin/python"
            arguments = ["--venv-dir", str(venv), "--skills-dir", directory]
            result = type("Result", (), {"returncode": 7})()
            with (
                patch.object(
                    sys, "argv", ["setup_environment.py", *arguments]
                ),
                patch.object(sys, "prefix", "/different-interpreter"),
                patch.object(sys.stdin, "isatty", return_value=True),
                patch.object(
                    setup_environment.shutil, "which", return_value="present"
                ),
                patch.object(setup_environment, "require_tsh_features"),
                patch.object(
                    setup_environment, "ensure_environment",
                    return_value=python,
                ),
                patch.object(
                    setup_environment.subprocess, "run", return_value=result
                ) as run,
                patch.object(setup_environment, "run_setup") as setup,
            ):
                self.assertEqual(setup_environment.main(), 7)
            self.assertEqual(run.call_args.args[0][0], str(python))
            self.assertEqual(run.call_args.args[0][2:], arguments)
            setup.assert_not_called()

    def test_legacy_inventory_is_ignored_and_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "environment.json"
            setup_environment.write_private_json(
                path, {"environments": [{"name": "old-private-context"}]}
            )
            original = path.read_bytes()
            self.assertEqual(setup_environment.read_preferences(path), {})
            self.assertEqual(path.read_bytes(), original)

    def test_preferences_load_only_connection_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "environment.json"
            setup_environment.write_private_json(path, {
                "proxy": "teleport.example.com:443",
                "teleportUser": "example.user", "roles": ["not-authority"],
            })
            self.assertEqual(setup_environment.read_preferences(path), {
                "proxy": "teleport.example.com:443",
                "teleportUser": "example.user",
            })

    def test_bootstrap_creates_venv_and_installs_only_its_dependencies(self):
        with tempfile.TemporaryDirectory() as directory:
            venv = Path(directory) / ".venv"
            with patch.object(
                setup_environment, "run_capture",
                side_effect=[
                    "", setup_environment.SetupError("missing dependency"),
                    "", "",
                ],
            ) as capture:
                python = setup_environment.ensure_environment(venv)
            commands = [call.args[0] for call in capture.call_args_list]
            self.assertEqual(commands[0], [
                sys.executable, "-m", "venv", str(venv),
            ])
            self.assertEqual(commands[2][:5], [
                str(python), "-m", "pip", "install", "-r",
            ])
            self.assertEqual(commands[1], commands[3])

    def test_bootstrap_reuses_ready_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            venv = Path(directory)
            (venv / "pyvenv.cfg").touch()
            with patch.object(
                setup_environment, "run_capture", return_value=""
            ) as capture:
                setup_environment.ensure_environment(venv)
            self.assertEqual(capture.call_count, 1)
            self.assertNotIn("pip", capture.call_args.args[0])

    def test_bootstrap_reports_missing_venv_without_prompting(self):
        with tempfile.TemporaryDirectory() as directory:
            with (
                patch.object(
                    setup_environment, "run_capture",
                    side_effect=setup_environment.SetupError("no ensurepip"),
                ) as capture,
                patch("builtins.input") as user_input,
            ):
                with self.assertRaisesRegex(
                    setup_environment.SetupError, "python3-venv"
                ):
                    setup_environment.ensure_environment(
                        Path(directory) / ".venv"
                    )
            self.assertEqual(capture.call_count, 1)
            user_input.assert_not_called()

    def test_local_blockers_are_reported_before_input_or_installation(self):
        with (
            patch.object(
                setup_environment.sys.stdin, "isatty", return_value=True
            ),
            patch.object(setup_environment, "Version", None),
            patch.object(setup_environment.shutil, "which", return_value=None),
            patch.object(
                setup_environment, "require_tsh_features",
                side_effect=setup_environment.SetupError("tsh unavailable"),
            ),
            patch.object(
                setup_environment, "client_version", return_value="15.4.6"
            ),
            patch.object(setup_environment, "install_skill") as install,
            patch.object(setup_environment, "get_proxy_versions") as metadata,
            patch("builtins.input") as user_input,
        ):
            with self.assertRaises(setup_environment.SetupError) as raised:
                setup_environment.run_setup(None)
        message = str(raised.exception)
        self.assertIn("semantic-version", message)
        self.assertIn("git", message)
        self.assertIn("tsh unavailable", message)
        user_input.assert_not_called()
        install.assert_not_called()
        metadata.assert_not_called()

    def test_preflight_validates_local_client_version(self):
        with (
            patch.object(setup_environment, "Version", FakeVersion),
            patch.object(
                setup_environment.shutil, "which", return_value="git"
            ),
            patch.object(setup_environment, "require_tsh_features"),
            patch.object(
                setup_environment, "client_version", return_value="invalid"
            ),
        ):
            with self.assertRaisesRegex(
                setup_environment.SetupError, "client version"
            ):
                setup_environment.check_local_prerequisites()

    def test_preflight_returns_verified_local_client_version(self):
        with (
            patch.object(setup_environment, "Version", FakeVersion),
            patch.object(
                setup_environment.shutil, "which", return_value="git"
            ),
            patch.object(setup_environment, "require_tsh_features"),
            patch.object(
                setup_environment, "client_version", return_value="15.4.6"
            ),
        ):
            self.assertEqual(
                setup_environment.check_local_prerequisites(), "15.4.6"
            )

    def test_proxy_prompt_includes_example_and_reprompts_invalid_input(self):
        with patch(
            "builtins.input",
            side_effect=[
                "", "http://teleport.example.com", "teleport.example.com",
            ],
        ) as user_input:
            self.assertEqual(
                setup_environment.ask_proxy(), "teleport.example.com:443"
            )
        self.assertEqual(user_input.call_count, 3)
        prompt = user_input.call_args.args[0]
        self.assertIn("teleport.example.com", prompt)
        self.assertIn("443", prompt)

    def test_setup_completes_with_preflight_before_input(self):
        with tempfile.TemporaryDirectory() as directory:
            expected_proxy = "teleport.example.com:443"
            session = {
                "proxy": expected_proxy, "teleportUser": "example.user",
                "cluster": "staging", "logins": ["root", "c2-support"],
                "valid_until": "2099-01-01T00:00:00+00:00",
            }
            answers = iter(["teleport.example.com", "example.user"])

            def answer(prompt):
                features.assert_called_once_with()
                version.assert_called_once_with()
                return next(answers)

            with (
                patch.object(
                    setup_environment.sys.stdin, "isatty", return_value=True
                ),
                patch.object(setup_environment, "Version", FakeVersion),
                patch.object(
                    setup_environment.shutil, "which", return_value="git"
                ),
                patch.object(
                    setup_environment, "require_tsh_features"
                ) as features,
                patch.object(
                    setup_environment, "client_version", return_value="15.4.6"
                ) as version,
                patch.object(
                    setup_environment, "find_git_root", return_value=None
                ),
                patch.object(
                    setup_environment, "ask_yes_no", return_value=True
                ),
                patch("builtins.input", side_effect=answer),
                patch.object(
                    setup_environment, "get_proxy_versions",
                    return_value=("15.4.6", "14.0.0"),
                ) as metadata,
                patch.object(setup_environment, "establish_login") as login,
                patch.object(
                    setup_environment, "read_session",
                    side_effect=[None, session],
                ),
                patch.object(
                    setup_environment, "parse_json_command",
                    return_value=[
                        {
                            "metadata": {
                                "name": "node-id", "labels": {"use": "qa"},
                            },
                            "spec": {"hostname": "qa-node"},
                        },
                    ],
                ) as commands,
            ):
                setup_environment.run_setup(None, directory)
            metadata.assert_called_once_with(expected_proxy)
            login.assert_called_once_with(expected_proxy, "example.user")
            commands.assert_called_once_with([
                "tsh", f"--proxy={expected_proxy}", "ls",
                "--cluster=staging", "--format=json",
            ])
            output = Path(directory) / "teleport-tsh/assets/environment.json"
            self.assertEqual(
                json.loads(output.read_text(encoding="utf-8")),
                {"proxy": expected_proxy, "teleportUser": "example.user"},
            )

    def test_setup_reuses_session_without_required_config(self):
        session = {
            "proxy": "teleport.example.com:443",
            "teleportUser": "example.user",
            "cluster": "staging", "logins": ["root"],
            "valid_until": "2099-01-01T00:00:00+00:00",
        }
        with tempfile.TemporaryDirectory() as directory:
            with (
                patch.object(
                    setup_environment.sys.stdin, "isatty", return_value=True
                ),
                patch.object(
                    setup_environment, "check_local_prerequisites",
                    return_value="15.4.6",
                ),
                patch.object(
                    setup_environment, "find_git_root", return_value=None
                ),
                patch.object(setup_environment, "Version", FakeVersion),
                patch.object(
                    setup_environment, "read_session", return_value=session
                ),
                patch.object(
                    setup_environment, "get_proxy_versions",
                    return_value=("15.4.7", "14.0.0"),
                ),
                patch.object(
                    setup_environment, "ask_yes_no", side_effect=[True, False]
                ),
                patch.object(setup_environment, "establish_login") as login,
                patch.object(
                    setup_environment, "parse_json_command", return_value=[]
                ),
                patch(
                    "builtins.input",
                    side_effect=AssertionError("Unexpected questionnaire"),
                ),
            ):
                setup_environment.run_setup(None, directory)
            login.assert_not_called()
            output = Path(directory) / "teleport-tsh/assets/environment.json"
            self.assertFalse(output.exists())

    def test_mismatched_login_stops_before_node_discovery(self):
        with tempfile.TemporaryDirectory() as directory:
            wrong_session = {
                "proxy": "teleport.example.com:443",
                "teleportUser": "someone.else", "cluster": "staging",
                "logins": ["root"],
            }
            with (
                patch.object(sys.stdin, "isatty", return_value=True),
                patch.object(setup_environment, "Version", FakeVersion),
                patch.object(
                    setup_environment, "check_local_prerequisites",
                    return_value="15.4.6",
                ),
                patch.object(
                    setup_environment, "find_git_root", return_value=None
                ),
                patch.object(
                    setup_environment, "read_session",
                    side_effect=[None, wrong_session],
                ),
                patch.object(
                    setup_environment, "get_proxy_versions",
                    return_value=("15.4.6", "14.0.0"),
                ),
                patch("builtins.input", side_effect=[
                    "teleport.example.com", "example.user",
                ]),
                patch.object(setup_environment, "establish_login"),
                patch.object(setup_environment, "list_nodes") as nodes,
            ):
                with self.assertRaisesRegex(
                    setup_environment.SetupError, "requested valid session"
                ):
                    setup_environment.run_setup(None, directory)
            nodes.assert_not_called()

    def test_unwritable_output_stops_before_input(self):
        with tempfile.TemporaryDirectory() as directory:
            with (
                patch.object(
                    setup_environment.sys.stdin, "isatty", return_value=True
                ),
                patch.object(
                    setup_environment, "check_local_prerequisites",
                    return_value="15.4.6",
                ),
                patch.object(
                    setup_environment, "install_skill",
                    return_value=Path(directory) / "teleport-tsh",
                ),
                patch.object(
                    setup_environment, "find_git_root", return_value=None
                ),
                patch.object(
                    setup_environment.tempfile, "TemporaryFile",
                    side_effect=PermissionError("Output is not writable"),
                ),
                patch("builtins.input") as user_input,
            ):
                with self.assertRaises(PermissionError):
                    setup_environment.run_setup(None, directory)
            user_input.assert_not_called()

    def test_feature_detection_reads_help_from_stderr(self):
        def help_result(command, **kwargs):
            subcommand = command[1]
            help_text = "--format Format output (text, json, yaml)"
            if subcommand == "version":
                help_text += "\n--[no-]client Show the client version only"
            if subcommand == "login":
                help_text = "--proxy --user --request-roles"
            if subcommand == "ls":
                help_text += " --cluster"
            if subcommand == "ssh":
                help_text = "--request-mode"
            return type(
                "Result", (),
                {"returncode": 0, "stdout": "", "stderr": help_text},
            )()

        with patch.object(
            setup_environment.subprocess, "run", side_effect=help_result
        ) as run:
            setup_environment.require_tsh_features()
        self.assertEqual(run.call_count, 5)

    def test_feature_detection_requires_access_request_control(self):
        with patch.object(
            setup_environment, "run_capture",
            return_value="--format json --client --proxy --user --cluster",
        ):
            with self.assertRaisesRegex(
                setup_environment.SetupError, "--request-roles"
            ):
                setup_environment.require_tsh_features()

    def test_feature_detection_still_rejects_missing_json_support(self):
        result = type(
            "Result", (),
            {"returncode": 0, "stdout": "", "stderr": "--[no-]client"},
        )()
        with patch.object(
            setup_environment.subprocess, "run", return_value=result
        ):
            with self.assertRaisesRegex(
                setup_environment.SetupError, "does not advertise JSON"
            ):
                setup_environment.require_tsh_features()

    def test_data_capture_does_not_mix_stderr_into_json(self):
        result = type(
            "Result", (),
            {"returncode": 0, "stdout": '{"clientVersion":"18.2.0"}',
             "stderr": "A warning"},
        )()
        with patch.object(
            setup_environment.subprocess, "run", return_value=result
        ):
            self.assertEqual(
                setup_environment.client_version(), "18.2.0"
            )

    def test_client_version_reads_top_level_version_field(self):
        with patch.object(
            setup_environment, "run_capture",
            return_value='{"version":"15.4.6","gitref":"v15.4.6-0-g5ed51dd",'
            '"runtime":"go1.22.4"}',
        ) as capture:
            self.assertEqual(setup_environment.client_version(), "15.4.6")
        capture.assert_called_once_with(
            ["tsh", "version", "--format=json", "--client"]
        )

    def test_setup_defaults_to_installed_skill_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            skill = Path(directory) / "teleport-tsh"
            script = skill / "scripts" / "setup_environment.py"
            installed = Path(directory) / "personal" / "teleport-tsh"
            expected = installed / "assets" / "environment.json"
            with (
                patch.object(setup_environment, "__file__", str(script)),
                patch.object(
                    setup_environment, "check_local_prerequisites",
                    return_value="15.4.6", create=True,
                ),
                patch.object(
                    setup_environment, "default_skills_directory",
                    return_value=installed.parent, create=True,
                ),
                patch.object(
                    setup_environment, "install_skill",
                    return_value=installed, create=True,
                ) as install,
                patch.object(
                    setup_environment.sys.stdin, "isatty", return_value=True
                ),
                patch.object(
                    setup_environment, "find_git_root", return_value=None
                ),
                patch.object(
                    setup_environment,
                    "validate_output_path",
                    side_effect=setup_environment.SetupError("output probe"),
                ) as validate,
            ):
                with self.assertRaisesRegex(
                    setup_environment.SetupError, "output probe"
                ):
                    setup_environment.run_setup(None)
                    install.assert_called_once_with(skill, installed.parent)
            validate.assert_called_once_with(expected, None)

    def test_setup_preserves_explicit_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "custom.json"
            with (
                patch.object(
                    setup_environment, "check_local_prerequisites",
                    return_value="15.4.6", create=True,
                ),
                patch.object(
                    setup_environment, "default_skills_directory",
                    return_value=Path(directory), create=True,
                ),
                patch.object(
                    setup_environment, "install_skill",
                    return_value=Path(directory) / "teleport-tsh",
                    create=True,
                ),
                patch.object(
                    setup_environment.sys.stdin, "isatty", return_value=True
                ),
                patch.object(
                    setup_environment, "find_git_root", return_value=None
                ),
                patch.object(
                    setup_environment,
                    "validate_output_path",
                    side_effect=setup_environment.SetupError("output probe"),
                ) as validate,
            ):
                with self.assertRaisesRegex(
                    setup_environment.SetupError, "output probe"
                ):
                    setup_environment.run_setup(str(output))
            validate.assert_called_once_with(output, None)

    def test_default_skills_directory_uses_windows_host_under_wsl(self):
        with (
            patch.dict(
                setup_environment.os.environ,
                {"WSL_DISTRO_NAME": "Ubuntu"}, clear=True,
            ),
            patch.object(
                setup_environment, "run_capture",
                side_effect=[
                    "C:\\Users\\example\r\n", "/mnt/c/Users/example\n",
                ],
            ) as capture,
        ):
            self.assertEqual(
                setup_environment.default_skills_directory(),
                Path("/mnt/c/Users/example/.copilot/skills"),
            )
        self.assertEqual(
            capture.call_args_list[0].args[0],
            ["cmd.exe", "/d", "/c", "echo", "%USERPROFILE%"],
        )
        self.assertEqual(
            capture.call_args_list[1].args[0],
            ["wslpath", "-u", "C:\\Users\\example"],
        )

    def test_default_skills_directory_uses_home_outside_wsl(self):
        with (
            patch.dict(setup_environment.os.environ, {}, clear=True),
            patch.object(Path, "home", return_value=Path("/home/example")),
        ):
            self.assertEqual(
                setup_environment.default_skills_directory(),
                Path("/home/example/.copilot/skills"),
            )

    def test_explicit_skills_directory_skips_host_detection(self):
        with tempfile.TemporaryDirectory() as directory:
            skills = Path(directory)
            with (
                patch.object(
                    setup_environment, "check_local_prerequisites",
                    return_value="15.4.6", create=True,
                ),
                patch.object(
                    setup_environment.sys.stdin, "isatty", return_value=True
                ),
                patch.object(
                    setup_environment, "default_skills_directory"
                ) as detect,
                patch.object(
                    setup_environment, "install_skill",
                    return_value=skills / "teleport-tsh",
                ) as install,
                patch.object(
                    setup_environment, "find_git_root", return_value=None
                ),
                patch.object(
                    setup_environment, "validate_output_path",
                    side_effect=setup_environment.SetupError("output probe"),
                ),
            ):
                with self.assertRaisesRegex(
                    setup_environment.SetupError, "output probe"
                ):
                    setup_environment.run_setup(None, str(skills))
            detect.assert_not_called()
            self.assertEqual(install.call_args.args[1], skills)

    def test_wsl_host_detection_failure_requires_explicit_destination(self):
        with (
            patch.dict(
                setup_environment.os.environ,
                {"WSL_DISTRO_NAME": "Ubuntu"}, clear=True,
            ),
            patch.object(
                setup_environment, "run_capture", return_value="%USERPROFILE%"
            ),
        ):
            with self.assertRaisesRegex(
                setup_environment.SetupError, "--skills-dir"
            ):
                setup_environment.default_skills_directory()

    def test_install_copies_skill_and_preserves_private_context(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source" / "teleport-tsh"
            assets = source / "assets"
            assets.mkdir(parents=True)
            (source / "SKILL.md").touch()
            (assets / "environment.example.json").touch()
            (source / "scripts").mkdir()
            (source / "scripts" / "setup_environment.py").touch()
            (source / "scripts" / "__pycache__").mkdir()
            (source / "scripts" / "__pycache__" / "setup.pyc").touch()
            setup_environment.write_private_json(
                assets / "environment.json", {"private": "source"}
            )
            skills = root / "personal"
            installed = setup_environment.install_skill(source, skills)
            self.assertEqual(installed, skills / "teleport-tsh")
            self.assertTrue((installed / "SKILL.md").is_file())
            self.assertTrue(
                (installed / "assets/environment.example.json").is_file()
            )
            self.assertTrue(
                (installed / "scripts/setup_environment.py").is_file()
            )
            self.assertFalse((installed / "scripts/__pycache__").exists())
            context = installed / "assets/environment.json"
            self.assertFalse(context.exists())
            setup_environment.write_private_json(context, {"private": "host"})
            original = context.read_bytes()
            (source / "SKILL.md").write_text("Updated skill", encoding="utf-8")
            setup_environment.install_skill(source, skills)
            self.assertEqual(context.read_bytes(), original)
            self.assertEqual(
                (installed / "SKILL.md").read_text(encoding="utf-8"),
                "Updated skill",
            )

    def test_install_rejects_symbolic_destination_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source/teleport-tsh"
            source.mkdir(parents=True)
            (source / "SKILL.md").touch()
            destination = root / "personal/teleport-tsh"
            destination.mkdir(parents=True)
            protected = root / "protected.md"
            protected.touch()
            (destination / "SKILL.md").symlink_to(protected)
            with self.assertRaisesRegex(
                setup_environment.SetupError, "Symbolic"
            ):
                setup_environment.install_skill(source, destination.parent)
            self.assertEqual(protected.read_bytes(), b"")

    def test_install_from_destination_is_a_no_op(self):
        with tempfile.TemporaryDirectory() as directory:
            skills = Path(directory)
            source = skills / "teleport-tsh"
            source.mkdir()
            self.assertEqual(
                setup_environment.install_skill(source, skills), source
            )

    def test_output_outside_git_does_not_require_a_repository(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "environment.json"
            self.assertEqual(
                setup_environment.validate_output_path(output, None),
                output.resolve(),
            )

    def test_find_git_root_allows_non_repository_installation(self):
        result = type("Result", (), {"returncode": 128})()
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(
                setup_environment.subprocess, "run", return_value=result
            ) as run:
                self.assertIsNone(
                    setup_environment.find_git_root(Path(directory))
                )
            self.assertEqual(
                run.call_args.args[0],
                [
                    "git", "-C", str(Path(directory).resolve()),
                    "rev-parse", "--show-toplevel",
                ],
            )

    def test_existing_output_outside_git_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "environment.json"
            output.touch()
            with self.assertRaisesRegex(
                setup_environment.SetupError, "overwrite"
            ):
                setup_environment.validate_output_path(output, None)

    def test_repository_output_must_be_git_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            output = root / "assets" / "environment.json"
            for returncode in (0, 1):
                result = type("Result", (), {"returncode": returncode})()
                with self.subTest(returncode=returncode), patch.object(
                    setup_environment.subprocess, "run", return_value=result
                ) as run:
                    if returncode == 0:
                        self.assertEqual(
                            setup_environment.validate_output_path(
                                output, root
                            ),
                            output,
                        )
                    else:
                        with self.assertRaisesRegex(
                            setup_environment.SetupError, "Git-ignored"
                        ):
                            setup_environment.validate_output_path(
                                output, root
                            )
                    run.assert_called_once_with(
                        [
                            "git", "-C", str(root), "check-ignore", "--quiet",
                            "--", str(output.relative_to(root)),
                        ],
                        check=False,
                    )

    def test_version_gate_checks_supported_majors_and_minimum(self):
        with patch.object(setup_environment, "Version", FakeVersion):
            setup_environment.check_version_gate("v15.4.6", "15.4.6", "15.0.0")
            setup_environment.check_version_gate("15.4.5", "15.4.6", "15.0.0")
            setup_environment.check_version_gate("14.2.0", "15.4.6", "14.0.0")
            for local in ("16.0.0", "13.0.0"):
                with self.assertRaisesRegex(
                    setup_environment.SetupError, "Unsupported major"
                ):
                    setup_environment.check_version_gate(
                        local, "15.4.6", "12.0.0"
                    )
            with self.assertRaisesRegex(
                setup_environment.SetupError, "below minimum"
            ):
                setup_environment.check_version_gate(
                    "14.0.0", "15.4.6", "15.0.0"
                )
            with self.assertRaisesRegex(
                setup_environment.SetupError, "inconsistent"
            ):
                setup_environment.check_version_gate(
                    "15.4.6", "15.4.6", "15.5.0"
                )

    def test_extract_logins_includes_root_and_rejects_unknown_schema(self):
        self.assertEqual(
            setup_environment.extract_logins(
                {"logins": ["ubuntu", "root", "diagnostics"]}
            ),
            ["diagnostics", "root", "ubuntu"],
        )
        with self.assertRaisesRegex(
            setup_environment.SetupError, "unsupported"
        ):
            setup_environment.extract_logins({"username": "user"})

    def test_active_session_uses_status_not_a_local_permission_inventory(self):
        document = {
            "active": {
                "profile_url": "https://teleport.example.com:443",
                "username": "example.user",
                "cluster": "example-cluster",
                "valid_until": "2999-01-01T00:00:00Z",
                "logins": ["root"],
                "traits": {"logins": ["not-the-active-login-list"]},
            },
            "profiles": [],
        }
        session = setup_environment.active_session(document)
        self.assertEqual(session["proxy"], "teleport.example.com:443")
        self.assertEqual(session["teleportUser"], "example.user")
        self.assertEqual(session["cluster"], "example-cluster")
        self.assertEqual(session["valid_until"], "2999-01-01T00:00:00+00:00")
        self.assertEqual(session["logins"], ["root"])

    def test_node_snapshot_prints_timestamp_id_and_labels(self):
        node = {
            "metadata": {"id": 123, "labels": {"use": "dev"}},
            "spec": {"hostname": "node-a"},
        }
        with (
            patch.object(
                setup_environment, "parse_json_command", return_value=[node]
            ),
            patch("sys.stdout", new_callable=io.StringIO) as stdout,
        ):
            setup_environment.list_nodes({
                "proxy": "teleport.example.com:443", "cluster": "staging",
            })
        output = stdout.getvalue()
        self.assertIn("Visible SSH nodes discovered at ", output)
        self.assertIn('"node-a"  123  {"use": "dev"}', output)

    def test_expired_session_is_not_reused(self):
        self.assertIsNone(setup_environment.active_session({
            "active": {
                "profile_url": "https://teleport.example.com:443",
                "username": "example.user", "cluster": "example-cluster",
                "valid_until": "2000-01-01T00:00:00Z", "logins": ["root"],
            }
        }))

    def test_proxy_accepts_hostname_or_https_url_with_default_port(self):
        for value, expected in (
            ("teleport.example.com", "teleport.example.com:443"),
            ("teleport.example.com:443", "teleport.example.com:443"),
            ("teleport.example.com:8443", "teleport.example.com:8443"),
            ("https://teleport.example.com", "teleport.example.com:443"),
            (
                "https://teleport.example.com:8443/",
                "teleport.example.com:8443",
            ),
            ("  teleport.example.com  ", "teleport.example.com:443"),
            ("[::1]", "[::1]:443"),
        ):
            with self.subTest(value=value):
                self.assertEqual(
                    setup_environment.validate_proxy(value), expected
                )

    def test_proxy_rejects_unsafe_or_malformed_addresses(self):
        for value in (
            "http://teleport.example.com", "",
            "https://user:password@teleport.example.com",
            "teleport.example.com/path", "teleport.example.com?query",
            "teleport.example.com#fragment", "teleport.example.com:",
            "teleport.example.com:0", "teleport.example.com:65536",
            "teleport.example.com:notaport", "tele port.example.com",
            "https://teleport.example.com/path", "teleport..example.com",
        ):
            with self.subTest(value=value):
                with self.assertRaises(setup_environment.SetupError):
                    setup_environment.validate_proxy(value)

    def test_private_json_creation_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "environment.json"
            setup_environment.write_private_json(output, {"environments": []})
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            with self.assertRaisesRegex(
                setup_environment.SetupError, "overwrite"
            ):
                setup_environment.write_private_json(
                    output, {"environments": []}
                )

    def test_not_logged_in_is_recoverable_but_other_status_errors_stop(self):
        for message, recoverable in (
            ("ERROR: Not logged in.", True),
            ("ERROR: Active profile expired.", True),
            ("ERROR: Access denied.", False),
        ):
            result = type("Status", (), {
                "returncode": 1, "stdout": "", "stderr": message,
            })()
            with self.subTest(message=message), patch.object(
                setup_environment.subprocess, "run", return_value=result
            ):
                if recoverable:
                    self.assertIsNone(setup_environment.read_session())
                else:
                    with self.assertRaises(setup_environment.SetupError):
                        setup_environment.read_session()

    def test_missing_status_requires_approved_login_and_confirmation(self):
        with patch.object(setup_environment, "run_interactive") as run:
            setup_environment.establish_login(
                "teleport.example.com:443", "example.user"
            )
        run.assert_called_once_with([
            "tsh", "--proxy=teleport.example.com:443", "--user=example.user",
            "login", "--request-roles=no",
        ])

    def test_positional_cluster_cannot_be_a_login_option(self):
        with (
            patch.object(setup_environment.subprocess, "run") as run,
            patch(
                "builtins.input",
                side_effect=AssertionError("Unexpected input"),
            ),
        ):
            with self.assertRaisesRegex(
                setup_environment.SetupError, "Cluster"
            ):
                setup_environment.establish_login(
                    "teleport.example.com:443", None, "--request-roles=admin"
                )
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
