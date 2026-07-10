import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
POLICY = SKILL_DIR / "scripts" / "policy_check.py"
sys.path.insert(0, str(SKILL_DIR / "scripts"))

from policy_check import check_paths, check_policy  # noqa: E402


class PolicyCheckTests(unittest.TestCase):
    def run_policy(self, patch_text, *args):
        with tempfile.TemporaryDirectory() as tmp:
            patch = Path(tmp) / "patch.diff"
            patch.write_text(patch_text, encoding="utf-8")
            process = subprocess.run(
                [sys.executable, str(POLICY), "--patch", str(patch), *args],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        return process.returncode, json.loads(process.stdout)

    def test_allows_changed_files_under_allowed_paths(self):
        code, result = self.run_policy(
            """diff --git a/src/example.py b/src/example.py
--- a/src/example.py
+++ b/src/example.py
@@ -1 +1 @@
-old
+new
""",
            "--allowed",
            "src/**",
        )
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["changed_files"], ["src/example.py"])

    def test_rejects_changed_files_outside_allowed_paths(self):
        code, result = self.run_policy(
            """diff --git a/src/example.py b/src/example.py
--- a/src/example.py
+++ b/src/example.py
@@ -1 +1 @@
-old
+new
""",
            "--allowed",
            "tests/**",
        )
        self.assertNotEqual(code, 0)
        self.assertEqual(result["status"], "failed")
        self.assertIn("Path outside allowed paths: src/example.py", result["violations"])

    def test_rejects_denied_paths(self):
        code, result = self.run_policy(
            """diff --git a/.env b/.env
--- a/.env
+++ b/.env
@@ -1 +1 @@
-old
+new
""",
            "--allowed",
            "**",
            "--deny",
            ".env*",
        )
        self.assertNotEqual(code, 0)
        self.assertIn("Denied path modified: .env", result["violations"])

    def test_rejects_binary_diff_by_default(self):
        code, result = self.run_policy(
            """diff --git a/assets/image.png b/assets/image.png
new file mode 100644
index 0000000..1234567
GIT binary patch
literal 0
HcmV?d00001
""",
            "--allowed",
            "assets/**",
        )
        self.assertNotEqual(code, 0)
        self.assertIn("Binary file changes are not allowed", result["violations"])

    def test_rejects_delete_by_default_and_allows_when_flagged(self):
        patch = """diff --git a/src/old.py b/src/old.py
deleted file mode 100644
--- a/src/old.py
+++ /dev/null
@@ -1 +0,0 @@
-old
"""
        code, result = self.run_policy(patch, "--allowed", "src/**")
        self.assertNotEqual(code, 0)
        self.assertIn("File deletions are not allowed", result["violations"])

        code, result = self.run_policy(patch, "--allowed", "src/**", "--allow-deletes")
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "passed")

    def test_rename_checks_old_and_new_path(self):
        code, result = self.run_policy(
            """diff --git a/src/old.py b/secrets/new.py
similarity index 100%
rename from src/old.py
rename to secrets/new.py
""",
            "--allowed",
            "src/**",
            "--deny",
            "secrets/**",
        )
        self.assertNotEqual(code, 0)
        self.assertIn("Denied path modified: secrets/new.py", result["violations"])

    def test_structured_paths_do_not_strip_diff_prefixes(self):
        result = check_paths(["a/private/key.txt"], ["**"], ["a/private/**"])
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["changed_files"], ["a/private/key.txt"])
        self.assertIn("Denied path modified: a/private/key.txt", result["violations"])

    def test_single_star_does_not_cross_path_segments(self):
        direct = check_paths(["src/file.py"], ["src/*"], [])
        nested = check_paths(["src/pkg/file.py"], ["src/*"], [])
        recursive = check_paths(["src/pkg/file.py"], ["src/**"], [])
        self.assertEqual(direct["status"], "passed")
        self.assertEqual(nested["status"], "failed")
        self.assertEqual(recursive["status"], "passed")

    def test_structured_metadata_prevents_keyword_false_positives(self):
        patch = b"""diff --git a/src/text.py b/src/text.py
--- a/src/text.py
+++ b/src/text.py
@@ -0,0 +1,2 @@
+GIT binary patch
+deleted file mode 100644
"""
        result = check_policy(
            patch,
            ["src/**"],
            [],
            changed_paths=["src/text.py"],
            has_binary_changes=False,
            has_deletes=False,
        )
        self.assertEqual(result["status"], "passed")


if __name__ == "__main__":
    unittest.main()
