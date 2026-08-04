# Git Hooks

This directory contains project-local git hooks. They are not
installed by default — opt in with:

```
git config core.hooksPath .githooks
```

Hooks here will then run automatically on `git commit` /
`git push` instead of the global `~/.git/hooks/` ones.

## Available hooks

- `pre-commit` — runs lightweight checks on staged files:
  - Python syntax (`py_compile`) on every staged `.py`
  - Soft-warns about raw hex colors in CSS property values
    (prefers `@define-color` tokens; see DESIGN_SYSTEM.md)
  - Soft-warns when a token in `forge.css` is removed but
    still referenced elsewhere
  - Warns about files larger than 512 KB

  All checks are **soft** except the Python syntax one, which
  blocks the commit. The CSS / size checks are advisory so
  they don't block legitimate work; CI runs the strict
  versions of these checks in
  `.github/workflows/ci.yml`.

## Skipping a hook

For a single commit when you know the check is wrong:

```
git commit --no-verify
```

Please don't make a habit of it.
