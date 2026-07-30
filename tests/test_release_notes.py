"""
Tests for scripts/release_notes.py.

The script generates release notes from PR titles, using
the GitHub REST API. We test the pure-Python helpers
(extract_section, is_security, format_pr, parse_args)
without hitting the network.
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add scripts/ to the path so we can import release_notes
SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import release_notes  # noqa: E402


class TestExtractSection:
    """Extract the conventional-commit section from a PR title."""

    def test_feat(self):
        assert release_notes.extract_section("feat(ui): new dialog") == "Features"

    def test_fix(self):
        assert release_notes.extract_section("fix: oops") == "Bug fixes"

    def test_perf(self):
        assert release_notes.extract_section("perf(render): 2x speedup") == "Performance"

    def test_docs(self):
        assert release_notes.extract_section("docs: typo fix") == "Documentation"

    def test_ci(self):
        assert release_notes.extract_section("ci: new workflow") == "Continuous integration"

    def test_with_scope(self):
        assert release_notes.extract_section("feat(machine): add pause") == "Features"

    def test_breaking_marker(self):
        # The ! is preserved but doesn't change section
        assert release_notes.extract_section("feat(api)!: breaking") == "Features"

    def test_unknown_type(self):
        assert release_notes.extract_section("random: thing") == "Other"

    def test_no_prefix(self):
        assert release_notes.extract_section("Just a title") == "Other"

    def test_uppercase(self):
        # Convention is lowercase, but be lenient
        assert release_notes.extract_section("FEAT: new thing") == "Features"


class TestIsSecurity:
    """Check if PR is security-sensitive."""

    def test_security_label(self):
        pr = {"title": "anything", "labels": [{"name": "security"}]}
        assert release_notes.is_security(pr) is True

    def test_security_in_title(self):
        pr = {
            "title": "fix: CVE-2024-1234 in dep",
            "labels": [],
            "body": "",
        }
        assert release_notes.is_security(pr) is True

    def test_xss_in_title(self):
        pr = {
            "title": "fix(xss): escape user input",
            "labels": [],
            "body": "",
        }
        assert release_notes.is_security(pr) is True

    def test_xxe_in_body(self):
        pr = {
            "title": "feat: parse SVG",
            "labels": [],
            "body": "Blocks XXE attacks via defusedxml.",
        }
        assert release_notes.is_security(pr) is True

    def test_injection(self):
        pr = {
            "title": "fix: command injection in sketcher",
            "labels": [],
            "body": "",
        }
        assert release_notes.is_security(pr) is True

    def test_normal_pr(self):
        pr = {
            "title": "feat: add dark mode toggle",
            "labels": [],
            "body": "Just a UI improvement.",
        }
        assert release_notes.is_security(pr) is False

    def test_empty_body(self):
        pr = {"title": "feat: thing", "labels": [], "body": None}
        assert release_notes.is_security(pr) is False


class TestFormatPr:
    """Format a PR as a Markdown bullet."""

    def test_basic(self):
        pr = {
            "title": "feat: new dialog",
            "number": 42,
            "user": {"login": "alice"},
        }
        result = release_notes.format_pr(pr)
        assert result == "- feat: new dialog (#42, @alice)"

    def test_missing_user(self):
        pr = {
            "title": "fix: bug",
            "number": 1,
            "user": {},
        }
        result = release_notes.format_pr(pr)
        assert result == "- fix: bug (#1, @)"


class TestParseArgs:
    """Argument parsing."""

    def test_required_args(self):
        with patch.object(sys, "argv", ["release_notes.py"]):
            with pytest.raises(SystemExit):
                release_notes.parse_args()

    def test_defaults(self, monkeypatch):
        monkeypatch.setattr(
            sys, "argv", ["release_notes.py", "--from-tag", "1.0.0"]
        )
        monkeypatch.setenv("GITHUB_TOKEN", "test")
        args = release_notes.parse_args()
        assert args.from_tag == "1.0.0"
        assert args.to_tag == "HEAD"
        assert args.repo == "yuri-schmaltz/rayforge"
        assert args.token == "test"
        assert args.out == "-"

    def test_explicit(self, monkeypatch):
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "release_notes.py",
                "--from-tag",
                "1.0.0",
                "--to-tag",
                "2.0.0",
                "--repo",
                "foo/bar",
                "--token",
                "abc",
                "--out",
                "/tmp/out.md",
            ],
        )
        args = release_notes.parse_args()
        assert args.from_tag == "1.0.0"
        assert args.to_tag == "2.0.0"
        assert args.repo == "foo/bar"
        assert args.token == "abc"
        assert args.out == "/tmp/out.md"


class TestGenerateIntegration:
    """End-to-end test with mocked GitHub API."""

    def test_generate_basic(self, monkeypatch):
        # Mock the API calls
        monkeypatch.setattr(sys, "argv", ["x", "--from-tag", "1.0.0"])
        monkeypatch.setenv("GITHUB_TOKEN", "test")

        # Mock merge_base response
        merge_base_response = {
            "merge_base_commit": {"sha": "abc1234567890"},
        }
        # Mock PR list response
        pr_list_response = [
            {
                "title": "feat: add thing",
                "number": 1,
                "user": {"login": "alice"},
                "merged_at": "2026-01-01T00:00:00Z",
                "merge_commit_sha": "def4567890",
                "labels": [],
                "body": "",
            },
            {
                "title": "fix: CVE-2024-1234",
                "number": 2,
                "user": {"login": "bob"},
                "merged_at": "2026-01-02T00:00:00Z",
                "merge_commit_sha": "7890abcdef",
                "labels": [],
                "body": "",
            },
        ]

        with patch.object(
            release_notes,
            "gh_request",
            side_effect=[
                merge_base_response,
                pr_list_response,
                [],  # page 2 (empty)
            ],
        ):
            notes = release_notes.generate(
                "foo/bar", "1.0.0", "HEAD", "test"
            )

        # Security PR is at the top
        assert "## Security" in notes
        assert "CVE-2024-1234" in notes
        # Features section
        assert "## Features" in notes
        assert "add thing" in notes
        # Auto-generated footer
        assert "Auto-generated" in notes

    def test_generate_no_prs(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["x", "--from-tag", "1.0.0"])
        monkeypatch.setenv("GITHUB_TOKEN", "test")

        with patch.object(
            release_notes,
            "gh_request",
            side_effect=[
                {"merge_base_commit": {"sha": "abc"}},
                [],
            ],
        ):
            notes = release_notes.generate(
                "foo/bar", "1.0.0", "HEAD", "test"
            )
        assert "No merged PRs" in notes

    def test_generate_no_merge_base(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["x", "--from-tag", "1.0.0"])
        monkeypatch.setenv("GITHUB_TOKEN", "test")

        with patch.object(
            release_notes,
            "gh_request",
            return_value={},  # No merge_base_commit
        ):
            with pytest.raises(SystemExit) as e:
                release_notes.generate(
                    "foo/bar", "1.0.0", "HEAD", "test"
                )
        assert e.value.code == 1
