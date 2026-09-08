# Reproducibility entry points. Override PYTHON when using another environment:
#   make test PYTHON=python3

PYTHON ?= .venv/bin/python

.DEFAULT_GOAL := help

.PHONY: help test regression regression-strict compare

help:
	@printf '%s\n' \
	  'Available targets:' \
	  '  make test              Run unit and analytic mask-contract tests.' \
	  '  make regression        Regenerate Natural Earth artifacts and write a Markdown regression report.' \
	  '  make regression-strict As regression, additionally require byte-identical published artifacts.' \
	  '  make compare CANDIDATE=<artifact-directory> [REFERENCE=<artifact-directory>]' \
	  '                         Compare existing artifacts and write a Markdown report.' \
	  '' \
	  'Reports are written to ignored regression-runs/<UTC timestamp>/ directories.' \
	  'Use PYTHON=... to select a different Python executable.'

test:
	$(PYTHON) -m unittest discover -s tests -v

regression:
	$(PYTHON) -m regression run

regression-strict:
	$(PYTHON) -m regression run --require-byte-identical

compare:
	@test -n "$(CANDIDATE)" || { echo 'CANDIDATE is required, e.g. make compare CANDIDATE=regression-runs/example/candidate'; exit 2; }
	$(PYTHON) -m regression compare --candidate-dir "$(CANDIDATE)" $(if $(REFERENCE),--reference-dir "$(REFERENCE)")
