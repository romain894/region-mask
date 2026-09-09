"""Notebook selection must be explicit; these checks never launch marimo."""

import os
from pathlib import Path
import shutil
import subprocess
import unittest


@unittest.skipUnless(shutil.which("make"), "make is not installed")
class MakeNotebookTests(unittest.TestCase):
    def run_make(self, *arguments):
        env = dict(os.environ)
        env.pop("NOTEBOOK", None)
        return subprocess.run(
            ["make", "--no-print-directory", "notebook", "PYTHON=echo", *arguments],
            cwd=Path(__file__).resolve().parents[1], env=env,
            text=True, capture_output=True, check=False,
        )

    def test_missing_selection_refuses_and_lists_choices(self):
        result = self.run_make()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("NOTEBOOK is required", result.stdout)
        self.assertIn("generate_mask.py", result.stdout)
        self.assertNotIn("-m marimo edit", result.stdout)

    def test_unknown_selection_refuses(self):
        result = self.run_make("NOTEBOOK=missing.py")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Unknown notebook", result.stdout)
        self.assertNotIn("-m marimo edit", result.stdout)

    def test_explicit_selection_opens_requested_file(self):
        result = self.run_make("NOTEBOOK=generate_mask.py")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("-m marimo edit", result.stdout)
        self.assertIn("notebooks/generate_mask.py", result.stdout)
