# Contributing to Pires Forge

This document covers **how to contribute** — branching,
PRs, worktrees, validation gates, and the conventions
we use.

For the **user manual** (how to use the app), see
[USER_MANUAL.md](USER_MANUAL.md). For **architecture and
development setup**, see [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md).

---

## Table of contents

1. [Code of conduct](#1-code-of-conduct)
2. [Workflow at a glance](#2-workflow-at-a-glance)
3. [Worktree workflow (recommended)](#3-worktree-workflow-recommended)
4. [Commit style](#4-commit-style)
5. [Pull request checklist](#5-pull-request-checklist)
6. [Validation gates](#6-validation-gates)
7. [i18n contribution](#7-i18n-contribution)
8. [Performance and tracing](#8-performance-and-tracing)
9. [Accessibility](#9-accessibility)
10. [Release process](#10-release-process)

---

## 1. Code of conduct

Pires Forge is a single-maintainer project. Be patient,
be kind, and prefer concrete suggestions over criticism.
PRs that don't get a response in 2 weeks can be pinged
once; if still no response, the contributor is free to
fork.

---

## 2. Workflow at a glance

```
1. Pick a P-item from ROADMAP.md (or open a fresh issue)
2. Create a worktree off main: git worktree add .worktrees/<branch> -b <branch> main
3. Develop, commit, repeat (one commit per logical change)
4. Run validation gates (see §6)
5. Push branch: git push -u origin <branch>
6. Open a PR via the GitHub web UI
7. After review, squash-merge
8. Cleanup: git worktree remove .worktrees/<branch> --force && git worktree prune
```

A typical small change (one feature, ~200 lines) is
1-3 commits, 1 PR, 1-2 days of work.

---

## 3. Worktree workflow (recommended)

Every change goes in a worktree. The main repo stays
on `main` (clean), each feature has its own branch in
its own worktree.

```sh
# Create the worktree
cd /workspace/pires-forge
git worktree add .worktrees/feature-x -b feature-x main

# Develop
cd .worktrees/feature-x
# ... edits ...
git add -A
git commit -m "feat: ..."

# Push
git push -u origin feature-x

# Open a PR via the GitHub web UI

# After merge, cleanup
cd /workspace/pires-forge
git worktree remove .worktrees/feature-x --force
git worktree prune
git branch -D feature-x
git pull --ff-only
```

**Why worktrees?**
- Main repo stays clean (always on main, always
  buildable)
- Multiple features can be in flight at the same time
  (e.g. you're reviewing PR #1 while working on PR #2)
- `git status` and `git log` show only the current
  branch's state, which is what you want 99% of the time

**Why one worktree per branch?**
- Each worktree has its own working directory, its own
  index, and its own uncommitted changes
- A worktree can be in a 'dirty' state (uncommitted
  changes) without affecting the main checkout
- If your session crashes, the worktree is preserved on
  disk; you can `git worktree list` and find where you
  left off

---

## 4. Commit style

We use **conventional commits** for the message format:

```
<type>(<scope>): <subject>
<BLANK LINE>
<body>
<BLANK LINE>
<footer>
```

Types: `feat`, `fix`, `docs`, `test`, `refactor`, `perf`,
`chore`, `ci`, `i18n`, `a11y`.

Example:

```
perf: lazy-load addon frontend modules on first attribute access

Reduces cold start by deferring the actual exec_module()
of each addon's frontend hooks until they're first used
(by pluggy looking up a hookimpl, or by user code
importing a hook). The first hit per addon is the same
as before (~50-200ms); subsequent hits are free.

New file: rayforge/addon_mgr/lazy.py (~140 lines)
  - LazyModule class: a module-shaped proxy...

Modified: rayforge/addon_mgr/addon_manager.py
  - load_addon checks the lazy flag...
```

The first line is the **subject** (max 70 chars). The
body explains **why**, not what (the diff shows what).
The footer is for `BREAKING CHANGE:`, `Refs:`, `Closes:`
etc.

For multi-commit PRs, each commit is reviewed
individually. The squash-merge produces a single
'what landed' commit on main with a description
covering all sub-commits.

---

## 5. Pull request checklist

Before opening a PR, verify:

- [ ] Branch is up to date with `main`:
  ```sh
  git fetch origin
  git rebase origin/main
  ```
  (rebase, don't merge — keep history linear)
- [ ] All files pass `python3 -c "import ast; ast.parse(open(f).read())"`
  (no syntax errors)
- [ ] `python3 -m rayforge.util.i18n_audit` returns 0 candidates
  (if you added user-facing strings)
- [ ] `python3 -m rayforge.util.contrast_check` returns 0
  (if you added a new color)
- [ ] `pytest tests/gui/ tests/property/` passes locally
  (if you modified a widget or a tested module)
- [ ] Commit messages follow the conventional commits format
- [ ] PR body describes:
  - **What** landed (bullets)
  - **Why** (the problem being solved)
  - **Test plan** (how a reviewer can verify)
  - **Risks** (if any)

---

## 6. Validation gates

Every PR is checked by CI. The gates are:

| Gate | Trigger | Pass criteria |
|---|---|---|
| Lint | Every PR | ruff + pyright pass |
| Backend tests | Every PR | pytest tests/core/ tests/addon_mgr/ passes |
| UI tests | Every PR | pytest tests/gui/ passes |
| Property tests | Every PR | 100 iterations × 8 properties pass |
| i18n check | Every PR | `i18n_extract --check` exits 0 |
| Contrast check | Every PR | `contrast_check` exits 0 |
| Perf gate | Every PR | `benchmarks --compare` < 10% regression |

The i18n and contrast checks are **advisory** today
(warnings, not errors). The other gates are blocking.

To run all gates locally:

```sh
pixi run -e test pytest tests/ -v
python3 -m rayforge.util.i18n_audit
python3 -m rayforge.util.contrast_check
python3 -m rayforge.util.benchmarks --output /tmp/bench.json
```

---

## 7. i18n contribution

**Adding a new user-facing string:**

1. Wrap in `_()`:
   ```python
   from rayforge.shared.util.localized import _
   label = Gtk.Label(label=_("Save"))
   ```
2. Run the audit: `python3 -m rayforge.util.i18n_audit`
   (should report 0 candidates)
3. Run the extract: `python3 -m rayforge.util.i18n_extract`
   (updates the .pot and all .po files)
4. Commit both the source change AND the .pot/.po
   changes

**Translating to a new language:**

1. Copy `rayforge/locale/rayforge.pot` to
   `rayforge/locale/<lang>/LC_MESSAGES/rayforge.po`
2. Open in POEdit (or any editor) and translate
3. Test by setting `LANGUAGE=<lang> pixi run pires-forge`
4. Open a PR with the new .po file

**Translation review (existing languages):**

1. Open `rayforge/locale/<lang>/LC_MESSAGES/rayforge.po`
2. Look for `#, fuzzy` entries (these were auto-merged
   and need a translator's eye)
3. Fill in any missing `msgstr` lines
4. Remove the `#, fuzzy` flag

---

## 8. Performance and tracing

**Profiling a slow operation:**

```python
from rayforge.util.tracing import get_tracer
tracer = get_tracer()

with tracer.span("my.slow.op"):
    # ... the slow code ...
```

**Visualizing as a flame graph:**

```sh
RAYFORGE_TRACE=1 pixi run pires-forge
# On exit, the trace report is printed. To get the
# JSON for the flame graph viewer:
python3 -c "
from rayforge.util.tracing import get_tracer
import atexit
tracer = get_tracer()
tracer.enable()
atexit.register(lambda: tracer.export_chrome('/tmp/trace.json'))
"
# Then open /tmp/trace.json in chrome://tracing or
# https://ui.perfetto.dev
```

**Benchmarking a change:**

```sh
# Before the change:
python3 -m rayforge.util.benchmarks --output /tmp/before.json

# After the change:
python3 -m rayforge.util.benchmarks \
  --compare /tmp/before.json \
  --fail-on-regression 10
```

---

## 9. Accessibility

Every new widget that has user-facing text or is
interactive should have AT-SPI metadata. Use the
helpers in `rayforge/shared/util/a11y.py`:

```python
from rayforge.shared.util.a11y import (
    set_a11y_label, mark_live_region,
)

set_a11y_label(
    my_button,
    label=_("Save"),
    description=_("Save the current document"),
    role=Gtk.AccessibleRole.BUTTON,
)

mark_live_region(my_status_bar, polite=True)
```

Verify with orca: `orca &` then launch pires-forge.
Tab through the UI and confirm every widget announces
correctly.

Run the contrast checker after adding a new color:

```sh
python3 -m rayforge.util.contrast_check
```

If the new color fails AA, either darken the bg,
lighten the fg, or add an entry to `KNOWN_FAILURES`
with a one-line rationale.

---

## 10. Release process

The maintainer cuts releases. The flow:

1. Update `pyproject.toml` version (and `rayforge/const.py`
   if version is read from there)
2. Update `CHANGELOG.md`
3. Tag the commit: `git tag v1.2.3`
4. Push: `git push origin v1.2.3`
5. CI builds and publishes the wheel + SBOM

Contributors don't need to touch versions or tags.
The maintainer does the release engineering at
merge time.

---

## See also

- [USER_MANUAL.md](USER_MANUAL.md) — how to use the app
- [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) — architecture and dev setup
- [ROADMAP.md](ROADMAP.md) — what's planned and what's done
- [PROCESS_JOURNAL.md](PROCESS_JOURNAL.md) — chronological log of recent waves
