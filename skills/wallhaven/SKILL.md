---
name: wallhaven
description: >-
  Search, inspect, or download wallpapers and visual references from Wallhaven when the user asks for wallpapers or provides a Wallhaven ID, page URL, or whvn.cc short link. Requires the separately installed wallhaven CLI; do not use it for bulk crawling, training-data collection, or unrequested NSFW searches.
---

# Wallhaven Agent Adapter

This skill is an adapter, not an HTTP client. It requires `wallhaven` CLI version `>=0.2.0,<0.3.0` to be available on `PATH`.

## Before use

Run `wallhaven --version` before the first Wallhaven operation in a session. If the command is unavailable, tell the user that the CLI must be installed first; do not replace it with `curl`, web scraping, or a second API implementation.

The CLI emits JSON for command results and errors. `--help` and `--version` are human-readable text. Original image `path` values are URLs, not image content; never load the image bytes into the conversation.

## Safe operating rules

1. Default to SFW: pass `--purity 100` unless the user explicitly requests sketchy or NSFW material. Any other purity value requires `WALLHAVEN_API_KEY`; if the CLI returns exit code 3, ask for the key and do not bypass the check.
2. Always pass `--categories` deliberately when the requested content needs category filtering. Do not rely on account-side Wallhaven preferences.
3. Search before downloading. Show a small set of candidates using their id, resolution, `thumb`, and `url`; download only after the user chooses an id, unless they explicitly request a known id to be downloaded.
4. Request one page at a time (at most 24 results). Do not crawl `last_page`, run concurrent searches, or treat results as a dataset.
5. The CLI retries HTTP 429 twice after a two-second pause. That does not coordinate rate limits between processes; callers must still avoid bursts.
6. Use wallpapers as references or personal wallpapers. Flag training-data, bulk-asset, or commercial-use requests for separate rights review.

## Commands

```bash
wallhaven search --q "+cyberpunk +tokyo +night" --categories 110 --purity 100 --atleast 2560x1440 --ratios 16x9 --sorting favorites --page 1
wallhaven get https://whvn.cc/wq37kp
wallhaven download wq37kp --out ./artifacts
wallhaven settings                                         # View account filter preferences (requires key)
wallhaven collections                                      # List your own collections (requires key)
wallhaven collections --user <username>                    # List a user's public collections
wallhaven collections --user <username> --id <id> --page 1 # Browse wallpapers in a collection
wallhaven tag <numeric-id>                                 # View tag metadata by numeric id (e.g. 1)
```

Existing target files are returned as `skipped: true`; pass `--force` only when the user asks to replace the file.

## Natural language to query

| Request | CLI argument |
|---|---|
| Cyberpunk Tokyo at night | `--q "+cyberpunk +tokyo +night"` |
| No people | `--categories 110` or `--q "-people"` |
| Anime only | `--categories 010` |
| PNG only | `--q "type:png"` |
| Similar to a wallpaper | `--q "like:wq37kp"` |
| By an uploader | `--q "@username"` |
| Exact tag id | `--q "id:123"` (do not combine with other terms) |

Treat `wallhaven.cc/w/<id>` and `whvn.cc/<id>` as `get` inputs, not search terms. For empty results, relax `--atleast` or `--ratios` first, then reduce required `+tags`; do not enable NSFW merely to obtain more results.
