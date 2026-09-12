#!/usr/bin/env python3
"""Wallhaven CLI: search / get / download, stable JSON on stdout."""

import argparse
import http.client
import json
import os
import re
import ssl
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

from . import __version__

API = "https://wallhaven.cc/api/v1"
KEY_ENV = "WALLHAVEN_API_KEY"
USER_ENV = "WALLHAVEN_USERNAME"
VERSION = __version__
USER_AGENT = f"wallhaven-cli/{VERSION}"

SORTING = {"date_added", "relevance", "random", "views", "favorites", "toplist"}
ORDER = {"desc", "asc"}
TOP_RANGE = {"1d", "3d", "1w", "1M", "3M", "6M", "1y"}
ID_RE = re.compile(r"^[A-Za-z0-9]{6}$")
RES_RE = re.compile(r"^\d{3,5}x\d{3,5}$")
RATIO_RE = re.compile(r"^\d{1,3}x\d{1,3}$")
COLOR_RE = re.compile(r"^[0-9a-fA-F]{6}$")
TRIPLE_RE = re.compile(r"^[01]{3}$")

# Official API allows roughly 45 requests/minute per account or IP.
RATE_LIMIT = 45
RATE_WINDOW = 60.0
_hits = []


class CliError(Exception):
    def __init__(self, message, code=2, **detail):
        super().__init__(message)
        self.code = code
        self.detail = detail


class JsonArgumentParser(argparse.ArgumentParser):
    """Return machine-readable errors for invalid command arguments."""

    def error(self, message):
        _write({"ok": False, "error": {"message": message}})
        raise SystemExit(2)


def _throttle():
    now = time.monotonic()
    while _hits and now - _hits[0] > RATE_WINDOW:
        _hits.pop(0)
    if len(_hits) >= RATE_LIMIT:
        time.sleep(RATE_WINDOW - (now - _hits[0]))
        _hits.clear()
    _hits.append(time.monotonic())


def _api_key():
    key = os.environ.get(KEY_ENV, "").strip()
    if key or sys.platform != "win32":
        return key
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as handle:
            return str(winreg.QueryValueEx(handle, KEY_ENV)[0]).strip()
    except OSError:
        return ""


def _username():
    user = os.environ.get(USER_ENV, "").strip()
    if user or sys.platform != "win32":
        return user
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as handle:
            return str(winreg.QueryValueEx(handle, USER_ENV)[0]).strip()
    except OSError:
        return ""


def _is_api_url(url):
    parsed = urllib.parse.urlsplit(url)
    return (
        parsed.scheme == "https"
        and parsed.hostname == "wallhaven.cc"
        and parsed.port in (None, 443)
        and parsed.username is None
        and parsed.password is None
        and parsed.path.startswith("/api/v1/")
    )


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        error = None
        if urllib.parse.urlsplit(newurl).scheme != "https":
            error = "Refusing a redirect to a non-HTTPS URL."
        elif req.has_header("X-api-key") and not _is_api_url(newurl):
            error = "Refusing to forward the API key outside the Wallhaven API."
        if error:
            if fp is not None:
                fp.close()
            raise CliError(error, 4)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_opener = urllib.request.build_opener(_SafeRedirectHandler())


def _request(url, timeout=30, want="json"):
    for attempt in range(3):
        _throttle()
        headers = {"User-Agent": USER_AGENT}
        key = _api_key() if _is_api_url(url) else ""
        if key:
            headers["X-API-Key"] = key
        req = urllib.request.Request(url, headers=headers)
        try:
            with _opener.open(req, timeout=timeout) as resp:
                body = resp.read()
                ctype = resp.headers.get_content_type()
            if want == "image":
                if not ctype.startswith("image/"):
                    raise CliError(f"Download returned {ctype}, not an image.", 4, url=url)
                return body
            if ctype != "application/json":
                raise CliError(f"Wallhaven API returned {ctype} instead of JSON.", 4, url=url)
            try:
                return json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise CliError("Wallhaven API returned malformed JSON.", 4, url=url) from exc
        except urllib.error.HTTPError as exc:
            exc.close()
            if exc.code == 429 and attempt < 2:
                time.sleep(2)
                continue
            if exc.code == 401:
                raise CliError(
                    f"{KEY_ENV} is set but rejected by Wallhaven (401).",
                    3,
                    hint="Check the key, or unset it to search SFW anonymously.",
                ) from exc
            if exc.code == 404:
                raise CliError("Not found on Wallhaven.", 4, status=404, url=url) from exc
            raise CliError(f"Wallhaven API returned HTTP {exc.code}.", 4, status=exc.code, url=url) from exc
        except (urllib.error.URLError, TimeoutError, ConnectionError,
                ssl.SSLError, http.client.IncompleteRead) as exc:
            reason = exc.reason if isinstance(exc, urllib.error.URLError) else exc
            if attempt < 2 and not isinstance(reason, ssl.SSLCertVerificationError):
                time.sleep(2)
                continue
            raise CliError(f"Network error talking to Wallhaven: {reason}", 5) from exc


def _slim(data):
    return {
        "id": data.get("id"),
        "url": data.get("url"),
        "purity": data.get("purity"),
        "category": data.get("category"),
        "resolution": data.get("resolution"),
        "ratio": data.get("ratio"),
        "file_type": data.get("file_type"),
        "file_size": data.get("file_size"),
        "favorites": data.get("favorites"),
        "created_at": data.get("created_at"),
        "path": data.get("path"),
        "thumb": (data.get("thumbs") or {}).get("large"),
    }


def _wallpaper_id(raw):
    candidate = raw.strip()
    if ID_RE.fullmatch(candidate):
        return candidate

    url = candidate if "://" in candidate or candidate.startswith("//") else f"https://{candidate}"
    parsed = urllib.parse.urlsplit(url)
    host = (parsed.hostname or "").lower()
    parts = [part for part in parsed.path.split("/") if part]

    if host in {"wallhaven.cc", "www.wallhaven.cc"} and len(parts) == 2 and parts[0] == "w":
        if ID_RE.fullmatch(parts[1]):
            return parts[1]
    if host in {"whvn.cc", "www.whvn.cc"} and len(parts) == 1:
        if ID_RE.fullmatch(parts[0]):
            return parts[0]
    raise CliError(f"'{raw}' is not a Wallhaven wallpaper id or URL.", 2)


def cmd_settings(args):
    if not _api_key():
        raise CliError(
            "settings requires a valid API key.",
            3,
            hint=f"Set {KEY_ENV} from your Wallhaven account settings.",
        )
    payload = _request(f"{API}/settings")
    data = payload.get("data")
    if not data:
        raise CliError("Failed to retrieve account settings.", 4)
    _emit({"ok": True, "command": "settings", "settings": data})


def cmd_tag(args):
    tag_id = args.id.strip()
    if not tag_id.isdigit():
        raise CliError(f"Tag ID '{args.id}' must be an integer.", 2)
    payload = _request(f"{API}/tag/{tag_id}")
    data = payload.get("data")
    if not data:
        raise CliError(f"Tag {tag_id} returned no data.", 4)
    _emit({"ok": True, "command": "tag", "tag": data})


def cmd_collections(args):
    user = args.user.strip() if args.user else ""
    cid = args.id.strip() if args.id else ""
    if cid and not user:
        user = _username()

    if cid and not user:
        raise CliError(
            f"Querying collection items by --id needs a username: pass --user <name> or set {USER_ENV}.",
            2,
            hint=f"Set {USER_ENV} once (e.g. setx {USER_ENV} your-username) so future sessions resolve it automatically.",
        )
    purity = args.purity

    if not TRIPLE_RE.match(purity):
        raise CliError("purity must be a 3-char binary string like 100 or 111.", 2)
    if purity != "100" and not _api_key():
        raise CliError(
            f"purity={purity} needs a valid API key; Wallhaven returns SFW-only silently without one.",
            3,
            hint=f"Set {KEY_ENV} from your Wallhaven account settings, or use --purity 100.",
        )
    if args.page < 1:
        raise CliError("page must be >= 1.", 2)

    if cid and user:
        params = {"purity": purity, "page": args.page}
        payload = _request(f"{API}/collections/{user}/{cid}?{urllib.parse.urlencode(params)}")
        meta = payload.get("meta") or {}
        _emit({
            "ok": True,
            "command": "collections",
            "user": user,
            "collection_id": int(cid) if cid.isdigit() else cid,
            "items": [_slim(item) for item in payload.get("data") or []],
            "meta": {
                "page": meta.get("current_page"),
                "last_page": meta.get("last_page"),
                "total": meta.get("total"),
                "purity": purity,
            },
        })

    if user:
        payload = _request(f"{API}/collections/{user}")
        _emit({
            "ok": True,
            "command": "collections",
            "user": user,
            "collections": payload.get("data") or [],
        })

    if not _api_key():
        raise CliError(
            "Listing your own collections requires a valid API key.",
            3,
            hint=f"Set {KEY_ENV}, or specify --user <username> to view public collections.",
        )
    payload = _request(f"{API}/collections")
    _emit({
        "ok": True,
        "command": "collections",
        "collections": payload.get("data") or [],
    })


def cmd_search(args):
    purity = args.purity
    categories = args.categories
    if not TRIPLE_RE.match(purity) or not TRIPLE_RE.match(categories):
        raise CliError("purity/categories must be 3-char binary strings like 100 or 111.", 2)
    if purity != "100" and not _api_key():
        # Wallhaven answers 200 and silently drops everything above sfw,
        # which looks like "no results" to the caller. Refuse instead.
        raise CliError(
            f"purity={purity} needs a valid API key; Wallhaven returns SFW-only silently without one.",
            3,
            hint=f"Set {KEY_ENV} from your Wallhaven account settings, or use --purity 100.",
        )
    if args.sorting not in SORTING:
        raise CliError(f"sorting must be one of: {', '.join(sorted(SORTING))}.", 2)
    if args.order not in ORDER:
        raise CliError("order must be desc or asc.", 2)
    top_range = args.top_range
    if top_range and args.sorting != "toplist":
        top_range = None
    if top_range and top_range not in TOP_RANGE:
        raise CliError(f"topRange must be one of: {', '.join(sorted(TOP_RANGE))}.", 2)
    if args.atleast and not RES_RE.match(args.atleast):
        raise CliError("atleast must look like 2560x1440.", 2)
    resolutions = _split_list(args.resolutions)
    ratios = _split_list(args.ratios)
    for value in resolutions:
        if not RES_RE.match(value):
            raise CliError(f"resolution '{value}' must look like 2560x1440.", 2)
    for value in ratios:
        if not RATIO_RE.match(value):
            raise CliError(f"ratio '{value}' must look like 16x9.", 2)
    colors = _split_list(args.colors)
    for value in colors:
        if not COLOR_RE.match(value.lstrip("#")):
            raise CliError(f"color '{value}' must be 6 hex digits without '#'.", 2)
    colors = [value.lstrip("#").lower() for value in colors]
    if args.page < 1:
        raise CliError("page must be >= 1.", 2)

    params = {
        "categories": categories,
        "purity": purity,
        "sorting": args.sorting,
        "order": args.order,
        "page": args.page,
    }
    if args.q:
        params["q"] = args.q
    if top_range:
        params["topRange"] = top_range
    if args.atleast:
        params["atleast"] = args.atleast
    if resolutions:
        params["resolutions"] = ",".join(resolutions)
    if ratios:
        params["ratios"] = ",".join(ratios)
    if colors:
        params["colors"] = ",".join(colors)

    payload = _request(f"{API}/search?{urllib.parse.urlencode(params)}")
    meta = payload.get("meta") or {}
    _emit({
        "ok": True,
        "command": "search",
        "items": [_slim(item) for item in payload.get("data") or []],
        "meta": {
            "page": meta.get("current_page"),
            "last_page": meta.get("last_page"),
            "total": meta.get("total"),
            "query_sent": params.get("q"),
            "purity": purity,
            "categories": categories,
        },
    })


def _split_list(value):
    return [part.strip() for part in (value or "").split(",") if part.strip()]


def _detail(wid):
    payload = _request(f"{API}/w/{wid}")
    data = payload.get("data")
    if not data:
        raise CliError(f"Wallpaper {wid} returned no data.", 4)
    return data


def cmd_get(args):
    data = _detail(_wallpaper_id(args.id))
    item = _slim(data)
    item["source"] = data.get("source") or None
    item["views"] = data.get("views")
    item["tags"] = [tag.get("name") for tag in data.get("tags") or []]
    item["uploader"] = (data.get("uploader") or {}).get("username")
    _emit({"ok": True, "command": "get", "item": item})


def cmd_download(args):
    data = _detail(_wallpaper_id(args.id))
    remote = data.get("path")
    if not remote:
        raise CliError("Wallpaper detail has no original image path.", 4)
    expected = data.get("file_size")
    if type(expected) is not int or expected <= 0:
        raise CliError("Wallpaper detail has no valid file size; cannot verify the download.", 4)
    outdir = os.path.abspath(args.out)
    try:
        os.makedirs(outdir, exist_ok=True)
    except OSError as exc:
        raise CliError("Could not create the output directory.", 4, path=outdir) from exc
    target = os.path.join(outdir, os.path.basename(urllib.parse.urlsplit(remote).path))
    if os.path.exists(target) and not args.force:
        try:
            valid = os.path.isfile(target) and os.path.getsize(target) == expected
        except OSError as exc:
            raise CliError("Could not inspect the existing download.", 4, path=target) from exc
        if not valid:
            raise CliError("Existing target does not match the expected file size.", 4,
                           path=target, hint="Use --force to replace it with a verified download.")
        _emit({"ok": True, "command": "download", "item": _slim(data),
               "file": {"path": target, "bytes": expected, "skipped": True}})
    body = _request(remote, timeout=120, want="image")
    if len(body) != expected:
        raise CliError("Download size does not match Wallhaven metadata.", 4,
                       expected_bytes=expected, actual_bytes=len(body))
    partial = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=outdir, prefix=os.path.basename(target) + ".", suffix=".part", delete=False
        ) as handle:
            partial = handle.name
            handle.write(body)
        os.replace(partial, target)
    except OSError as exc:
        if partial is not None:
            try:
                os.remove(partial)
            except OSError:
                pass
        raise CliError("Could not save the download.", 4, path=target) from exc
    _emit({"ok": True, "command": "download", "item": _slim(data),
           "file": {"path": target, "bytes": len(body)}})


def _emit(payload):
    _write(payload)
    raise SystemExit(0)


def _write(payload):
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    try:
        sys.stdout.write(text + "\n")
    except UnicodeEncodeError:
        sys.stdout.buffer.write((text + "\n").encode("utf-8"))


def build_parser():
    parser = JsonArgumentParser(prog="wallhaven", description="Wallhaven search/get/download as JSON.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search", help="search wallpapers (1 page = 24 items)")
    s.add_argument("--q", default=None, help='query, e.g. "+tokyo +night" or "like:94x38z"')
    s.add_argument("--categories", default="111", help="general/anime/people as 1/0 triplet")
    s.add_argument("--purity", default="100", help="sfw/sketchy/nsfw as 1/0 triplet (needs key if not 100)")
    s.add_argument("--sorting", default="relevance")
    s.add_argument("--order", default="desc")
    s.add_argument("--top-range", dest="top_range", default=None, help="only with --sorting toplist")
    s.add_argument("--atleast", default=None, help="minimum resolution, e.g. 2560x1440")
    s.add_argument("--resolutions", default=None, help="exact resolutions, comma separated")
    s.add_argument("--ratios", default=None, help="e.g. 16x9,16x10")
    s.add_argument("--colors", default=None, help="comma separated hex without #")
    s.add_argument("--page", type=int, default=1)
    s.set_defaults(func=cmd_search)

    g = sub.add_parser("get", help="one wallpaper with tags")
    g.add_argument("id", help="wallpaper id, or a wallhaven.cc / whvn.cc URL")
    g.set_defaults(func=cmd_get)

    d = sub.add_parser("download", help="save the original image")
    d.add_argument("id")
    d.add_argument("-o", "--out", default=".", help="output directory")
    d.add_argument("--force", action="store_true", help="re-download if the file exists")
    d.set_defaults(func=cmd_download)

    set_p = sub.add_parser("settings", help="view account settings and filter preferences (requires key)")
    set_p.set_defaults(func=cmd_settings)

    t = sub.add_parser("tag", help="view tag metadata by numeric tag id")
    t.add_argument("id", help="numeric tag id (e.g. 1)")
    t.set_defaults(func=cmd_tag)

    c = sub.add_parser("collections", help="list collections or browse items in a collection")
    c.add_argument("--user", default=None, help="username (omitted = own collections, requires key)")
    c.add_argument("--id", default=None, help="collection id (requires --user or WALLHAVEN_USERNAME)")
    c.add_argument("--purity", default="100", help="sfw/sketchy/nsfw as 1/0 triplet (needs key if not 100)")
    c.add_argument("--page", type=int, default=1)
    c.set_defaults(func=cmd_collections)
    return parser


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except (ValueError, OSError):
            pass
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except CliError as err:
        _write({"ok": False, "error": {"message": str(err), **err.detail}})
        return err.code
    except Exception:
        _write({"ok": False, "error": {"message": "Unexpected internal error."}})
        return 4
    return 0


if __name__ == "__main__":
    sys.exit(main())
