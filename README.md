# wallhaven-cli

`wallhaven-cli` is a dependency-free, JSON-first command-line client for searching, inspecting, and downloading wallpapers through the [Wallhaven API](https://wallhaven.cc/help/api).

It is a standalone CLI first. The repository also ships an optional agent skill under [`skills/wallhaven`](skills/wallhaven/) that teaches skill-aware agents how to call the installed command safely; the CLI never depends on that skill.

> This is an unofficial client and is not affiliated with Wallhaven.

## Features

- Full Wallhaven API v1 coverage: `search`, `get`, `download`, `settings`, `collections`, and `tag`.
- Stable JSON result and structured error output for every command.
- SFW by default; non-SFW purity values require an API key rather than silently falling back to SFW-only results.
- Accepts wallpaper IDs, `wallhaven.cc/w/<id>` pages, and `whvn.cc/<id>` short links.
- Uses only the Python standard library at runtime.
- Rejects non-image download responses and writes image files atomically.
- Installs a normal `wallhaven` command on Windows, macOS, and Linux.

## Install the CLI

Python 3.9 or newer is required. Clone or download this repository, then install the CLI from the repository root:

```bash
python -m pip install .
wallhaven --version
```

For development, use an editable install instead:

```bash
python -m pip install -e .
```

The project has no runtime dependencies. It is not published to a package index yet, so installation currently starts from a clone or source archive.

## Quick start

```bash
wallhaven search --q "+tokyo +night" --atleast 2560x1440 --ratios 16x9 --sorting favorites
wallhaven get https://whvn.cc/wq37kp
wallhaven download wq37kp --out ./artifacts
wallhaven settings
wallhaven collections
wallhaven tag 1
```

Subcommands write JSON to stdout for both success and operational errors. `--help` and `--version` intentionally use normal human-readable command-line output.

| Command | Purpose |
|---|---|
| `wallhaven search` | Return one page of matching wallpapers (up to 24 items). |
| `wallhaven get <id-or-url>` | Return one wallpaper's metadata, tags, and uploader. |
| `wallhaven download <id-or-url> --out <directory>` | Save the original image; skips an existing filename unless `--force` is supplied. |
| `wallhaven settings` | Return account search and filter preferences (requires API key). |
| `wallhaven collections` | List own collections (requires key) or view a user's collections with `--user <username>`. |
| `wallhaven tag <id>` | Return tag details (name, category, purity) by numeric tag id. |

Run `wallhaven search --help` for all search flags.

## API key and content safety

SFW search works without a key. `--purity` defaults to `100` (SFW); every other purity value requires `WALLHAVEN_API_KEY`, because Wallhaven can otherwise return HTTP 200 while silently limiting results to SFW.

Set the key in the process environment, not in this repository, an `.env` file, or an agent prompt:

```powershell
# Windows PowerShell: new shells inherit this user environment variable.
setx WALLHAVEN_API_KEY "your-key"
```

```bash
# macOS / Linux
export WALLHAVEN_API_KEY='your-key'
```

On Windows, the CLI falls back to the user environment entry at `HKCU\Environment\WALLHAVEN_API_KEY` when a non-login shell did not inherit it. The key is sent only in the `X-API-Key` header, never in an API URL.

Similarly, `collections --id <id>` (browsing items of a specific collection) needs your Wallhaven username in the API path. Pass `--user <name>`, or set `WALLHAVEN_USERNAME` once and the CLI resolves it automatically:

```powershell
setx WALLHAVEN_USERNAME "your-wallhaven-username"
```

## Optional agent skill

The [`skills/wallhaven`](skills/wallhaven/) directory is a separate Agent Skill artifact. It contains workflow and safety guidance only; it requires `wallhaven` CLI version `>=0.2.0,<0.3.0` on `PATH`.

Install in this order:

1. Install the CLI and verify `wallhaven --version` succeeds.
2. Install or copy the complete `skills/wallhaven/` directory into the skill location used by your agent host.
3. Do not copy `src/` into the skill or replace the command with raw HTTP requests.

For a Codex repository-scoped setup, place the complete skill directory at `.agents/skills/wallhaven/` in the consuming repository. Codex scans that location for repo skills; see the [official skills documentation](https://learn.chatgpt.com/docs/build-skills). For broad end-user distribution, a plugin is the appropriate later packaging step.

## Development and verification

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
wallhaven --version
```

The tests use only the standard library and mock HTTP requests. A live smoke test uses a normal SFW query:

```bash
wallhaven search --q "+tokyo +night" --ratios 16x9 --sorting favorites
```

The GitHub Actions workflow installs the package before running the unit suite and command smoke test on Windows and Ubuntu with Python 3.9 and 3.13.

Before publishing a release:

1. Run the unit suite and a live SFW smoke search through the installed command.
2. Install the package into a clean environment and verify `wallhaven --version`, JSON error output, and one download.
3. Update the skill's CLI version range if the command-line or JSON contract changed, and re-validate the skill.
4. Confirm no local paths, API keys, or downloaded images are staged.

## Architecture

The CLI owns API access, validation, JSON contracts, key handling, and downloads. The Skill only turns user requests into safe CLI calls.

```text
Agent skill  ──depends on──>  wallhaven CLI
wallhaven CLI ──does not depend on──> Agent skill
```

### Design boundary: primitives, not workflows

The CLI exposes one verb per API endpoint and nothing more. Features that are mere combinations of primitives belong to the caller, not the CLI:

- **Batch download**: pipe `search` output through your shell.

  ```powershell
  $r = wallhaven search --q "+tokyo +night" --sorting favorites | ConvertFrom-Json
  $r.items | Select-Object -First 5 -ExpandProperty id | ForEach-Object { wallhaven download $_ -o ./artifacts }
  ```

- **Set as desktop wallpaper**: any agent can call the OS API directly (e.g. `SystemParametersInfo` on Windows); adding it here would couple an API client to desktop environments for no benefit.
- **Full collection export**: loop `collections --user X --id Y --page N` in a script; per-process rate limiting already keeps each request safe.

This keeps the public surface at 6 commands, the test suite small, and lets agents and scripts compose freely.

## Responsible use

Respect Wallhaven's API rules, rate limits, copyright, and the rights of each wallpaper's creator. Do not use search results as a training corpus or a bulk commercial asset library. The CLI retries HTTP 429 twice after a two-second wait; callers must still avoid concurrent calls and large page sweeps.

## License

[MIT](LICENSE).
