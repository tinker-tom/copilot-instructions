import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[2] / "tools" / "sync_skills.py"
SPEC = importlib.util.spec_from_file_location("sync_skills", SCRIPT)
sync_skills = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync_skills)


class SyncSkillsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.sources = self.root / "sources"
        self.destination = self.root / "personal" / "skills"
        self.source = self.sources / "example-skill"
        self.write(
            self.source / "SKILL.md",
            "---\nname: example-skill\n"
            "description: Use when testing skill updates\n---\n\n# Example\n",
        )
        self.write(self.source / "references" / "guide.md", "Original guide\n")

    def write(self, path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def synchronize(self, apply=False, destinations=None, names=None):
        return sync_skills.sync_skills(
            self.sources,
            names or ["example-skill"],
            destinations or [self.destination],
            apply=apply,
        )

    def test_preview_does_not_create_destination(self):
        messages = self.synchronize()
        self.assertIn("INSTALL", "\n".join(messages))
        self.assertFalse(self.destination.parent.exists())

    def test_install_and_update_managed_files(self):
        self.synchronize(apply=True)
        self.write(self.source / "references" / "guide.md", "Updated guide\n")
        messages = self.synchronize(apply=True)
        self.assertIn("UPDATE", "\n".join(messages))
        guide = self.destination / "example-skill" / "references" / "guide.md"
        self.assertEqual(guide.read_text(), "Updated guide\n")
        self.assertIn("CURRENT", "\n".join(self.synchronize()))

    def test_refuse_local_edit_without_changing_any_destination(self):
        other = self.root / "other" / "skills"
        self.synchronize(apply=True)
        installed = (
            self.destination / "example-skill" / "references" / "guide.md"
        )
        self.write(installed, "Private local edit\n")
        self.write(
            self.source / "references" / "guide.md", "Repository update\n"
        )
        with self.assertRaisesRegex(sync_skills.SyncError, "guide.md"):
            self.synchronize(
                apply=True, destinations=[other, self.destination]
            )
        self.assertFalse(other.exists())
        self.assertEqual(installed.read_text(), "Private local edit\n")

    def test_refuse_added_or_deleted_local_files(self):
        self.synchronize(apply=True)
        extra = self.destination / "example-skill" / "private.json"
        self.write(extra, "private\n")
        with self.assertRaises(sync_skills.SyncError):
            self.synchronize(apply=True)
        extra.unlink()
        guide = self.destination / "example-skill" / "references" / "guide.md"
        guide.unlink()
        with self.assertRaises(sync_skills.SyncError):
            self.synchronize(apply=True)

    def test_adopt_identical_existing_copy(self):
        import shutil

        shutil.copytree(self.source, self.destination / "example-skill")
        self.assertIn("ADOPT", "\n".join(self.synchronize()))
        self.assertFalse((self.destination / ".skill-sync-state").exists())
        self.synchronize(apply=True)
        self.assertIn("CURRENT", "\n".join(self.synchronize()))

    def test_refuse_unmanaged_different_copy(self):
        installed = self.destination / "example-skill" / "SKILL.md"
        self.write(installed, "Local skill\n")
        with self.assertRaisesRegex(sync_skills.SyncError, "unmanaged"):
            self.synchronize(apply=True)
        self.assertEqual(installed.read_text(), "Local skill\n")

    def test_remove_obsolete_managed_files(self):
        self.synchronize(apply=True)
        (self.source / "references" / "guide.md").unlink()
        self.synchronize(apply=True)
        guide = self.destination / "example-skill" / "references" / "guide.md"
        self.assertFalse(guide.exists())

    def test_restore_installation_if_manifest_write_fails(self):
        self.synchronize(apply=True)
        self.write(self.source / "references" / "guide.md", "Updated guide\n")
        manifest = (
            self.destination / ".skill-sync-state" / "example-skill.json"
        )
        original_manifest = manifest.read_bytes()
        with mock.patch.object(
            sync_skills, "write_manifest",
            side_effect=OSError("Simulated write failure"),
        ):
            with self.assertRaises(OSError):
                self.synchronize(apply=True)
        guide = self.destination / "example-skill" / "references" / "guide.md"
        self.assertEqual(guide.read_text(), "Original guide\n")
        self.assertEqual(manifest.read_bytes(), original_manifest)
        self.assertFalse([
            path for path in self.destination.glob(".skill-sync-*")
            if path.name != sync_skills.STATE_DIRECTORY
        ])

    def test_refuse_changes_after_planning(self):
        self.synchronize(apply=True)
        plan = sync_skills.make_plan(self.source, self.destination)
        plan["action"] = "UPDATE"
        installed = (
            self.destination / "example-skill" / "references" / "guide.md"
        )
        self.write(installed, "Concurrent edit\n")
        with self.assertRaisesRegex(
            sync_skills.SyncError, "changed after preview"
        ):
            sync_skills.apply_plan(plan)
        self.assertEqual(installed.read_text(), "Concurrent edit\n")

    def test_refuse_name_mismatching_directory(self):
        self.write(
            self.source / "SKILL.md",
            "---\nname: different-name\ndescription: Use when testing\n---\n",
        )
        with self.assertRaisesRegex(sync_skills.SyncError, "name must match"):
            self.synchronize(apply=True)

    def test_refuse_unreadable_subdirectory(self):
        failure = PermissionError("Cannot inspect source")
        with mock.patch.object(
            sync_skills.os, "walk",
            side_effect=lambda *args, **kwargs: kwargs["onerror"](failure),
        ):
            with self.assertRaisesRegex(
                sync_skills.SyncError, "Cannot inspect source"
            ):
                self.synchronize(apply=True)

    def test_exclude_private_runtime_and_credential_files(self):
        for relative in (
            ".local/environment.json", ".env",
            "scripts/__pycache__/helper.pyc", "assets/client.pem",
        ):
            self.write(self.source / relative, "Do not distribute\n")
        self.write(
            self.source / "assets" / "environment.example.json",
            '{"environments": []}\n',
        )
        self.synchronize(apply=True)
        installed = self.destination / "example-skill"
        template = installed / "assets" / "environment.example.json"
        self.assertTrue(template.is_file())
        self.assertFalse((installed / ".local").exists())
        self.assertFalse((installed / ".env").exists())
        self.assertFalse((installed / "assets" / "client.pem").exists())
        self.assertFalse((installed / "scripts" / "__pycache__").exists())

    def test_refuse_overlapping_source_and_destination(self):
        with self.assertRaises(sync_skills.SyncError):
            self.synchronize(apply=True, destinations=[self.sources])

    def test_refuse_symbolic_links(self):
        link = self.source / "references" / "external.md"
        try:
            link.symlink_to(self.source / "SKILL.md")
        except OSError:
            self.skipTest("Symbolic links unavailable")
        with self.assertRaisesRegex(sync_skills.SyncError, "[Ss]ymbolic"):
            self.synchronize(apply=True)

    def test_corrupt_manifest_is_not_overwritten(self):
        self.synchronize(apply=True)
        manifest = (
            self.destination / ".skill-sync-state" / "example-skill.json"
        )
        self.write(manifest, "not JSON\n")
        with self.assertRaises(sync_skills.SyncError):
            self.synchronize(apply=True)
        self.assertEqual(manifest.read_text(), "not JSON\n")

    def test_reject_invalid_skill_name_and_frontmatter(self):
        with self.assertRaises(sync_skills.SyncError):
            self.synchronize(names=["../escape"])
        self.write(self.source / "SKILL.md", "No frontmatter\n")
        with self.assertRaises(sync_skills.SyncError):
            self.synchronize(apply=True)

    def test_cli_all_preview_and_apply(self):
        command = [
            sys.executable, str(SCRIPT),
            "--source-root", str(self.sources), "--all",
            "--destination", str(self.destination),
        ]
        preview = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertFalse(self.destination.exists())
        applied = subprocess.run(
            command + ["--apply"], capture_output=True, text=True
        )
        self.assertEqual(applied.returncode, 0, applied.stderr)
        manifest_path = (
            self.destination / ".skill-sync-state" / "example-skill.json"
        )
        manifest = json.loads(manifest_path.read_text())
        self.assertEqual(manifest["schema_version"], 1)
        self.assertIn("SKILL.md", manifest["files"])


if __name__ == "__main__":
    unittest.main()
