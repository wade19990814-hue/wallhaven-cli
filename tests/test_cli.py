import contextlib
import io
import json
from email.message import Message
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wallhaven_cli import cli as wallhaven


class FakeResponse:
    def __init__(self, body, content_type="application/json"):
        self._body = body
        self.headers = Message()
        self.headers["Content-Type"] = content_type

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


class WallhavenCliTests(unittest.TestCase):
    def run_subcommand(self, argv):
        args = wallhaven.build_parser().parse_args(argv)
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout), self.assertRaises(SystemExit) as exited:
            args.func(args)
        return exited.exception.code, json.loads(stdout.getvalue())

    def test_wallpaper_id_accepts_only_supported_urls(self):
        for value in (
            "wq37kp",
            "https://wallhaven.cc/w/wq37kp?ref=example",
            "whvn.cc/wq37kp",
            "https://whvn.cc/wq37kp",
        ):
            self.assertEqual(wallhaven._wallpaper_id(value), "wq37kp")

        for value in (
            "https://wallhaven.cc/tag/wq37kp",
            "https://evilwallhaven.cc/w/wq37kp",
            "https://wallhaven.cc/w/not-an-id",
        ):
            with self.assertRaises(wallhaven.CliError):
                wallhaven._wallpaper_id(value)

    def test_search_accepts_documented_ratio_and_returns_json(self):
        payload = {"data": [], "meta": {"current_page": 1, "last_page": 1, "total": 0}}
        with mock.patch.object(wallhaven, "_request", return_value=payload) as request:
            code, result = self.run_subcommand(["search", "--ratios", "16x9"])

        self.assertEqual(code, 0)
        self.assertTrue(result["ok"])
        self.assertIn("ratios=16x9", request.call_args.args[0])

    def test_invalid_parser_argument_is_json(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout), self.assertRaises(SystemExit) as exited:
            wallhaven.main(["search", "--page", "invalid"])

        self.assertEqual(exited.exception.code, 2)
        result = json.loads(stdout.getvalue())
        self.assertFalse(result["ok"])
        self.assertIn("--page", result["error"]["message"])

    def test_request_rejects_malformed_json(self):
        response = FakeResponse(b"not valid json")
        with mock.patch.object(wallhaven.urllib.request, "urlopen", return_value=response):
            with self.assertRaises(wallhaven.CliError) as raised:
                wallhaven._request("https://wallhaven.cc/api/v1/search")

        self.assertEqual(raised.exception.code, 4)
        self.assertIn("malformed JSON", str(raised.exception))

    def test_download_uses_atomic_write(self):
        wallpaper = {
            "id": "wq37kp",
            "url": "https://wallhaven.cc/w/wq37kp",
            "thumbs": {"large": "https://th.wallhaven.cc/lg/wq/wq37kp.jpg"},
            "path": "https://w.wallhaven.cc/full/wq/wallhaven-wq37kp.jpg",
        }
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.object(wallhaven, "_detail", return_value=wallpaper), mock.patch.object(
                wallhaven, "_request", return_value=b"image-bytes"
            ):
                code, result = self.run_subcommand(["download", "wq37kp", "--out", directory])

            target = Path(result["file"]["path"])
            self.assertEqual(code, 0)
            self.assertEqual(target.read_bytes(), b"image-bytes")
            self.assertFalse(target.with_name(target.name + ".part").exists())

    def test_settings_requires_key(self):
        with mock.patch.object(wallhaven, "_api_key", return_value=""):
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = wallhaven.main(["settings"])
            self.assertEqual(code, 3)
            result = json.loads(stdout.getvalue())
            self.assertFalse(result["ok"])

    def test_settings_success(self):
        fake_settings = {"data": {"thumb_size": "small", "per_page": "24", "purity": ["sfw"]}}
        with mock.patch.object(wallhaven, "_api_key", return_value="test-key"), mock.patch.object(
            wallhaven, "_request", return_value=fake_settings
        ):
            code, result = self.run_subcommand(["settings"])
            self.assertEqual(code, 0)
            self.assertTrue(result["ok"])
            self.assertEqual(result["settings"]["thumb_size"], "small")

    def test_tag_success(self):
        fake_tag = {"data": {"id": 1, "name": "anime", "category": "Anime & Manga"}}
        with mock.patch.object(wallhaven, "_request", return_value=fake_tag):
            code, result = self.run_subcommand(["tag", "1"])
            self.assertEqual(code, 0)
            self.assertTrue(result["ok"])
            self.assertEqual(result["tag"]["name"], "anime")

    def test_tag_invalid_id(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = wallhaven.main(["tag", "abc"])
        self.assertEqual(code, 2)
        result = json.loads(stdout.getvalue())
        self.assertFalse(result["ok"])
        self.assertIn("integer", result["error"]["message"])

    def test_collections_own_requires_key(self):
        with mock.patch.object(wallhaven, "_api_key", return_value=""):
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = wallhaven.main(["collections"])
            self.assertEqual(code, 3)
            result = json.loads(stdout.getvalue())
            self.assertFalse(result["ok"])

    def test_collections_own_success(self):
        fake_cols = {"data": [{"id": 123, "label": "Favorites", "count": 10}]}
        with mock.patch.object(wallhaven, "_api_key", return_value="test-key"), mock.patch.object(
            wallhaven, "_request", return_value=fake_cols
        ):
            code, result = self.run_subcommand(["collections"])
            self.assertEqual(code, 0)
            self.assertTrue(result["ok"])
            self.assertEqual(len(result["collections"]), 1)

    def test_collections_user_public(self):
        fake_cols = {"data": [{"id": 456, "label": "Public Collection", "count": 5}]}
        with mock.patch.object(wallhaven, "_request", return_value=fake_cols):
            code, result = self.run_subcommand(["collections", "--user", "someone"])
            self.assertEqual(code, 0)
            self.assertTrue(result["ok"])
            self.assertEqual(result["user"], "someone")
            self.assertEqual(len(result["collections"]), 1)

    def test_collections_id_requires_user(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = wallhaven.main(["collections", "--id", "123"])
        self.assertEqual(code, 2)
        result = json.loads(stdout.getvalue())
        self.assertFalse(result["ok"])
        self.assertIn("--user", result["error"]["message"])

    def test_collections_items_success(self):
        fake_items = {
            "data": [
                {
                    "id": "wq37kp",
                    "url": "https://wallhaven.cc/w/wq37kp",
                    "purity": "sfw",
                    "resolution": "2560x1440",
                }
            ],
            "meta": {"current_page": 1, "last_page": 1, "total": 1},
        }
        with mock.patch.object(wallhaven, "_request", return_value=fake_items):
            code, result = self.run_subcommand(["collections", "--user", "someone", "--id", "123"])
            self.assertEqual(code, 0)
            self.assertTrue(result["ok"])
            self.assertEqual(result["collection_id"], 123)
            self.assertEqual(len(result["items"]), 1)
            self.assertEqual(result["items"][0]["id"], "wq37kp")


if __name__ == "__main__":
    unittest.main()
