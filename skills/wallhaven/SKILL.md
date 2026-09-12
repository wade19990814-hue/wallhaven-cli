---
name: wallhaven
description: >-
  Search, inspect, or download wallpapers and visual references from Wallhaven, or browse and back up a user's collections. Use for wallpaper requests and Wallhaven IDs, page URLs, or whvn.cc short links. Requires the separately installed wallhaven CLI; not for bulk crawling or training-data collection.
---

# Wallhaven Agent Adapter

Use the installed `wallhaven` CLI (`>=0.2.1,<0.3.0`); this skill is not a second HTTP client. Check `wallhaven --version` before the first operation in a session. If unavailable or incompatible, ask the user to install or update it rather than substituting raw API calls or scraping.

Command results and errors are JSON; `--help` and `--version` are plain text. Check both the exit code and `ok` before using a result. A failed page is not an empty page.

## Scope and account settings

- Search defaults to `--purity 100` (SFW). Keep that scope unless the user requests other content or an explicitly full backup of their collection. Other purity values require `WALLHAVEN_API_KEY`. On exit code 3, explain how to configure or correct the key locally; never ask the user to paste it into chat.
- Categories are general/anime/people bits (`111` = all, `010` = anime). Purity bits are SFW/sketchy/NSFW. A category filter does not guarantee visual content: excluding the People category does not remove every image containing a person.
- Account filters can affect authenticated results. Use `settings` when investigating unexpected omissions; explicit search flags do not necessarily override tag/user blacklists or AI-art filtering. Do not change the user's preferences.
- Follow the requested action: an ID or URL can be inspected with `get`; it does not itself authorize a download. For an open-ended search, show a few candidates. If the user delegated selection and downloading, work within their criteria without requiring an extra selection step.
- Browse one page at a time. Do not sweep search results as a dataset. A requested collection backup may require pagination. Pace calls across CLI processes: the per-process limiter cannot enforce the shared rate limit (roughly 45 API requests/minute). HTTP 429 and transient network failures get at most two retries, two seconds apart; report failures that remain.
- Finding or downloading an image does not grant reuse rights. Use `source` to investigate attribution or licensing when reuse is part of the request.

## Commands

```bash
wallhaven search --q "+tokyo +night" --categories 110 --purity 100 --atleast 2560x1440 --ratios 16x9 --sorting favorites --page 1
wallhaven get https://whvn.cc/wq37kp
wallhaven download wq37kp --out ./artifacts
wallhaven settings
wallhaven collections
wallhaven collections --user <username>
wallhaven collections --user <username> --id <collection-id> --purity 100 --page 1
wallhaven tag <numeric-tag-id>
```

`settings` and listing one's own collections require a key; public collections can be listed with `--user`. Wallpaper page URLs and short links belong in `get`/`download`, not in `--q`.

## Browsing or backing up a collection

- With `--id`, username resolution is explicit `--user` → `WALLHAVEN_USERNAME` → Windows user registry fallback. Wallhaven does not supply the username from the API key. If unavailable, ask once and pass `--user` for this session; persistent configuration is optional (`setx WALLHAVEN_USERNAME <name>` on Windows, or a shell profile on macOS/Linux).
- Purity filters change both the item set and pagination. Keep the requested filter on every page. For an explicitly full collection backup, use `--purity 111` with a key; for SFW-only backup, keep `100`. Do not describe a filtered export as the whole collection.
- Follow successful responses through `meta.last_page`, deduplicate by wallpaper ID, and compare unique IDs with `meta.total` as a consistency check. Counts and page contents can drift while a collection changes; this is not a snapshot guarantee. If a page fails after retries, stop or record it for recovery and report the backup as incomplete.
- Local `wallhaven-<id>.*` filenames help identify prior downloads, but names alone do not prove integrity. Check sizes against item `file_size`, or let `download` check before skipping. Download missing items; report mismatched files and use `--force` only when replacement is authorized. Report unresolved downloads separately from enumeration results.

## Building a useful query

Wallhaven searches tags and metadata, not a natural-language visual description. Translate the request into a few searchable concepts, then inspect previews to judge composition and style.

| Intent | Query or filter |
|---|---|
| Tokyo at night | `--q "+tokyo +night"` |
| Exclude the people tag | `--q "-people"` (still inspect previews) |
| Anime category | `--categories 010` |
| PNG format | `--q "type:png"` |
| Related tags to a wallpaper | `--q "like:wq37kp"` |
| An uploader's images | `--q "@username"` |
| Exact numeric tag | `--q "id:123"` (cannot combine with other terms) |

- A bare tag term uses fuzzy matching; `+tag1 +tag2` requires both terms, while `-tag` excludes a term. Numeric `id:` is the exact-tag selector. Do not assume aliases or adding/removing `+` will always expand results. Use `get` on a promising image to learn its actual tag names; `tag` takes a numeric ID, not a name.
- Use a small initial query and adjust one filter at a time. Preserve the user's hard requirements; relax only optional constraints when results are empty. Do not enable NSFW just to get more results.
- `relevance` ranks query relevance, `favorites` sorts by favorite count, and `toplist` uses Wallhaven's ranking over `--top-range` (e.g. `1M`). These are discovery signals, not measures of the user's taste. `random` offers variety, not stable pagination. `like:<id>` uses shared tags, not visual similarity.
- `--colors` uses Wallhaven's fixed palette values, not arbitrary RGB shades; comma-separated values select alternatives. See the palette and search syntax in the [official API reference](https://wallhaven.cc/help/api).

## Reading and showing images

- `resolution` gives exact width and height; `ratio` is rounded (e.g. `1.78`). Use dimensions for precise screen-fit decisions. `--atleast` is a minimum size; `--resolutions` requests exact dimensions. Do not substitute one for the other without regard to intent.
- `file_size` is bytes; `file_type` is the MIME type. Compare the reported sizes rather than assuming PNG is always larger than JPEG. The CLI checks MIME type and byte count, not image decoding or a cryptographic checksum.
- Use `thumb` for previews and an available image viewer for visual inspection. `path` is the original URL; `download` saves it locally. Pass paths or URLs to image tools instead of dumping binary/base64 into chat. Do not claim to have visually inspected an image from tags alone.
