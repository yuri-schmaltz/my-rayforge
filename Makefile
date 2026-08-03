# Pires Forge developer Makefile
#
# This Makefile is a thin wrapper around `pixi` for the most
# common dev tasks. It exists so that contributors can use the
# familiar `make test` / `make lint` workflow even if they don't
# remember the exact pixi task names.
#
# All targets are thin pass-throughs; nothing is implemented in
# the Makefile itself. If a target is missing, run
# `pixi task list` to see what's actually available.

# Use bash for shell snippets (so $(shell ...) and conditionals
# work portably on Linux + macOS).
SHELL := /usr/bin/env bash

# Default target shown by `make` with no args.
.DEFAULT_GOAL := help

# Print a help message that lists every documented target.
.PHONY: help
help:
	@echo "Pires Forge dev targets:"
	@echo "  make install   - install the pixi environment"
	@echo "  make run       - run the app (pixi run pires-forge)"
	@echo "  make test      - run the test suite"
	@echo "  make uitest    - run the UI tests (needs a display)"
	@echo "  make lint      - run ruff + bandit + format checks"
	@echo "  make format    - auto-format Python source with ruff"
	@echo "  make coverage  - run tests with coverage report"
	@echo "  make build     - build the .deb installer (Linux only)"
	@echo "  make clean     - remove build artifacts and caches"
	@echo "  make reset     - remove the pixi env and lockfile"

# Install the pixi environment. Idempotent: if the env already
# exists, pixi is a no-op.
.PHONY: install
install:
	pixi install

# Run the app in dev mode.
.PHONY: run
run:
	pixi run pires-forge

# Run the full test suite (pytest, including addon tests).
.PHONY: test
test:
	pixi run test

# Run the UI tests. Requires a graphical environment.
.PHONY: uitest
uitest:
	pixi run uitest

# Lint everything: ruff check + bandit. Fails on any HIGH-severity
# bandit finding.
.PHONY: lint
lint:
	pixi run lint

# Auto-format Python source with ruff.
.PHONY: format
format:
	pixi run -e default ruff check --fix rayforge tests scripts
	pixi run -e default ruff format rayforge tests scripts

# Run tests with coverage report.
.PHONY: coverage
coverage:
	pixi run coverage

# Build the .deb installer. Linux only; macOS/Windows have their
# own scripts.
.PHONY: build
build:
	pixi run build-deb

# Remove build artifacts and Python caches. Does NOT touch the
# pixi env.
.PHONY: clean
clean:
	pixi run clean
	rm -rf .pytest_cache .ruff_cache .mypy_cache htmlcov .coverage
	find . -name __pycache__ -type d -prune -exec rm -rf {} +

# Nuclear option: remove the pixi env and lockfile. Forces a
# full re-resolve on the next `make install`.
.PHONY: reset
reset:
	rm -rf .pixi pixi.lock
	@echo "pixi env and lockfile removed. Run 'make install' to recreate."
