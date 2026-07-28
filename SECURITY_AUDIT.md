# Security Audit — 2026-07-28

A robust error and vulnerability audit was performed on the `yuri-schmaltz/rayforge`
fork at tag `1.9.0+resilience.4`. The audit combined several industry-standard
tools with manual review of critical files.

## Tools used

| Tool | Purpose | Result |
|------|---------|--------|
| **bandit** | Python security linter (AST-based) | 1 HIGH, 26 MEDIUM, 4001 LOW |
| **ruff** (`--select S`) | Security-focused rules (S101–S7xx) | 55 issues (S101 asserts in tests excluded) |
| **pip-audit** | Vulnerable dependencies (CVE database) | 0 in direct `requirements.txt`; transitive issues only in sandbox's pip, not the project |
| **detect-secrets** | Hardcoded credential scanner | 0 findings |
| **mypy** | Type checker | Sandbox-only "module not found" errors (gi.repository); no real type issues |
| **vulture** | Dead-code detection | 100+ unused imports/variables (code quality, not security) |
| **Custom grep** | shell=True, verify=False, pickle, yaml.load, os.system, etc. | 0 findings |

## Findings

### 🔴 Real issues (fixed in PR #13)

#### 1. `rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/core/params.py` — bare `eval()` (B307 / S307)

The `ParameterContext` class evaluated user-provided math strings with
`eval(str(expression), {"__builtins__": None}, ctx)`. The "disable builtins"
sandbox is bypassable via attribute access on objects in the namespace:

```python
# Classic Python sandbox escape
().__class__.__mro__[1].__subclasses__()
# Equivalent: access any class via the object model
```

Sketch files (`.sketch` format) can be shared, so this was a real attack
surface: a malicious sketch file could execute arbitrary code on import.

**Fix** (PR #13): switch to the AST-whitelisted
`rayforge.core.expression.safe_evaluate` (the same evaluator hardened in
PR #10). Dunder / private attribute access is rejected at the AST level
before any execution. 16 new regression tests cover the classic
sandbox-escape vectors plus 4 sanity tests for legitimate math.

#### 2. `rayforge/core/expression/evaluator.py` — `AttributeError` leaked out of `safe_evaluate`

When a public attribute was missing on a namespace value (e.g.
`n.bit_length()` where `n` is a float), the `_eval_node` handler raised
`AttributeError` from `getattr()`. The exception propagated through
`safe_evaluate` (which only catches `ValueError`, `TypeError`,
`ZeroDivisionError`), breaking the graceful-fail contract used by
`ParameterContext.get()`.

**Fix** (PR #13): convert `AttributeError` to `ValueError` in the
attribute access handler with a clear message including the value type
and the requested attribute name.

#### 3. `rayforge/version.py` — S606/S607 (subprocess with partial path)

`subprocess.check_output(["git", "describe"])` used a partial path.
S607 ("Starting a process with a partial executable path") is a
defence-in-depth warning: a fully-qualified path is more robust on
systems with restricted `PATH` (e.g. snap-confined environments).

**Fix** (PR #13): resolve `git` via `shutil.which()` first; early-return
`None` when `git` is not on `PATH`. S603 (subprocess untrusted input)
suppressed with a comment + `# noqa` since the resolved `git` is
trusted and the second argument is a hardcoded constant.

### 🟢 False positives (kept with justification)

| ID | Location | Description | Why it's safe |
|----|----------|-------------|---------------|
| B102 / S102 | `rayforge/uiscript.py:57` | `exec(code, script_globals)` | **Intended feature**: the `--uiscript` CLI option lets the user run a Python script with access to the app/window context. Documented at the top of the file. The user explicitly passes the script path on the command line. |
| B324 / S324 | `rayforge/pipeline/intent_builder.py:1075` | `hashlib.sha1(blob).digest()` | **Content hashing, not security**: SHA-1 is used to derive a stable 63-bit cache key from a canonical JSON payload. No adversarial input — the payload is internal to the app. Marked for future migration to `usedforsecurity=False` (Python 3.9+) for clarity. |
| B307 / S307 | `rayforge/core/expression/evaluator.py` (PR #10) | None — already migrated to AST whitelist. | n/a |
| B314 / S314 | `rayforge/image/lightburn/{importer,renderer}.py` (11x) | `xml.etree.ElementTree.fromstring()` | **LightBurn `.lbrn` file format is XML**, but the parser is built-in and the files come from the user's local filesystem. The threat model (user opening a malicious file) is the same as opening a malicious `.svg` or `.docx` — accepted. For higher security, the project could migrate to `defusedxml` (already in `pixi.lock` deps). |
| B310 / S310 | `rayforge/shared/util/http.py`, `rayforge/shared/oauth/flow.py` (14x) | `urllib.request.urlopen()` | **URLs are either hardcoded (oauth providers) or passed in by the user via settings**. The resilient layer doesn't accept user-supplied URLs from untrusted input. |
| B104 / S104 | `rayforge/machine/driver/ruida/ruida_simulator.py` (5x) | `host = "0.0.0.0"` | **Intended for the simulator**: the simulator is a testing tool that needs to accept connections from the host. Production code binds to the configured machine address. |
| S606 | `rayforge/version.py` | `subprocess.check_output` | **Fixed in PR #13** — now uses `shutil.which` and a `# noqa` for S603. |
| B101 / S101 | All tests | `assert` statements | **Standard pytest pattern**. Asserts are removed only when running with `python -O`, which is never done in tests or production. |

### ✅ Clean checks

- **No `shell=True`** in any subprocess call.
- **No `verify=False`** in any SSL/TLS context.
- **No `pickle.loads()`** on untrusted input.
- **No `yaml.load()`** (only `yaml.safe_load()`).
- **No `os.system()`** or `os.popen()`.
- **No hardcoded credentials** (no API keys, tokens, passwords, or PATs in source).
- **No `DEBUG = True`** in production code.
- **No secrets in commit history** (verified via `git log -p`).
- **0 vulnerabilities in direct dependencies** (`pip-audit -r requirements.txt --no-deps`).
- **0 detect-secrets findings** across the entire repository.

## Recommendations (not yet implemented)

1. **Migrate `intent_builder.py:1075` to `usedforsecurity=False`** — the
   Python 3.9+ idiom for non-security hashes. Improves clarity even
   though the current usage is safe.

2. **Consider `defusedxml` for LightBurn XML parsing** — the project
   already pulls `defusedxml` in via pixi for tests, so the cost is
   near zero. Adds XML-bomb / billion-laughs protection for
   untrusted `.lbrn` files.

3. **Add a bandit step to CI** — the current `lint-test.yml` only runs
   flake8 + pyright + pyflakes. A bandit step would catch regressions
   like the sketcher eval before they merge.

4. **Add a pip-audit step to CI** — already present in
   `security-perf.yml` (gated to `barebaric/rayforge`). Ungate it for
   the fork so transitive CVEs are caught early.

5. **Review remaining `S110` (try/except pass)** — 17 occurrences.
   These are mostly in image importers and config loaders where the
   fallback is benign. Consider logging the exception at debug level
   so the user can diagnose failures.

6. **Document the `--uiscript` feature** as a security boundary in
   the user-facing docs. Users who run the app in a multi-tenant
   environment should be aware that anyone with command-line access
   can execute arbitrary Python in the app's process context.

## Tools added / unlocked

- `.github/workflows/build-deb.yml` — new fork-friendly workflow that
  builds the Ubuntu 24.04 `.deb` and uploads it as a CI artifact
  (PR `b52f5bc7`). The upstream `publish-deb.yml` is gated to
  `barebaric/rayforge` and not available on forks.
