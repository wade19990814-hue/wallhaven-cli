# wallhaven-cli

[English](README.md) | 简体中文

`wallhaven-cli` 是一个零第三方依赖、JSON 优先的命令行客户端，用于通过 [Wallhaven API](https://wallhaven.cc/help/api) 搜索、查看和下载壁纸。

它首先是一个可独立运行的 CLI 工具；同时在 [`skills/wallhaven`](skills/wallhaven/) 目录下附带了一个可选的 Agent Skill 适配层，用于指导支持 Skill 的 AI Agent（如 Codex、Claude Code 等）安全、高效地调用已安装的命令。CLI 本身绝不依赖 Skill。

> 本项目为非官方客户端，与 Wallhaven 官方无隶属关系。

## 特性

- **六个命令**：`search`、`get`、`download`、`settings`、`collections` 和 `tag`。
- **面向 JSON**：业务子命令统一向 stdout 输出 JSON；退出码为 0 成功、2 参数错误、3 缺少凭据或鉴权失败、4 HTTP/响应/文件错误（包括未找到）、5 网络错误。
- **默认安全（SFW）**：默认 `--purity 100`；未配置 Key 时查询非 SFW 内容直接以退出码 3 明确拒绝，阻断官方 API 静默降级的歧义行为。
- **输入容错**：支持 6 位图片 ID、`wallhaven.cc/w/<id>` 网页链接与 `whvn.cc/<id>` 短链。
- **零依赖**：纯 Python 标准库实现（Python 3.9+），无任何第三方包依赖。
- **下载校验**：检查图片 MIME 类型和字节数，采用临时文件原子替换；仅在已有文件大小符合 API 元数据时跳过。
- **网络容错**：遇到 HTTP 429 或连接瞬断时自动退避重试。

## 安装 CLI

需要 Python 3.9 或更高版本。项目通过 GitHub 源码和构建产物分发，不再向 PyPI 发布新版本。

### 从源码安装

克隆本仓库，或[下载当前源码 ZIP](https://github.com/wade19990814-hue/wallhaven-cli/archive/refs/heads/main.zip) 并解压。在包含 `pyproject.toml` 的目录中打开终端：

```bash
git clone https://github.com/wade19990814-hue/wallhaven-cli.git
cd wallhaven-cli
python -m venv .venv
```

macOS/Linux 执行 `source .venv/bin/activate`，Windows PowerShell 执行 `.venv\Scripts\Activate.ps1` 激活虚拟环境，然后安装：

```bash
python -m pip install .
wallhaven --version
```

下载 ZIP 时无需执行 `git clone`，直接进入解压目录即可。开发时可在同一环境中改用 `python -m pip install -e .` 进行可编辑安装。CLI 没有运行时第三方依赖；pip 会安装从源码构建所需的构建工具。

### 从 GitHub 下载

当前 `main` 源码版本为 `0.2.1`。旧的 [v0.2.0 Release](https://github.com/wade19990814-hue/wallhaven-cli/releases/tag/v0.2.0) 没有附加 wheel 或可执行文件，也不满足随仓库提供的 Skill 所要求的 `>=0.2.1`。需要当前 CLI 和 Skill 时，请使用上面的当前源码安装方式。

[分发包工作流](https://github.com/wade19990814-hue/wallhaven-cli/actions/workflows/package.yml) 在 `main`、手动选择的 ref 或 Release 标签构建成功后生成名为 `distributions` 的 artifact，其中包含 wheel 和源码包。存在成功产物时，可下载并解压，再用 `python -m pip install --force-reinstall <下载的-wheel-文件路径.whl>` 安装 wheel，或解压源码包后按上面的源码步骤安装。请核对运行所用提交或标签，并通过 `wallhaven --version` 确认版本。下载 Actions artifact 需要登录 GitHub，且产物可能过期；仍可使用源码安装。工作流不会自动把文件附加到 Release，也不会发布到 PyPI。

## 快速上手

```bash
wallhaven search --q "+tokyo +night" --atleast 2560x1440 --ratios 16x9 --sorting favorites
wallhaven get https://whvn.cc/wq37kp
wallhaven download wq37kp --out ./artifacts
wallhaven settings
wallhaven collections
wallhaven tag 1
```

所有业务子命令均向 stdout 输出 JSON 格式，方便脚本管道解析与 Agent 理解。`--help` 与 `--version` 保持常规命令行纯文本输出。

| 命令 | 用途 |
|---|---|
| `wallhaven search` | 搜索壁纸并返回一页结果（每页最多 24 项）。 |
| `wallhaven get <id-or-url>` | 获取单张壁纸的元数据、标签列表与上传者。 |
| `wallhaven download <id-or-url> --out <目录>` | 保存原图；已有文件大小与 API 元数据一致才跳过，使用 `--force` 可重新下载并替换。 |
| `wallhaven settings` | 查看账号的搜索与过滤偏好设置（需 API Key）。 |
| `wallhaven collections` | 查看自己的收藏夹（需 Key）或通过 `--user <用户名>` 浏览用户的公开收藏夹。 |
| `wallhaven tag <id>` | 根据数字标签 ID 查询标签详情（名称、分类、纯度等）。 |

运行 `wallhaven search --help` 查看所有搜索过滤参数。

下载内容必须与 API 的 `file_size` 一致才会写入目标文件。已有文件大小不符时返回错误，未经 `--force` 不会覆盖；即使使用 `--force`，下载失败也会保留原文件。MIME 类型和字节数检查不能替代图片解码或校验和验证。

## API Key 与用户名配置

SFW 壁纸搜索无需配置 Key。`--purity` 默认值为 `100`（SFW）；使用任何非 SFW 纯度均需要设置 `WALLHAVEN_API_KEY`。

请在系统或进程环境变量中配置 Key，不要将其写入仓库代码、`.env` 文件或 Agent 提示词中：

```powershell
# Windows PowerShell（新打开的终端将继承该用户变量）
setx WALLHAVEN_API_KEY "你的-api-key"
```

```bash
# macOS / Linux
export WALLHAVEN_API_KEY='你的-api-key'
```

在 Windows 上，进程环境变量为空或不存在时，CLI 会回退读取注册表 `HKCU\Environment\WALLHAVEN_API_KEY`。Key 只通过 `X-API-Key` 请求头发送到 HTTPS Wallhaven API，不拼入 URL，也不发送到图片 CDN。带 Key 的请求若重定向到 API 范围之外会被拒绝，HTTPS 降级同样会被拒绝。

环境变量和用户注册表不是加密的密钥存储。如果不想让 Key 留在终端历史里，可通过系统的环境变量设置界面配置；不要把真实 Key 发到 Agent 对话中。

类似地，使用 `collections --id <id>` 浏览特定收藏夹内容时，API 路径需要提供你的 Wallhaven 用户名。你可以显式传入 `--user <用户名>`，也可以通过环境变量配置一次：

```powershell
setx WALLHAVEN_USERNAME "你的用户名"
```

用户名采用与 Key 相同的环境变量/Windows 注册表回退规则，显式 `--user` 优先。临时使用只需传入 `--user`，不必做持久配置。macOS/Linux 可使用 `export WALLHAVEN_USERNAME='你的用户名'`。

## 可选的 Agent Skill 适配层

[`skills/wallhaven`](skills/wallhaven/) 目录是一个独立的 Agent Skill。它仅包含工作流和平台知识，依赖系统 `PATH` 中版本满足 `>=0.2.1,<0.3.0` 的 `wallhaven` CLI。

**安装顺序**：

1. 先安装 CLI，确认 `wallhaven --version` 在 Agent 使用的环境中执行成功；若使用虚拟环境，请先激活它再启动 Agent，确保命令在其 `PATH` 中；
2. 从本仓库或对应版本的源码分发包中获取完整的 `skills/wallhaven/` 目录，复制到 Agent 所读取的 Skill 路径下；pip 安装 CLI wheel 不会自动安装 Skill；
3. 不要将 `src/` 拷贝进 Skill，也不要用裸 HTTP 请求替代 CLI 调用。

在 Codex 仓库级配置中，将整个目录放置于消费项目的 `.agents/skills/wallhaven/` 下即可被自动发现。

## 开发与验证

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
wallhaven --version
```

单元测试仅依赖标准库，隔离环境变量和注册表配置，并阻止未模拟的网络请求。执行实时冒烟测试可运行常规 SFW 查询：

```bash
wallhaven search --q "+tokyo +night" --ratios 16x9 --sorting favorites
```

GitHub Actions CI 流水线会在 Windows 和 Ubuntu（Python 3.9 与 3.13）环境下先安装包再执行完整测试与冒烟验证。

**分发前检查清单**：

1. 运行离线单测套件并在已安装环境中执行 SFW 实时搜索；
2. 在全新虚拟环境中安装包，验证 `wallhaven --version`、JSON 参数错误输出和单张图片下载；
3. 若 CLI 的命令行参数或 JSON 契约发生变动，同步更新 Skill 中的版本约束并重新运行验证；
4. 确认未暂存任何本地绝对路径、真实 API Key 或下载的壁纸文件。

### 打包（维护者）

在验证过的源码目录中执行：

```bash
python -m pip install --upgrade build twine
python -m build
python -m twine check --strict dist/*
```

源码包和 wheel 会生成在 `dist/` 下。源码包包含中英文 README 和可选 Skill；wheel 只安装 CLI。分发前请在全新虚拟环境中验证安装结果。

`package.yml` 工作流会在 `main` 的源码或打包配置变更时自动运行，也可从 Actions 页面手动运行；仅文档变更不会触发。工作流先运行现有 Windows/Linux 测试矩阵，再构建源码包和 wheel，并检查包内容及安装结果。分支构建无需创建 Release 或版本标签。最终只上传 `distributions` Actions artifact。工作流仅使用仓库只读权限，无需发布凭据，也没有 PyPI 发布任务。

从成功的 **Build distribution artifacts** 运行中下载 `distributions` artifact，分享开发构建时保留对应提交信息。以后若需要标签构建，标签必须与包版本一致（`v<版本号>`）；发布 GitHub Release 也会触发该校验。仅有 Release 不代表提供了 wheel，此工作流不会上传 Release 附件。不要移动已发布的版本标签，也不要让同一已发布版本号对应不同的包内容。

## 架构与设计原则

CLI 负责 API 通信、参数校验、JSON 输出、Key 解析、重试与下载。Skill 提供平台知识，让 Agent 能按用户的需求组合这些能力，完成壁纸选择、桌面美化、收藏夹备份或视觉参考收集等任务。

```text
Agent skill   ──依赖──>  wallhaven CLI
wallhaven CLI ──不依赖──> Agent skill
```

### 设计边界：提供原语，而非复合工作流

CLI 提供可组合的基础操作。组合已有操作就能实现的功能（如批量下载、收藏夹导出、桌面壁纸设置）交给调用方或 Agent：

- **批量下载**：通过 Shell 或 PowerShell 管道连接 `search` 与 `download`。

  ```powershell
  $r = wallhaven search --q "+tokyo +night" --sorting favorites | ConvertFrom-Json
  if ($LASTEXITCODE -ne 0 -or -not $r.ok) { throw "Search failed" }
  $r.items | Select-Object -First 5 -ExpandProperty id | ForEach-Object {
    Start-Sleep -Seconds 3
    wallhaven download $_ -o ./artifacts
    if ($LASTEXITCODE -ne 0) { throw "Download failed: $_" }
  }
  ```

- **设为桌面壁纸**：Agent 可直接调用操作系统原生接口（如 Windows 的 `SystemParametersInfo`），无需让 API 客户端强耦合桌面环境。
- **收藏夹导出**：循环请求 `collections --user X --id Y --page N`，每页保持相同的内容范围（明确备份整个收藏夹时使用 `111`，需 Key）。按 ID 去重并核对数量，报告失败页和下载失败项，不把未完成的导出报成成功。

保持命令接口简洁，让脚本和 Agent 按需组合即可。

## 合规与免责

请遵守 Wallhaven 的 API 规则、速率限制与壁纸原作者的版权权益，不要将搜索结果用作训练语料或批量商业素材库。CLI 遇到 HTTP 429 或瞬时连接/读取错误时，最多重试 2 次，每次间隔 2 秒；证书验证错误不重试。重试耗尽仍会返回错误。

限速器只在单个进程内有效，多次启动 CLI 不共享计数。调用方需要把所有调用及重试合并考虑，控制在 Wallhaven 约每分钟 45 次 API 请求的限制内；每次下载也会请求一次 API 元数据。避免并发突发请求和大范围翻页抓取。

## 开源协议

[MIT](LICENSE)。
