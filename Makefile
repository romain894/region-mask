# Reproducibility entry points. Override PYTHON when using another environment:
#   make test PYTHON=python3

PYTHON ?= .venv/bin/python
NOTEBOOKS := $(wildcard notebooks/*.py)
NOTEBOOK_NAMES := $(basename $(notdir $(NOTEBOOKS)))
NOTEBOOK ?=

.DEFAULT_GOAL := help

.PHONY: help test generate-ne check-notebooks notebook docs build package-check regression regression-strict compare

help:
	@printf '%s\n' \
	  'Available targets:' \
	  '  make test              Run unit and analytic mask-contract tests.' \
	  '  make generate-ne       Regenerate all Natural Earth shapefiles, both masks and ID tables (overwrites outputs).' \
	  '  make check-notebooks   Validate marimo notebook structure.' \
	  '  make notebook NOTEBOOK=<name>  Open a notebook, e.g. NOTEBOOK=oceans (required).' \
	  '  make docs              Build Sphinx HTML documentation (warnings fail).' \
	  '  make build             Build a source archive and wheel.' \
	  '  make package-check     Build and test the installed wheel outside the checkout.' \
	  '  make regression        Regenerate Natural Earth artifacts and write a Markdown regression report.' \
	  '  make regression-strict As regression, additionally require byte-identical published artifacts.' \
	  '  make compare CANDIDATE=<artifact-directory> [REFERENCE=<artifact-directory>]' \
	  '                         Compare existing artifacts and write a Markdown report.' \
	  '' \
	  'Reports are written to ignored regression-runs/<UTC timestamp>/ directories.' \
	  'Use PYTHON=... to select a different Python executable.'

test:
	$(PYTHON) -m unittest discover -s tests -v

generate-ne:
	$(PYTHON) -m region_mask all-ne

regression:
	$(PYTHON) -m regression run

check-notebooks:
	$(PYTHON) -m marimo check --strict $(NOTEBOOKS)

notebook:
	@if [ -z "$(NOTEBOOK)" ]; then \
	  echo 'NOTEBOOK is required. Example: make notebook NOTEBOOK=mask'; \
	  echo 'Available notebooks: $(NOTEBOOK_NAMES)'; exit 2; \
	fi
	@case " $(NOTEBOOK_NAMES) " in \
	  *" $(NOTEBOOK) "*) ;; \
	  *) echo 'Unknown notebook: $(NOTEBOOK)'; \
	     echo 'Available notebooks: $(NOTEBOOK_NAMES)'; exit 2 ;; \
	esac
	$(PYTHON) -m marimo edit "notebooks/$(NOTEBOOK).py"

docs:
	$(PYTHON) -m sphinx -b html -W --keep-going docs docs/_build/html

build:
	$(PYTHON) -m build

package-check: build
	$(PYTHON) scripts/check_distribution.py

regression-strict:
	$(PYTHON) -m regression run --require-byte-identical

compare:
	@test -n "$(CANDIDATE)" || { echo 'CANDIDATE is required, e.g. make compare CANDIDATE=regression-runs/example/candidate'; exit 2; }
	$(PYTHON) -m regression compare --candidate-dir "$(CANDIDATE)" $(if $(REFERENCE),--reference-dir "$(REFERENCE)")
