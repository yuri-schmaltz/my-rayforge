#!/usr/bin/env python3
"""
Generate a Software Bill of Materials (SBOM) for the Pires Forge
runtime dependency tree.

Outputs both:
  - CycloneDX 1.5 JSON (machine-readable, the SPDX-compatible
    format that GitHub's dependency submission API accepts and
    that most compliance tooling ingests)
  - SPDX 2.3 JSON (the de-facto standard for legal / procurement)

Run via:
    python3 scripts/generate_sbom.py                # online (PyPI lookups)
    python3 scripts/generate_sbom.py --offline      # offline (no network)
    python3 scripts/generate_sbom.py --format spdx  # SPDX only
    python3 scripts/generate_sbom.py --version 1.1.0  # override version

The output files are written to `dist/sbom/`:
    dist/sbom/pires-forge.cdx.json    # CycloneDX 1.5
    dist/sbom/pires-forge.spdx.json   # SPDX 2.3

Why a custom script vs. `cyclonedx-py` or `pip-licenses`?
  - `cyclonedx-py` doesn't ship with the pixi env by default and
    adds a non-trivial dep tree.
  - `pip-licenses` outputs a custom format, not standard SBOM.
  - The script below uses only stdlib + the locked `requirements.txt`
    so it works without modifying `pixi.toml`. The "rich" part of
    the SBOM (vulns, licenses per package) is filled in where the
    metadata is publicly available; the rest is best-effort.

Note: the script deliberately does NOT do SCA (vulnerability
scanning). `pip-audit` covers that in `security-perf.yml`.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
REQUIREMENTS = REPO_ROOT / "requirements.txt"
OUTPUT_DIR = REPO_ROOT / "dist" / "sbom"
PYPI_URL = "https://pypi.org/pypi/{name}/{version}/json"


def load_locked_versions() -> list[tuple[str, str]]:
    """Parse requirements.txt for pinned (==) packages."""
    pkgs = []
    for line in REQUIREMENTS.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^([A-Za-z0-9._\-\[\]]+)\s*==\s*([A-Za-z0-9._\-+!]+)$", line)
        if m:
            pkgs.append((m.group(1), m.group(2)))
    return pkgs


def fetch_pypi_metadata(name: str, version: str) -> dict[str, Any]:
    """Fetch package metadata from PyPI's JSON API. Returns empty
    dict on network error so the SBOM generation still works
    offline."""
    try:
        with urllib.request.urlopen(PYPI_URL.format(name=name, version=version), timeout=10) as r:
            data = json.loads(r.read())
        return {
            "name": data["info"]["name"],
            "version": data["info"]["version"],
            "license": (data["info"].get("license") or "").strip() or "UNKNOWN",
            "homepage": data["info"].get("home_page") or data["info"].get("project_url") or "",
            "summary": (data["info"].get("summary") or "").strip(),
            "dependencies": [
                d.split(";")[0].split(" ")[0].split("[")[0]
                for d in (data["info"].get("requires_dist") or [])
                if d and "extra" not in d  # skip extras for the runtime SBOM
            ],
        }
    except Exception as e:
        return {"name": name, "version": version, "license": "UNKNOWN",
                "homepage": "", "summary": "", "dependencies": [],
                "fetch_error": str(e)}


def cdx_bom(packages: list[dict[str, Any]], project_version: str) -> dict[str, Any]:
    """Build a CycloneDX 1.5 BOM JSON."""
    components = []
    dependencies = []
    for p in packages:
        components.append({
            "type": "library",
            "bom-ref": f"pkg:pypi/{p['name']}@{p['version']}",
            "name": p["name"],
            "version": p["version"],
            "purl": f"pkg:pypi/{p['name']}@{p['version']}",
            "licenses": ([{"license": {"name": p["license"]}}]
                        if p["license"] and p["license"] != "UNKNOWN" else []),
            "externalReferences": ([
                {"type": "website", "url": p["homepage"]}
            ] if p["homepage"] else []),
        })
        dependencies.append({
            "ref": f"pkg:pypi/{p['name']}@{p['version']}",
            "dependsOn": [f"pkg:pypi/{d}@*"
                           for d in p["dependencies"] if d != p["name"]],
        })
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{generate_uuid()}",
        "version": 1,
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tools": [{"name": "pires-forge-generate-sbom", "version": "1.0.0"}],
            "component": {
                "type": "application",
                "bom-ref": f"pkg:pypi/pires-forge@{project_version}",
                "name": "pires-forge",
                "version": project_version,
            },
        },
        "components": components,
        "dependencies": dependencies,
    }


def spdx_bom(packages: list[dict[str, Any]], project_version: str) -> dict[str, Any]:
    """Build an SPDX 2.3 SBOM JSON."""
    packages_spdx = []
    for p in packages:
        packages_spdx.append({
            "SPDXID": f"SPDXRef-PKG-{p['name'].upper().replace('-', '').replace('_', '').replace('.', '-')}",
            "name": p["name"],
            "versionInfo": p["version"],
            "downloadLocation": f"https://pypi.org/project/{p['name']}/{p['version']}/",
            "licenseConcluded": p["license"] if p["license"] != "UNKNOWN" else "NOASSERTION",
            "licenseDeclared": p["license"] if p["license"] != "UNKNOWN" else "NOASSERTION",
            "externalRefs": ([{
                "referenceCategory": "PACKAGE-MANAGER",
                "referenceType": "purl",
                "referenceLocator": f"pkg:pypi/{p['name']}@{p['version']}",
            }] if True else []),
        })
    return {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"pires-forge-{project_version}-sbom",
        "documentNamespace": f"https://github.com/yuri-schmaltz/pires-forge/sbom/{generate_uuid()}",
        "creationInfo": {
            "created": datetime.now(timezone.utc).isoformat(),
            "creators": ["Tool: pires-forge-generate-sbom-1.0.0"],
        },
        "packages": packages_spdx,
    }


def generate_uuid() -> str:
    """Generate a UUID4 (RFC 4122) for SBOM identifiers."""
    import uuid
    return str(uuid.uuid4())


def get_project_version() -> str:
    """Get the project version from pixi.toml."""
    pixi = (REPO_ROOT / "pixi.toml").read_text()
    m = re.search(r'^name = "pires-forge"\s*\nversion = "([^"]+)"', pixi, re.MULTILINE)
    return m.group(1) if m else "0.0.0"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true",
                    help="Skip PyPI lookups; produce a basic SBOM with version + name only.")
    ap.add_argument("--format", choices=["cyclonedx", "spdx", "both"], default="both")
    ap.add_argument("--version", default=None,
                    help="Override the project version (otherwise read from pixi.toml). "
                         "Pass this from CI workflows so the SBOM matches the tag "
                         "(e.g. --version 1.1.0 when triggered by tag v1.1.0).")
    args = ap.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"=== Generating SBOM (offline={args.offline}, format={args.format}) ===")
    print(f"Output dir: {OUTPUT_DIR}")

    locked = load_locked_versions()
    print(f"Found {len(locked)} pinned packages in {REQUIREMENTS.name}")
    project_version = args.version or get_project_version()
    print(f"Project version: {project_version}")

    packages = []
    for i, (name, version) in enumerate(locked):
        if args.offline:
            meta = {"name": name, "version": version, "license": "UNKNOWN",
                    "homepage": "", "summary": "", "dependencies": []}
        else:
            meta = fetch_pypi_metadata(name, version)
            print(f"  [{i+1}/{len(locked)}] {name}=={version} -> "
                  f"{'OK' if 'fetch_error' not in meta else 'FAIL: ' + meta['fetch_error']}")
        packages.append(meta)

    if args.format in ("cyclonedx", "both"):
        out = OUTPUT_DIR / "pires-forge.cdx.json"
        out.write_text(json.dumps(cdx_bom(packages, project_version), indent=2))
        print(f"  Wrote {out} ({out.stat().st_size//1024} KB)")
    if args.format in ("spdx", "both"):
        out = OUTPUT_DIR / "pires-forge.spdx.json"
        out.write_text(json.dumps(spdx_bom(packages, project_version), indent=2))
        print(f"  Wrote {out} ({out.stat().st_size//1024} KB)")

    print("Done.")


if __name__ == "__main__":
    main()
