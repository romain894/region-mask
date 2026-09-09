"""Sphinx configuration; document the installed package, not a sys.path override."""

from importlib.metadata import version as package_version

project = "Region Mask"
author = "Romain Thomas, Giulia Cigna, Elena De Petrillo"
copyright = "2026, " + author
release = package_version("region-mask")
version = release

extensions = ["sphinx.ext.autodoc", "sphinx.ext.napoleon", "sphinx.ext.viewcode"]
html_theme = "alabaster"
exclude_patterns = ["_build"]
autodoc_member_order = "bysource"
autodoc_typehints = "description"
