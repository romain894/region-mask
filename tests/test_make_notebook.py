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
        prefix = "Available notebooks:"
        choices_lines = [line for line in result.stdout.splitlines() if line.startswith(prefix)]
        self.assertEqual(len(choices_lines), 1, result.stdout)
        # Make's wildcard ordering can differ across systems/locales. Check
        # membership and duplicates, not the incidental display order.
        self.assertCountEqual(
            choices_lines[0].removeprefix(prefix).split(),
            ["countries", "countries_oceans", "land_ocean", "mask", "oceans"],
        )
        self.assertNotIn("-m marimo edit", result.stdout)

    def test_unknown_selection_refuses(self):
        result = self.run_make("NOTEBOOK=missing")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Unknown notebook", result.stdout)
        self.assertNotIn("-m marimo edit", result.stdout)

    def test_explicit_selection_opens_requested_file(self):
        for name in ("countries", "oceans", "countries_oceans", "land_ocean", "mask"):
            with self.subTest(name=name):
                result = self.run_make(f"NOTEBOOK={name}")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("-m marimo edit", result.stdout)
                self.assertIn(f"notebooks/{name}.py", result.stdout)
