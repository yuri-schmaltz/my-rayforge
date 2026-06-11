"""
Resilience tests for license providers (Gumroad, Patreon) and the
addon registry fetch, validating the retry/cache-fallback behaviour
added in the Onda 1 and Onda 2 hardening cycle.
"""

import io
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from rayforge.license import (
    GumroadProvider,
    LicenseStatus,
    LicenseType,
)
from rayforge.license import PatreonProvider


# ---------------------------------------------------------------------------
# Gumroad – resilience
# ---------------------------------------------------------------------------


class TestGumroadResilience:
    @pytest.fixture
    def provider(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = GumroadProvider(Path(tmpdir))
            p.add_license("PROD1", "KEY1")
            yield p

    def test_network_error_uses_cache_fallback(self, provider):
        """When the HTTP call returns None, cached result is returned."""
        provider._cache["PROD1"] = {
            "status": "valid",
            "message": "Cached valid",
            "license_type": "one_time",
            "customer_email": None,
            "last_validated": datetime.now().isoformat(),
            "metadata": {},
        }

        with patch(
            "rayforge.license.gumroad_provider.resilient_post",
            return_value=None,
        ):
            result = provider.validate({"product_ids": ["PROD1"]})

        assert result.status == LicenseStatus.VALID
        assert result.message == "Cached valid"

    def test_network_error_without_cache_returns_error(self, provider):
        """None response with empty cache returns ERROR result."""
        with patch(
            "rayforge.license.gumroad_provider.resilient_post",
            return_value=None,
        ):
            result = provider.validate({"product_ids": ["PROD1"]})

        assert result.status == LicenseStatus.ERROR
        assert "Gumroad" in result.message or "Network" in result.message

    def test_valid_response_parsed_correctly(self, provider):
        import json

        payload = {
            "success": True,
            "purchase": {
                "email": "user@example.com",
                "product_name": "Test Addon",
                "sale_timestamp": "2026-01-01T00:00:00Z",
            },
        }
        with patch(
            "rayforge.license.gumroad_provider.resilient_post",
            return_value=json.dumps(payload).encode(),
        ):
            result = provider.validate({"product_ids": ["PROD1"]})

        assert result.status == LicenseStatus.VALID
        assert result.customer_email == "user@example.com"
        assert result.license_type == LicenseType.ONE_TIME

    def test_invalid_license_response(self, provider):
        import json

        payload = {"success": False}
        with patch(
            "rayforge.license.gumroad_provider.resilient_post",
            return_value=json.dumps(payload).encode(),
        ):
            result = provider.validate({"product_ids": ["PROD1"]})

        assert result.status == LicenseStatus.INVALID

    def test_refunded_purchase_returns_invalid(self, provider):
        import json

        payload = {
            "success": True,
            "purchase": {"refunded": True},
        }
        with patch(
            "rayforge.license.gumroad_provider.resilient_post",
            return_value=json.dumps(payload).encode(),
        ):
            result = provider.validate({"product_ids": ["PROD1"]})

        assert result.status == LicenseStatus.INVALID
        assert "refunded" in result.message.lower()


# ---------------------------------------------------------------------------
# Patreon – resilience
# ---------------------------------------------------------------------------


class TestPatreonResilience:
    @pytest.fixture
    def provider(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = PatreonProvider(Path(tmpdir), "client_id")
            p._access_token = "token"
            yield p

    def test_network_error_uses_cache_fallback(self, provider):
        provider._cache["TIER1"] = {
            "status": "valid",
            "message": "Cached",
            "license_type": "subscription",
            "customer_email": None,
            "last_validated": datetime.now().isoformat(),
            "metadata": {},
        }

        with patch(
            "rayforge.license.patreon_provider.resilient_get",
            return_value=None,
        ):
            result = provider.validate({"patreon_tier_ids": ["TIER1"]})

        assert result.status == LicenseStatus.VALID

    def test_network_error_without_cache_returns_error(self, provider):
        with patch(
            "rayforge.license.patreon_provider.resilient_get",
            return_value=None,
        ):
            result = provider.validate({"patreon_tier_ids": ["TIER99"]})

        assert result.status == LicenseStatus.ERROR
        assert "Patreon" in result.message or "Network" in result.message

    def test_active_patron_with_matching_tier_returns_valid(self, provider):
        import json

        api_response = {
            "data": {},
            "included": [
                {
                    "type": "tier",
                    "id": "TIER1",
                    "attributes": {"title": "Supporter"},
                },
                {
                    "type": "member",
                    "id": "MEM1",
                    "attributes": {
                        "patron_status": "active_patron",
                    },
                    "relationships": {
                        "currently_entitled_tiers": {
                            "data": [{"id": "TIER1"}]
                        }
                    },
                },
            ],
        }
        with patch(
            "rayforge.license.patreon_provider.resilient_get",
            return_value=json.dumps(api_response).encode(),
        ):
            result = provider.validate({"patreon_tier_ids": ["TIER1"]})

        assert result.status == LicenseStatus.VALID

    def test_inactive_patron_returns_invalid(self, provider):
        import json

        api_response = {
            "data": {},
            "included": [
                {
                    "type": "member",
                    "id": "MEM1",
                    "attributes": {"patron_status": "former_patron"},
                    "relationships": {
                        "currently_entitled_tiers": {"data": []}
                    },
                }
            ],
        }
        with patch(
            "rayforge.license.patreon_provider.resilient_get",
            return_value=json.dumps(api_response).encode(),
        ):
            result = provider.validate({"patreon_tier_ids": ["TIER1"]})

        assert result.status == LicenseStatus.INVALID


# ---------------------------------------------------------------------------
# AddonManager – registry fetch resilience
# ---------------------------------------------------------------------------


def _make_manager():
    with tempfile.TemporaryDirectory() as tmpdir:
        from unittest.mock import Mock
        from rayforge.addon_mgr.addon_manager import AddonManager

        addons_dir = Path(tmpdir) / "addons"
        plugin_mgr = Mock()
        return AddonManager([addons_dir], addons_dir, plugin_mgr)


class TestAddonRegistryFetch:
    def test_fetch_registry_returns_empty_on_network_failure(self):
        manager = _make_manager()
        with patch(
            "rayforge.addon_mgr.addon_manager.resilient_get",
            return_value=None,
        ):
            result = manager.fetch_registry()

        assert result == []

    def test_fetch_registry_parses_list_format(self):
        manager = _make_manager()
        registry_data = yaml.safe_dump(
            [
                {
                    "name": "my-addon",
                    "version": "1.0.0",
                    "description": "Test",
                    "api_version": 1,
                    "author": "Test",
                    "url": "https://github.com/a/b",
                }
            ]
        ).encode()

        with patch(
            "rayforge.addon_mgr.addon_manager.resilient_get",
            return_value=registry_data,
        ):
            result = manager.fetch_registry()

        assert len(result) == 1
        assert result[0].name == "my-addon"

    def test_fetch_registry_returns_empty_on_bad_yaml(self):
        manager = _make_manager()
        with patch(
            "rayforge.addon_mgr.addon_manager.resilient_get",
            return_value=b"{{{{ invalid yaml!}}}",
        ):
            result = manager.fetch_registry()

        assert result == []


# ---------------------------------------------------------------------------
# AddonManager – zip download resilience
# ---------------------------------------------------------------------------


class TestAddonZipDownload:
    def test_fetch_zip_returns_none_on_network_failure(self):
        from rayforge.addon_mgr.addon_manager import AddonManager

        with patch(
            "rayforge.addon_mgr.addon_manager.resilient_get",
            return_value=None,
        ):
            result = AddonManager._fetch_zip_data("http://example.com/a.zip")

        assert result is None

    def test_fetch_zip_returns_bytes_io_on_success(self):
        from rayforge.addon_mgr.addon_manager import AddonManager

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("test.txt", "hello")
        zip_bytes = buf.getvalue()

        with patch(
            "rayforge.addon_mgr.addon_manager.resilient_get",
            return_value=zip_bytes,
        ):
            result = AddonManager._fetch_zip_data("http://example.com/a.zip")

        assert result is not None
        assert isinstance(result, io.BytesIO)
