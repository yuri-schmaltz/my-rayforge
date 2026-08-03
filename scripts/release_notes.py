#!/usr/bin/env python3
"""
Auto-generate release notes for the fork from PR titles.

Usage:
    python scripts/release_notes.py --from-tag v0.0.0 \\
                                    --to-tag v0.0.0

Output: a Markdown-formatted changelog section for the
release. Designed to be pasted into CHANGELOG.md or used
as the body of a GitHub release.

Privacy: only uses data from the public fork repository.
No personal data is sent anywhere.

The script uses the GitHub REST API with the GITHUB_TOKEN
environment variable (or PAT passed via --token). It
respects rate limits (5000 req/hour authenticated).

Exit code 0 on success, 1 on failure.
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# Conventional Commit prefixes that map to CHANGELOG sections.
# See https://www.conventionalcommits.org/ for the spec.
SECTION_MAP = {
    "feat": "Features",
    "fix": "Bug fixes",
    "perf": "Performance",
    "refactor": "Refactoring",
    "docs": "Documentation",
    "test": "Tests",
    "ci": "Continuous integration",
    "build": "Build system",
    "chore": "Chores",
    "style": "Style",
    "revert": "Reverts",
}

# Security-sensitive: always promoted to a top section.
SECURITY_PATTERN = re.compile(
    r"\b(security|cve|exploit|injection|xss|xxe|rce|sandbox escape)\b",
    re.IGNORECASE,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate release notes from PR titles."
    )
    parser.add_argument(
        "--repo",
        default="yuri-schmaltz/pires-forge",
        help="GitHub repo (default: yuri-schmaltz/pires-forge).",
    )
    parser.add_argument(
        "--from-tag",
        required=True,
        help="Start tag (exclusive). E.g. v0.0.0",
    )
    parser.add_argument(
        "--to-tag",
        default="HEAD",
        help="End tag (inclusive, default: HEAD). "
        "Can be a tag name, branch name, or commit SHA.",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("GITHUB_TOKEN", ""),
        help="GitHub token (default: $GITHUB_TOKEN).",
    )
    parser.add_argument(
        "--out",
        default="-",
        help="Output file (default: stdout).",
    )
    return parser.parse_args()


def gh_request(
    url: str, token: str, params: Optional[Dict[str, str]] = None
) -> Any:
    """GET a GitHub API endpoint.

    Returns the parsed JSON. The shape depends on the
    endpoint: the compare API returns a dict, the pulls
    API returns a list of PR dicts. Use \`Any\` here so
    callers can iterate / subscript without a cast.
    """
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def get_compare_sha(
    repo: str, from_tag: str, to_tag: str, token: str
) -> str:
    """Get the merge base SHA between from_tag and to_tag."""
    url = f"https://api.github.com/repos/{repo}/compare/{from_tag}...{to_tag}"
    data = gh_request(url, token)
    return data.get("merge_base_commit", {}).get("sha", "")


def _is_valid_sha(s: str) -> bool:
    """Check if s is a 40-char hex SHA."""
    if not s or len(s) != 40:
        return False
    return all(c in "0123456789abcdefABCDEF" for c in s)


def list_prs_between(
    repo: str, from_sha: str, to_sha: str, token: str
) -> List[Dict[str, Any]]:
    """List merged PRs between two SHAs (exclusive of from_sha).

    \`to_sha\` is optional. If it's not a 40-char hex SHA (e.g.
    the literal "HEAD"), it's ignored and all PRs newer than
    \`from_sha\` are returned.

    The same applies to \`from_sha\` and any PR's
    \`merge_commit_sha\`: if not a valid 40-char hex, the PR
    is included (we can't reliably compare partial SHAs).
    """
    # If to_sha is not a real SHA, treat it as unbounded
    if to_sha and not _is_valid_sha(to_sha):
        to_sha = ""

    url = f"https://api.github.com/repos/{repo}/pulls"
    prs = []
    page = 1
    while True:
        data = gh_request(
            url,
            token,
            {
                "state": "closed",
                "base": "main",
                "per_page": "100",
                "page": str(page),
                "sort": "created",
                "direction": "desc",
            },
        )
        for pr in data:
            if pr.get("merged_at") is None:
                continue
            merge_sha = pr.get("merge_commit_sha", "")
            if not merge_sha:
                continue
            # Filter by SHA range (string comparison on hex SHAs)
            # If from_sha or merge_sha aren't valid SHAs, include
            # the PR (we can't reliably compare partial values).
            if (
                from_sha
                and _is_valid_sha(from_sha)
                and _is_valid_sha(merge_sha)
                and merge_sha <= from_sha
            ):
                continue
            if to_sha and merge_sha > to_sha:
                continue
            prs.append(pr)
        if len(data) < 100:
            break
        page += 1
        if page > 10:  # Safety: max 1000 PRs
            break
    return prs


def extract_section(pr_title: str) -> str:
    """Extract the conventional-commit section from a PR title."""
    # Match scope: type(scope)!: description or type: description
    m = re.match(r"^([a-z]+)(?:\([^)]+\))?(!?):\s*", pr_title.lower())
    if not m:
        return "Other"
    ctype = m.group(1)
    return SECTION_MAP.get(ctype, "Other")


def is_security(pr: Dict[str, Any]) -> bool:
    """Check if PR is security-sensitive."""
    title = pr.get("title", "")
    body = pr.get("body", "") or ""
    labels = [l.get("name", "") for l in pr.get("labels", [])]
    if any("security" in l.lower() for l in labels):
        return True
    if SECURITY_PATTERN.search(title) or SECURITY_PATTERN.search(body):
        return True
    return False


def format_pr(pr: Dict[str, Any]) -> str:
    """Format a single PR as a Markdown bullet."""
    title = pr.get("title", "")
    number = pr.get("number", "")
    user = pr.get("user", {}).get("login", "")
    return f"- {title} (#{number}, @{user})"


def generate(
    repo: str,
    from_tag: str,
    to_tag: str,
    token: str,
) -> str:
    """Generate the release notes."""
    # Get the merge base SHA
    from_sha = get_compare_sha(repo, from_tag, to_tag, token)
    if not from_sha:
        sys.stderr.write(
            f"::error::Could not find merge base between "
            f"{from_tag} and {to_tag}\n"
        )
        sys.exit(1)
    sys.stderr.write(f"Merge base: {from_sha[:8]}\n")
    # List PRs
    prs = list_prs_between(repo, from_sha, "HEAD", token)
    sys.stderr.write(f"Found {len(prs)} merged PRs\n")
    # Categorize
    security_prs = []
    sections: Dict[str, List[Dict[str, Any]]] = {
        s: [] for s in SECTION_MAP.values()
    }
    sections["Other"] = []
    for pr in prs:
        if is_security(pr):
            security_prs.append(pr)
        else:
            section = extract_section(pr.get("title", ""))
            sections[section].append(pr)
    # Build the Markdown
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out = []
    out.append(f"## Release notes: {from_tag} → {to_tag} ({today})")
    out.append("")
    if security_prs:
        out.append("### Security")
        out.append("")
        for pr in security_prs:
            out.append(format_pr(pr))
        out.append("")
    for section, sec_prs in sections.items():
        if not sec_prs:
            continue
        out.append(f"### {section}")
        out.append("")
        for pr in sec_prs:
            out.append(format_pr(pr))
        out.append("")
    if not prs:
        out.append("_No merged PRs found between these tags._")
        out.append("")
    out.append("---")
    out.append("")
    out.append(
        f"_Auto-generated by `scripts/release_notes.py`. "
        f"PRs are categorized by Conventional Commit prefix. "
        f"Security-sensitive PRs are promoted to the top "
        f"section._"
    )
    out.append("")
    return "\n".join(out)


def main() -> int:
    args = parse_args()
    if not args.token:
        sys.stderr.write(
            "::error::GITHUB_TOKEN not set. Pass via env var or "
            "--token.\n"
        )
        return 1
    try:
        notes = generate(
            args.repo, args.from_tag, args.to_tag, args.token
        )
    except urllib.error.HTTPError as e:
        sys.stderr.write(
            f"::error::HTTP {e.code} from GitHub: "
            f"{e.read().decode('utf-8')[:200]}\n"
        )
        return 1
    except Exception as e:
        sys.stderr.write(f"::error::{e}\n")
        return 1
    if args.out == "-":
        sys.stdout.write(notes)
    else:
        with open(args.out, "w") as f:
            f.write(notes)
        sys.stderr.write(f"Wrote release notes to {args.out}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
