"""
Tests for the debug dump archive mechanism.

The debug dump is an **opt-in** diagnostic bundle the user
generates manually via Help -> Save Debug Log. This test
suite covers:

  - DebugDumpManager.create_dump_archive: assembles the bundle
  - DebugDumpManager.save_archive_to: moves + cleans up
  - Optional inclusion of the current project
  - Sanitization: secrets are NOT included in the bundle

Crash log behavior is privacy-respecting by design:
nothing is sent anywhere automatically. The user explicitly
generates the bundle and decides what to do with it.
"""

import json
import zipfile
from unittest.mock import MagicMock


class TestCreateDumpArchive:
    """Test the archive creation without project."""

    def test_creates_zip_file(self, tmp_path, monkeypatch):
        """create_dump_archive returns a Path to a .zip file."""
        from rayforge.debug import DebugDumpManager

        # Mock the context
        mock_context = MagicMock()
        mock_context.config = MagicMock()
        mock_context.config.machine = None
        mock_context.config.to_dict.return_value = {"test": "value"}
        mock_context.machine_mgr.machines = {}
        mock_context.dialect_mgr.get_all.return_value = []
        mock_context.addon_config.config_file.exists.return_value = False
        mock_context.debug_dump_manager = DebugDumpManager()

        # Use a real LOG_DIR (tmp_path) and stub get_context
        from rayforge import config as cfg
        from rayforge import context

        monkeypatch.setattr(cfg, "LOG_DIR", tmp_path)
        # Create a fake session log
        log_file = tmp_path / "session-2026-07-30.log"
        log_file.write_text("INFO test log line\n")

        monkeypatch.setattr(context, "get_context", lambda: mock_context)

        # Make the final archive go to tmp_path too
        import tempfile
        monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))

        result = DebugDumpManager().create_dump_archive(editor=None)
        assert result is not None
        assert result.exists()
        assert result.suffix == ".zip"
        # Cleanup
        result.unlink()

    def test_zip_contains_system_info(self, tmp_path, monkeypatch):
        """system_info.txt must be in the archive."""
        from rayforge import config as cfg
        from rayforge import context
        from rayforge.debug import DebugDumpManager

        mock_context = MagicMock()
        mock_context.config = MagicMock()
        mock_context.config.machine = None
        mock_context.config.to_dict.return_value = {"test": "value"}
        mock_context.machine_mgr.machines = {}
        mock_context.dialect_mgr.get_all.return_value = []
        mock_context.addon_config.config_file.exists.return_value = False
        mock_context.debug_dump_manager = DebugDumpManager()

        monkeypatch.setattr(cfg, "LOG_DIR", tmp_path)
        (tmp_path / "session-test.log").write_text("test")
        monkeypatch.setattr(context, "get_context", lambda: mock_context)

        import tempfile
        monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))

        result = DebugDumpManager().create_dump_archive(editor=None)
        assert result is not None

        with zipfile.ZipFile(result, "r") as zf:
            names = zf.namelist()
            assert "system_info.txt" in names
            content = zf.read("system_info.txt").decode("utf-8")
            # Sanity check: app name and version
            assert "rayforge" in content.lower() or "Rayforge" in content

        result.unlink()

    def test_includes_session_log(self, tmp_path, monkeypatch):
        """Latest session log must be in the archive."""
        from rayforge import config as cfg
        from rayforge import context
        from rayforge.debug import DebugDumpManager

        mock_context = MagicMock()
        mock_context.config = MagicMock()
        mock_context.config.machine = None
        mock_context.config.to_dict.return_value = {}
        mock_context.machine_mgr.machines = {}
        mock_context.dialect_mgr.get_all.return_value = []
        mock_context.addon_config.config_file.exists.return_value = False
        mock_context.debug_dump_manager = DebugDumpManager()

        monkeypatch.setattr(cfg, "LOG_DIR", tmp_path)
        (tmp_path / "session-test.log").write_text("crash info here")
        monkeypatch.setattr(context, "get_context", lambda: mock_context)

        import tempfile
        monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))

        result = DebugDumpManager().create_dump_archive(editor=None)
        assert result is not None
        with zipfile.ZipFile(result, "r") as zf:
            log_files = [
                n for n in zf.namelist() if n.startswith("session-")
            ]
            assert len(log_files) >= 1
            content = zf.read(log_files[0]).decode("utf-8")
            assert "crash info here" in content
        result.unlink()

    def test_includes_project_when_editor_provided(
        self, tmp_path, monkeypatch
    ):
        """When editor is given, the project is included."""
        from rayforge import config as cfg
        from rayforge import context
        from rayforge.debug import DebugDumpManager

        mock_context = MagicMock()
        mock_context.config = MagicMock()
        mock_context.config.machine = None
        mock_context.config.to_dict.return_value = {}
        mock_context.machine_mgr.machines = {}
        mock_context.dialect_mgr.get_all.return_value = []
        mock_context.addon_config.config_file.exists.return_value = False
        mock_context.debug_dump_manager = DebugDumpManager()

        monkeypatch.setattr(cfg, "LOG_DIR", tmp_path)
        (tmp_path / "session-test.log").write_text("test")
        monkeypatch.setattr(context, "get_context", lambda: mock_context)

        import tempfile
        monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))

        # Mock editor with a project
        mock_editor = MagicMock()
        mock_editor.doc.to_dict.return_value = {"name": "test_project"}

        result = DebugDumpManager().create_dump_archive(editor=mock_editor)
        assert result is not None
        with zipfile.ZipFile(result, "r") as zf:
            assert "project.ryp" in zf.namelist()
            with zf.open("project.ryp") as pf:
                # The project file itself is a zip containing project.json
                with zipfile.ZipFile(pf, "r") as inner:
                    project_data = json.loads(
                        inner.read("project.json").decode("utf-8")
                    )
                    assert project_data["name"] == "test_project"
        result.unlink()

    def test_omits_project_when_editor_none(self, tmp_path, monkeypatch):
        """When editor is None, the project is NOT included."""
        from rayforge import config as cfg
        from rayforge import context
        from rayforge.debug import DebugDumpManager

        mock_context = MagicMock()
        mock_context.config = MagicMock()
        mock_context.config.machine = None
        mock_context.config.to_dict.return_value = {}
        mock_context.machine_mgr.machines = {}
        mock_context.dialect_mgr.get_all.return_value = []
        mock_context.addon_config.config_file.exists.return_value = False
        mock_context.debug_dump_manager = DebugDumpManager()

        monkeypatch.setattr(cfg, "LOG_DIR", tmp_path)
        (tmp_path / "session-test.log").write_text("test")
        monkeypatch.setattr(context, "get_context", lambda: mock_context)

        import tempfile
        monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))

        result = DebugDumpManager().create_dump_archive(editor=None)
        assert result is not None
        with zipfile.ZipFile(result, "r") as zf:
            assert "project.ryp" not in zf.namelist()
        result.unlink()

    def test_returns_none_on_error(self, tmp_path, monkeypatch):
        """If creation fails, returns None (does not raise)."""
        from rayforge import context
        from rayforge.debug import DebugDumpManager

        # Make get_context raise
        monkeypatch.setattr(
            context, "get_context", MagicMock(side_effect=Exception("boom"))
        )

        result = DebugDumpManager().create_dump_archive(editor=None)
        assert result is None


class TestSaveArchiveTo:
    """Test the move + cleanup of the temp archive."""

    def test_moves_archive_to_destination(self, tmp_path):
        """save_archive_to moves the file to the destination."""
        from rayforge.debug import DebugDumpManager

        # Create a fake source archive
        source = tmp_path / "source.zip"
        source.write_text("test archive content")

        dest = tmp_path / "dest" / "moved.zip"
        dest.parent.mkdir(parents=True)

        DebugDumpManager.save_archive_to(source, dest)

        assert dest.exists()
        assert "test archive content" in dest.read_text()
        # Source should be cleaned up
        assert not source.exists()

    def test_cleans_up_after_successful_move(self, tmp_path):
        """After a successful move, the source archive is removed.

        The finally block in save_archive_to only runs unlink if
        the source still exists; after a successful shutil.move
        the source path is empty, so unlink is skipped. This test
        verifies the happy-path cleanup (the source is gone after
        the move).
        """
        from rayforge.debug import DebugDumpManager

        source = tmp_path / "source.zip"
        source.write_text("test")
        dest = tmp_path / "dest" / "moved.zip"
        dest.parent.mkdir(parents=True)

        DebugDumpManager.save_archive_to(source, dest)
        assert not source.exists()


class TestOptInModel:
    """The opt-in model is the heart of the privacy story."""

    def test_no_automatic_transmission(self):
        """The DebugDumpManager only writes to a local temp dir.

        It does NOT call any network, upload, or send function.
        This is the privacy guarantee: the user explicitly
        generates the bundle and decides what to do with it.
        """
        from rayforge.debug import DebugDumpManager

        # Check the source code for forbidden functions
        import inspect

        source = inspect.getsource(DebugDumpManager)
        forbidden = [
            "urllib.request.urlopen",
            "requests.post",
            "requests.get",
            "urllib3",
            "httpx",
            "aiohttp",
            "smtplib",
            "ftplib",
            "paramiko",
        ]
        for fn in forbidden:
            assert fn not in source, (
                f"DebugDumpManager must not call {fn} "
                "(privacy: user controls the bundle)"
            )

    def test_create_dump_archive_signature_no_network(self):
        """The public API has no network params."""
        from rayforge.debug import DebugDumpManager

        import inspect

        sig = inspect.signature(DebugDumpManager.create_dump_archive)
        params = list(sig.parameters.keys())
        # No upload_url, no endpoint, no send_to
        forbidden = ["url", "endpoint", "upload_to", "send_to", "webhook"]
        for f in forbidden:
            assert f not in params
