import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import updates


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class VersionTests(unittest.TestCase):
    def test_parse_version(self):
        self.assertEqual(updates.parse_version("v1.2.3"), (1, 2, 3))
        self.assertEqual(updates.parse_version("1.2.3"), (1, 2, 3))
        self.assertIsNone(updates.parse_version("latest"))
        self.assertIsNone(updates.parse_version(None))

    def test_version_string(self):
        self.assertEqual(updates.version_string("v2.0.1"), "2.0.1")
        self.assertIsNone(updates.version_string("release"))

    def test_is_newer(self):
        self.assertTrue(updates.is_newer("v1.1.0", "1.0.0"))
        self.assertFalse(updates.is_newer("1.0.0", "1.0.0"))
        self.assertFalse(updates.is_newer("1.0.0", "1.1.0"))
        self.assertFalse(updates.is_newer("nope", "1.0.0"))


class AssetTests(unittest.TestCase):
    def setUp(self):
        self.assets = [
            {
                "name": "Spendly-1.1.0-Setup.exe",
                "url": "https://example.com/setup",
                "size": 100,
                "digest": None,
            },
            {
                "name": "Spendly-1.1.0-Update.exe",
                "url": "https://example.com/update",
                "size": 50,
                "digest": "sha256:" + "a" * 64,
            },
            {
                "name": "Spendly-1.1.0-portable.zip",
                "url": "https://example.com/portable",
                "size": 25,
                "digest": "sha256:" + "b" * 64,
            },
        ]

    def test_installed_prefers_lite_installer(self):
        asset = updates.select_asset(self.assets, "1.1.0", False)
        self.assertEqual(asset["name"], "Spendly-1.1.0-Update.exe")

    def test_installed_falls_back_to_setup(self):
        assets = [self.assets[0]]
        asset = updates.select_asset(assets, "1.1.0", False)
        self.assertEqual(asset["name"], "Spendly-1.1.0-Setup.exe")

    def test_portable_uses_zip(self):
        asset = updates.select_asset(self.assets, "1.1.0", True)
        self.assertEqual(asset["name"], "Spendly-1.1.0-portable.zip")

    def test_missing_asset(self):
        self.assertIsNone(updates.select_asset([], "1.1.0", False))

    def test_digest_for(self):
        self.assertEqual(updates.digest_for(self.assets[1]), "a" * 64)
        self.assertIsNone(updates.digest_for(self.assets[0]))
        self.assertIsNone(updates.digest_for({"digest": "sha256:xyz"}))


class FetchTests(unittest.TestCase):
    def payload(self):
        return {
            "tag_name": "v1.1.0",
            "name": "Spendly 1.1.0",
            "body": "Update notes",
            "published_at": "2026-11-05T00:00:00Z",
            "html_url": "https://github.com/robolivice/spendly/releases/tag/v1.1.0",
            "draft": False,
            "prerelease": False,
            "assets": [
                {
                    "name": "Spendly-1.1.0-Update.exe",
                    "browser_download_url": "https://example.com/update",
                    "size": 123,
                    "digest": "sha256:" + "c" * 64,
                }
            ],
        }

    def test_fetch_latest(self):
        response = FakeResponse(self.payload())
        with patch.object(updates, "urlopen", return_value=response):
            release = updates.fetch_latest()
        self.assertEqual(release["version"], "1.1.0")
        self.assertEqual(release["notes"], "Update notes")
        self.assertEqual(release["assets"][0]["size"], 123)
        self.assertEqual(updates.digest_for(release["assets"][0]), "c" * 64)

    def test_fetch_rejects_prerelease(self):
        payload = self.payload()
        payload["prerelease"] = True
        response = FakeResponse(payload)
        with patch.object(updates, "urlopen", return_value=response):
            with self.assertRaises(updates.UpdateError):
                updates.fetch_latest()

    def test_ps_quote(self):
        self.assertEqual(updates._ps_quote("C:\\it's here"), "'C:\\it''s here'")


@unittest.skipUnless(sys.platform == "win32", "Windows only")
class InstallTests(unittest.TestCase):
    def test_helper_spawn_uses_hidden_process_without_detaching(self):
        manager = updates.UpdateManager()
        target = Path(tempfile.gettempdir()) / "spendly-test-update.exe"
        target.write_bytes(b"update")
        release = {
            "version": "1.2.1",
            "assets": [
                {
                    "name": "Spendly-1.2.1-Update.exe",
                    "digest": "sha256:" + "d" * 64,
                }
            ],
        }
        manager._download = {
            "state": "ready",
            "asset_name": "Spendly-1.2.1-Update.exe",
            "target": str(target),
        }
        try:
            with patch.object(updates, "sha256_file", return_value="d" * 64), patch.object(
                updates.paths, "is_frozen", return_value=True
            ), patch.object(updates.sys, "platform", "win32"), patch.object(
                manager, "_state", return_value={"cached_release": release}
            ), patch.object(updates.subprocess, "Popen") as popen:
                ok, _message = manager.install()
        finally:
            target.unlink(missing_ok=True)
        self.assertTrue(ok)
        flags = popen.call_args.kwargs["creationflags"]
        self.assertTrue(flags & updates.subprocess.CREATE_NO_WINDOW)
        self.assertFalse(
            flags & getattr(updates.subprocess, "DETACHED_PROCESS", 0)
        )


if __name__ == "__main__":
    unittest.main()
