import contextlib
import http.client
import io
import json
from email.message import Message
from pathlib import Path
import sys
import ssl
import tempfile
import unittest
import urllib.error
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
        if isinstance(self._body, Exception):
            raise self._body
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


class WallhavenCliTests(unittest.TestCase):
    def setUp(self):
        # Never read the developer's credentials/registry or make a live request.
        self.registry = mock.MagicMock()
        self.registry.OpenKey.side_effect = FileNotFoundError
        patches = [
            mock.patch.dict(wallhaven.os.environ, {wallhaven.KEY_ENV: "", wallhaven.USER_ENV: ""}),
            mock.patch.dict(sys.modules, {"winreg": self.registry}),
            mock.patch.object(wallhaven, "_throttle"),
            mock.patch.object(wallhaven._opener, "open", side_effect=AssertionError("Unexpected network request")),
        ]
        for patch in patches:
            started = patch.start()
            self.addCleanup(patch.stop)
        self.network = started

    def tearDown(self):
        self.network.assert_not_called()

    def run_main(self, argv):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            try:
                code = wallhaven.main(argv)
            except SystemExit as exc:
                code = exc.code
        return code, json.loads(stdout.getvalue())

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
        with mock.patch.object(wallhaven._opener, "open", return_value=response):
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
            "file_size": len(b"image-bytes"),
        }
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.object(wallhaven, "_detail", return_value=wallpaper), mock.patch.object(
                wallhaven, "_request", return_value=b"image-bytes"
            ):
                code, result = self.run_subcommand(["download", "wq37kp", "--out", directory])

            target = Path(result["file"]["path"])
            self.assertEqual(code, 0)
            self.assertEqual(target.read_bytes(), b"image-bytes")
            self.assertEqual(list(Path(directory).glob("*.part")), [])

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

    def test_collections_id_uses_username_env(self):
        fake_items = {
            "data": [],
            "meta": {"current_page": 1, "last_page": 1, "total": 0},
        }
        with mock.patch.object(wallhaven, "_request", return_value=fake_items) as req, \
                mock.patch.dict(wallhaven.os.environ, {"WALLHAVEN_USERNAME": "tester"}, clear=False):
            code, result = self.run_subcommand(["collections", "--id", "123"])
            self.assertEqual(code, 0)
            self.assertTrue(result["ok"])
            self.assertEqual(result["user"], "tester")
            self.assertIn("/collections/tester/123", req.call_args[0][0])

    def test_request_retries_transient_network_error(self):
        responses = [
            urllib.error.URLError("SSL: UNEXPECTED_EOF_WHILE_READING"),
            FakeResponse(json.dumps({"data": {"id": "wq37kp"}}).encode(), "application/json"),
        ]
        calls = {"n": 0}

        def fake_urlopen(req, timeout=30):
            if calls["n"] == 0:
                calls["n"] += 1
                raise responses[0]
            return responses[1]

        with mock.patch.object(wallhaven.time, "sleep") as fake_sleep, \
                mock.patch.object(wallhaven._opener, "open", side_effect=fake_urlopen):
            payload = wallhaven._request("https://wallhaven.cc/api/v1/w/wq37kp")
            self.assertEqual(payload["data"]["id"], "wq37kp")
            fake_sleep.assert_called()

    def test_credentials_environment_takes_precedence(self):
        with mock.patch.dict(wallhaven.os.environ, {
            wallhaven.KEY_ENV: " synthetic-key ", wallhaven.USER_ENV: " example-user ",
        }):
            self.assertEqual(wallhaven._api_key(), "synthetic-key")
            self.assertEqual(wallhaven._username(), "example-user")
        self.registry.OpenKey.assert_not_called()

    def test_credentials_windows_registry_fallback(self):
        self.registry.OpenKey.side_effect = None
        values = {wallhaven.KEY_ENV: " synthetic-key ", wallhaven.USER_ENV: " example-user "}
        self.registry.QueryValueEx.side_effect = lambda handle, name: (values[name], 1)
        with mock.patch.object(wallhaven.sys, "platform", "win32"):
            self.assertEqual(wallhaven._api_key(), "synthetic-key")
            self.assertEqual(wallhaven._username(), "example-user")

    def test_credentials_missing_registry_and_non_windows(self):
        for platform in ("win32", "linux"):
            with self.subTest(platform=platform), mock.patch.object(wallhaven.sys, "platform", platform):
                self.assertEqual(wallhaven._api_key(), "")
                self.assertEqual(wallhaven._username(), "")

    def test_explicit_collection_user_overrides_environment(self):
        with mock.patch.dict(wallhaven.os.environ, {wallhaven.USER_ENV: "saved-user"}), \
                mock.patch.object(wallhaven, "_request", return_value={"data": []}) as request:
            code, result = self.run_main(["collections", "--id", "123", "--user", "chosen-user"])
        self.assertEqual(code, 0)
        self.assertEqual(result["user"], "chosen-user")
        self.assertIn("/collections/chosen-user/123?", request.call_args.args[0])

    def test_non_sfw_requires_key_for_search_and_collection(self):
        for args in (["search"], ["collections", "--user", "example-user", "--id", "123"]):
            with self.subTest(args=args):
                code, result = self.run_main(args + ["--purity", "111"])
                self.assertEqual(code, 3)
                self.assertFalse(result["ok"])

    def test_request_retries_read_failures(self):
        errors = [
            TimeoutError("read timed out"), ConnectionResetError("connection reset"),
            ssl.SSLEOFError("TLS interrupted"), http.client.IncompleteRead(b"partial", 20),
            http.client.RemoteDisconnected("peer closed connection"),
        ]
        for error in errors:
            with self.subTest(error=type(error).__name__), \
                    mock.patch.object(wallhaven.time, "sleep") as sleep, \
                    mock.patch.object(wallhaven._opener, "open", side_effect=[
                        FakeResponse(error), FakeResponse(b'{"data": []}'),
                    ]) as request:
                self.assertEqual(wallhaven._request(wallhaven.API + "/search"), {"data": []})
                self.assertEqual(request.call_count, 2)
                sleep.assert_called_once_with(2)

    def test_network_retry_exhaustion_is_json_exit_five(self):
        errors = [urllib.error.URLError("unreachable"), TimeoutError("timed out"),
                  ConnectionResetError("reset"), ssl.SSLEOFError("TLS interrupted"),
                  http.client.IncompleteRead(b"partial", 20)]
        for error in errors:
            with self.subTest(error=type(error).__name__), \
                    mock.patch.object(wallhaven.time, "sleep") as sleep, \
                    mock.patch.object(wallhaven._opener, "open", return_value=FakeResponse(error)) as request:
                code, result = self.run_main(["search"])
                self.assertEqual(code, 5)
                self.assertFalse(result["ok"])
                self.assertEqual(request.call_count, 3)
                self.assertEqual(sleep.call_args_list, [mock.call(2), mock.call(2)])

    def test_certificate_errors_are_not_retried(self):
        cert_error = ssl.SSLCertVerificationError("certificate rejected")
        for error in (cert_error, urllib.error.URLError(cert_error)):
            with self.subTest(error=type(error).__name__), \
                    mock.patch.object(wallhaven.time, "sleep") as sleep, \
                    mock.patch.object(wallhaven._opener, "open", side_effect=error) as request:
                code, result = self.run_main(["search"])
                self.assertEqual(code, 5)
                self.assertFalse(result["ok"])
                self.assertEqual(request.call_count, 1)
                sleep.assert_not_called()

    def test_http_errors_keep_exit_contract(self):
        for status, expected_code, attempts in ((401, 3, 1), (404, 4, 1), (429, 4, 3), (500, 4, 1)):
            error = urllib.error.HTTPError(wallhaven.API + "/search", status, "HTTP error", {}, io.BytesIO(b""))
            with self.subTest(status=status), mock.patch.object(wallhaven.time, "sleep") as sleep, \
                    mock.patch.object(wallhaven._opener, "open", side_effect=error) as request:
                code, result = self.run_main(["search"])
                self.assertEqual(code, expected_code)
                self.assertFalse(result["ok"])
                self.assertEqual(request.call_count, attempts)
                self.assertEqual(sleep.call_count, attempts - 1)

    def test_http_429_can_recover(self):
        error = urllib.error.HTTPError(wallhaven.API + "/search", 429, "rate limit", {}, io.BytesIO(b""))
        with mock.patch.object(wallhaven.time, "sleep") as sleep, \
                mock.patch.object(wallhaven._opener, "open", side_effect=[error, FakeResponse(b'{}')]):
            self.assertEqual(wallhaven._request(wallhaven.API + "/search"), {})
            sleep.assert_called_once_with(2)

    def test_api_key_is_scoped_to_api_requests(self):
        urls = {
            wallhaven.API + "/search": True,
            "https://wallhaven.cc:443/api/v1/search": True,
            "https://wallhaven.cc/api/v10/search": False,
            "https://wallhaven.cc/api/v1.evil/search": False,
            "https://wallhaven.cc:444/api/v1/search": False,
            "https://wallhaven.cc.evil.invalid/api/v1/search": False,
            "http://wallhaven.cc/api/v1/search": False,
            "https://w.wallhaven.cc/full/wq/wallhaven-wq37kp.jpg": False,
        }
        with mock.patch.object(wallhaven, "_api_key", return_value="synthetic-key"):
            for url, authenticated in urls.items():
                with self.subTest(url=url), mock.patch.object(
                    wallhaven._opener, "open", return_value=FakeResponse(b'{}')
                ) as request:
                    wallhaven._request(url)
                    sent = request.call_args.args[0]
                    self.assertEqual(sent.has_header("X-api-key"), authenticated)

    def test_authenticated_redirects_stay_in_api_scope(self):
        handler = wallhaven._SafeRedirectHandler()
        req = wallhaven.urllib.request.Request(wallhaven.API + "/search", headers={"X-API-Key": "synthetic-key"})
        allowed = handler.redirect_request(req, None, 302, "Found", {}, wallhaven.API + "/w/wq37kp")
        self.assertEqual(allowed.get_header("X-api-key"), "synthetic-key")
        for target in ("https://example.invalid/search", "https://wallhaven.cc/help/api",
                       "https://wallhaven.cc:444/api/v1/search", "http://wallhaven.cc/api/v1/search"):
            response = io.BytesIO(b"redirect body")
            with self.subTest(target=target), self.assertRaises(wallhaven.CliError):
                handler.redirect_request(req, response, 302, "Found", {}, target)
            self.assertTrue(response.closed)

    def test_anonymous_https_redirect_has_no_key_and_rejects_downgrade(self):
        handler = wallhaven._SafeRedirectHandler()
        req = wallhaven.urllib.request.Request("https://w.wallhaven.cc/image.jpg")
        redirected = handler.redirect_request(req, None, 302, "Found", {}, "https://example.invalid/image.jpg")
        self.assertFalse(redirected.has_header("X-api-key"))
        with self.assertRaises(wallhaven.CliError):
            handler.redirect_request(req, None, 302, "Found", {}, "http://example.invalid/image.jpg")
        self.assertTrue(any(isinstance(h, wallhaven._SafeRedirectHandler) for h in wallhaven._opener.handlers))

    def test_response_content_type_is_checked(self):
        for want in ("json", "image"):
            with self.subTest(want=want), mock.patch.object(
                wallhaven._opener, "open", return_value=FakeResponse(b"<html>blocked</html>", "text/html")
            ), self.assertRaises(wallhaven.CliError) as raised:
                wallhaven._request(wallhaven.API + "/search", want=want)
            self.assertEqual(raised.exception.code, 4)

    def test_download_rejects_missing_or_invalid_size(self):
        for size in (None, 0, -1, "100", True):
            with self.subTest(size=size), mock.patch.object(wallhaven, "_detail", return_value={
                "path": "https://w.wallhaven.cc/wallhaven-wq37kp.jpg", "file_size": size,
            }):
                code, result = self.run_main(["download", "wq37kp"])
                self.assertEqual(code, 4)
                self.assertFalse(result["ok"])

    def test_download_file_integrity_and_force(self):
        wallpaper = {"id": "wq37kp", "path": "https://w.wallhaven.cc/wallhaven-wq37kp.jpg", "file_size": 11}
        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.object(wallhaven, "_detail", return_value=wallpaper), \
                mock.patch.object(wallhaven, "_request", return_value=b"bad") as request:
            args = ["download", "wq37kp", "--out", directory]
            target = Path(directory) / "wallhaven-wq37kp.jpg"
            code, result = self.run_main(args)
            self.assertEqual(code, 4)
            self.assertEqual(result["error"]["actual_bytes"], 3)
            self.assertFalse(target.exists())

            target.write_bytes(b"")
            request.reset_mock()
            code, result = self.run_main(args)
            self.assertEqual(code, 4)
            self.assertIn("--force", result["error"]["hint"])
            request.assert_not_called()

            code, result = self.run_main(args + ["--force"])
            self.assertEqual(code, 4)
            self.assertEqual(target.read_bytes(), b"")
            request.return_value = b"image-bytes"
            code, result = self.run_main(args + ["--force"])
            self.assertEqual(code, 0)
            self.assertEqual(target.read_bytes(), b"image-bytes")

            request.reset_mock()
            code, result = self.run_main(args)
            self.assertEqual(code, 0)
            self.assertTrue(result["file"]["skipped"])
            request.assert_not_called()
            self.assertEqual(list(Path(directory).glob("*.part")), [])

    def test_failed_atomic_replace_preserves_original_and_cleans_partial(self):
        wallpaper = {"path": "https://w.wallhaven.cc/wallhaven-wq37kp.jpg", "file_size": 11}
        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.object(wallhaven, "_detail", return_value=wallpaper), \
                mock.patch.object(wallhaven, "_request", return_value=b"image-bytes"), \
                mock.patch.object(wallhaven.os, "replace", side_effect=PermissionError):
            target = Path(directory) / "wallhaven-wq37kp.jpg"
            target.write_bytes(b"keep-original")
            code, result = self.run_main(["download", "wq37kp", "--out", directory, "--force"])
            self.assertEqual(code, 4)
            self.assertFalse(result["ok"])
            self.assertEqual(target.read_bytes(), b"keep-original")
            self.assertEqual(list(Path(directory).glob("*.part")), [])


if __name__ == "__main__":
    unittest.main()
