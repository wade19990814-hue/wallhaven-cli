# wallhaven-cli

English | [简体中文](README_zh.md)

`wallhaven-cli` is a dependency-free, JSON-first command-line client for searching, inspecting, and downloading wallpapers through the [Wallhaven API](https://wallhaven.cc/help/api).

It is a standalone CLI first. The repository also ships an optional agent skill under [`skills/wallhaven`](skills/wallhaven/) that teaches skill-aware agents how to call the installed command safely; the CLI never depends on that skill.

> This is an unofficial client and is not affiliated with Wallhaven.

## Features

- Six commands: `search`, `get`, `download`, `settings`, `collections`, and `tag`.
- Stable JSON result and structured error output for every command.
- SFW by default; non-SFW purity values require an API key rather than silently falling back to SFW-only results.
- Accepts wallpaper IDs, `wallhaven.cc/w/<id>` pages, and `whvn.cc/<id>` short links.
- Uses only the Python standard library at runtime.
- Checks download MIME type and byte count before writing image files atomically.
- Installs a normal `wallhaven` command on Windows, macOS, and Linux.

## Install the CLI

Python 3.9 or newer is required. This project is distributed through GitHub source and build artifacts; new versions are not published to PyPI.

### Install from source

Clone this repository, or [download the current source ZIP](https://github.com/wade19990814-hue/wallhaven-cli/archive/refs/heads/main.zip) and extract it. Open a terminal in the directory containing `pyproject.toml`:

```bash
git clone https://github.com/wade19990814-hue/wallhaven-cli.git
cd wallhaven-cli
python -m venv .venv
```

Activate the environment with `source .venv/bin/activate` on macOS/Linux or `.venv\Scripts\Activate.ps1` in Windows PowerShell, then install:

```bash
python -m pip install .
wallhaven --version
```

The ZIP download replaces the `git clone` step; enter the extracted directory instead. For an editable development install, use `python -m pip install -e .` in the same environment. The CLI has no runtime dependencies; pip installs the build tools needed to build it from source.

### GitHub downloads

The current `main` source is version `0.2.1`. The older [v0.2.0 Release](https://github.com/wade19990814-hue/wallhaven-cli/releases/tag/v0.2.0) has no attached wheel or executable and does not satisfy the bundled Skill's `>=0.2.1` requirement. Use the current source above for the current CLI and Skill.

The [distribution workflow](https://github.com/wade19990814-hue/wallhaven-cli/actions/workflows/package.yml) produces a `distributions` artifact containing a wheel and source archive after a successful build from `main`, a manually selected ref, or a Release tag. Download and extract that artifact when available, then install the wheel with `python -m pip install --force-reinstall <path-to-downloaded-wheel.whl>` or extract the source archive and follow the source-install steps above. Check the run's commit or tag and `wallhaven --version` against the version you need. Actions artifacts require a GitHub sign-in and may expire; the source-install route remains available. The workflow does not attach files to Releases or publish to PyPI.

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
| `wallhaven download <id-or-url> --out <directory>` | Save the original image; skips an existing file only if its size matches API metadata. Use `--force` to replace it. |
| `wallhaven settings` | Return account search and filter preferences (requires API key). |
| `wallhaven collections` | List own collections (requires key) or view a user's collections with `--user <username>`. |
| `wallhaven tag <id>` | Return tag details (name, category, purity) by numeric tag id. |

Run `wallhaven search --help` for all search flags.

Exit codes: `0` success, `2` invalid arguments, `3` missing or rejected credentials, `4` HTTP/response/file errors (including not found), `5` network errors.

Downloads must match the API's `file_size` before replacing the destination. A mismatched existing file returns an error and is left untouched unless `--force` is used. Even with `--force`, a failed download leaves the original file intact. MIME and size checks do not replace image decoding or checksum verification.

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

On Windows, the CLI falls back to the user environment entry at `HKCU\Environment\WALLHAVEN_API_KEY` when the process variable is empty or absent. The key is sent only in the `X-API-Key` header to the HTTPS Wallhaven API, never in an API URL or an image CDN request. Authenticated redirects outside the API are rejected, as are HTTPS downgrades.

Environment variables and the user registry are not encrypted secret storage. Prefer your operating system's environment settings UI if you want to keep the key out of shell history; never paste it into an agent conversation.

Similarly, `collections --id <id>` (browsing items of a specific collection) needs your Wallhaven username in the API path. Pass `--user <name>`, or set `WALLHAVEN_USERNAME` once and the CLI resolves it automatically:

```powershell
setx WALLHAVEN_USERNAME "your-wallhaven-username"
```

Username lookup follows the same environment/Windows-registry fallback as the key, with `--user` taking precedence. For a one-off session, just pass `--user`; no persistent configuration is needed. On macOS/Linux, use `export WALLHAVEN_USERNAME='your-wallhaven-username'`.

## Optional agent skill

The [`skills/wallhaven`](skills/wallhaven/) directory is a separate Agent Skill artifact. It contains workflow and platform guidance only; it requires `wallhaven` CLI version `>=0.2.1,<0.3.0` on `PATH`.

Install in this order:

1. Install the CLI and verify `wallhaven --version` succeeds in the environment used by your agent. If you used a virtual environment, activate it before launching the agent so the command is on its `PATH`.
2. Get the complete `skills/wallhaven/` directory from this repository or the matching source distribution, then copy it into the skill location used by your agent host. Installing the CLI wheel with pip does not install the skill.
3. Do not copy `src/` into the skill or replace the command with raw HTTP requests.

For a Codex repository-scoped setup, place the complete skill directory at `.agents/skills/wallhaven/` in the consuming repository; see the [official skills documentation](https://learn.chatgpt.com/docs/build-skills).

## Development and verification

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
wallhaven --version
```

The tests use only the standard library, isolate environment and registry settings, and reject unexpected network requests. A live smoke test uses a normal SFW query:

```bash
wallhaven search --q "+tokyo +night" --ratios 16x9 --sorting favorites
```

The GitHub Actions workflow installs the package before running the unit suite and command smoke test on Windows and Ubuntu with Python 3.9 and 3.13.

Before distributing a build:

1. Run the unit suite and a live SFW smoke search through the installed command.
2. Install the package into a clean environment and verify `wallhaven --version`, JSON error output, and one download.
3. Update the skill's CLI version range if the command-line or JSON contract changed, and re-validate the skill.
4. Confirm no local paths, API keys, or downloaded images are staged.

### Packaging (maintainers)

Build locally from a verified checkout:

```bash
python -m pip install --upgrade build twine
python -m build
python -m twine check --strict dist/*
```

The source archive and wheel are written to `dist/`. The source archive includes both READMEs and the optional Skill; the wheel installs only the CLI. Test an install in a fresh virtual environment before sharing either file.

The `package.yml` workflow runs automatically for source or packaging configuration changes on `main`, and can also be run manually from the Actions page. Documentation-only changes do not trigger it. It runs the existing Windows/Linux test matrix, builds the source archive and wheel, and checks their contents and installation. No release or version tag is needed for branch builds. It uploads only the `distributions` Actions artifact. It has read-only repository permissions, needs no publishing credentials, and has no PyPI publishing job.

Download the `distributions` artifact from a successful **Build distribution artifacts** run and keep its commit reference when sharing a development build. If a tagged build is desired later, its tag must match the package version (`v<version>`); publishing a GitHub Release also triggers that validation. A Release by itself does not provide a wheel, and this workflow does not upload Release assets. Do not move published version tags or reuse a released version for different package contents.

## Architecture

The CLI owns API access, validation, JSON contracts, key handling, and downloads. The Skill supplies platform knowledge so an agent can use these capabilities for the user's wallpaper, desktop, collection, or visual-reference tasks.

```text
Agent skill  ──depends on──>  wallhaven CLI
wallhaven CLI ──does not depend on──> Agent skill
```

### Design boundary: primitives, not workflows

The CLI exposes small, composable operations. Features that combine these operations belong to the caller, not the CLI:

- **Batch download**: pipe `search` output through your shell.

  ```powershell
  $r = wallhaven search --q "+tokyo +night" --sorting favorites | ConvertFrom-Json
  if ($LASTEXITCODE -ne 0 -or -not $r.ok) { throw "Search failed" }
  $r.items | Select-Object -First 5 -ExpandProperty id | ForEach-Object {
    Start-Sleep -Seconds 3
    wallhaven download $_ -o ./artifacts
    if ($LASTEXITCODE -ne 0) { throw "Download failed: $_" }
  }
  ```

- **Set as desktop wallpaper**: any agent can call the OS API directly (e.g. `SystemParametersInfo` on Windows); adding it here would couple an API client to desktop environments for no benefit.
- **Collection export**: loop `collections --user X --id Y --page N` in a script, keeping the requested purity filter on every page (`111` with a key for an explicitly full collection backup). Deduplicate IDs, check counts, and report failed pages or downloads instead of claiming an incomplete export is complete.

This keeps the public surface small while letting agents and scripts compose freely.

## Responsible use

Respect Wallhaven's API rules, rate limits, copyright, and the rights of each wallpaper's creator. Do not use search results as a training corpus or a bulk commercial asset library. The CLI retries HTTP 429 and transient connection/read failures up to twice, waiting two seconds between attempts. Certificate-verification errors are not retried. Exhausted retries remain errors.

Rate limiting is per process; separate CLI invocations do not share a counter. Callers must pace the combined workload against Wallhaven's limit of roughly 45 API requests per minute, including retries. Each download also fetches API metadata. Avoid concurrent bursts and large search-page sweeps.

## License

[MIT](LICENSE).
