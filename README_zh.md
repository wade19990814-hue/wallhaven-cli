# wallhaven-cli

[English](README.md) | 简体中文

`wallhaven-cli` 是一个零第三方依赖、JSON 优先的命令行客户端，用于通过 [Wallhaven API](https://wallhaven.cc/help/api) 搜索、查看和下载高质量壁纸。

它首先是一个可独立运行的 CLI 工具；同时在 [`skills/wallhaven`](skills/wallhaven/) 目录下附带了一个可选的 Agent Skill 适配层，用于指导支持 Skill 的 AI Agent（如 Codex、Claude Code 等）安全、高效地调用已安装的命令。CLI 本身绝不依赖 Skill。

> 本项目为非官方客户端，与 Wallhaven 官方无隶属关系。

## 特性

- **完整 API 覆盖**：支持 `search`、`get`、`download`、`settings`、`collections` 和 `tag` 全部 6 个官方端点。
- **面向 JSON**：所有业务子命令统一向 stdout 输出结构化 JSON，退出码明确（0 成功、2 参数错误、3 鉴权失败、4 未找到、5 网络错误）。
- **默认安全（SFW）**：默认 `--purity 100`；未配置 Key 时查询非 SFW 内容直接以退出码 3 明确拒绝，阻断官方 API 静默降级的歧义行为。
- **输入容错**：支持 6 位图片 ID、`wallhaven.cc/w/<id>` 网页链接与 `whvn.cc/<id>` 短链。
- **零依赖**：纯 Python 标准库实现（Python 3.9+），无任何第三方包依赖。
- **安全落盘**：严格校验图片 Content-Type，采用 `.part` 临时文件原子替换，默认跳过已存在文件。
- **网络容错**：遇到 HTTP 429 或连接瞬断时自动退避重试。

## 安装 CLI

需要 Python 3.9 或更高版本。克隆本仓库并在仓库根目录下执行安装：

```bash
python -m pip install .
wallhaven --version
```

开发调试时推荐使用可编辑安装（Editable install）：

```bash
python -m pip install -e .
```

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
| `wallhaven get <id-or-url>` | 获取单张壁纸的完整元数据、标签列表与上传者。 |
| `wallhaven download <id-or-url> --out <目录>` | 下载并保存原图；若目标文件已存在则默认跳过（除非传入 `--force`）。 |
| `wallhaven settings` | 查看账号的搜索与过滤偏好设置（需 API Key）。 |
| `wallhaven collections` | 查看自己的收藏夹（需 Key）或通过 `--user <用户名>` 浏览用户的公开收藏夹。 |
| `wallhaven tag <id>` | 根据数字标签 ID 查询标签详情（名称、分类、纯度等）。 |

运行 `wallhaven search --help` 查看所有搜索过滤参数。

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

在 Windows 上，当非登录 shell 未能继承环境变量时，CLI 会自动回退读取注册表 `HKCU\Environment\WALLHAVEN_API_KEY`。Key 仅在 HTTP 请求头 `X-API-Key` 中传输，绝不拼入 URL。

类似地，使用 `collections --id <id>` 浏览特定收藏夹内容时，API 路径需要提供你的 Wallhaven 用户名。你可以显式传入 `--user <用户名>`，也可以通过环境变量配置一次：

```powershell
setx WALLHAVEN_USERNAME "你的用户名"
```

## 可选的 Agent Skill 适配层

[`skills/wallhaven`](skills/wallhaven/) 目录是一个独立的 Agent Skill。它仅包含工作流规范与安全指引，依赖系统 `PATH` 中版本满足 `>=0.2.0,<0.3.0` 的 `wallhaven` CLI。

**安装顺序**：

1. 先安装 CLI，确认 `wallhaven --version` 在终端中执行成功；
2. 将完整的 `skills/wallhaven/` 目录复制或链接到 Agent 主机所读取的 Skill 路径下；
3. 不要将 `src/` 拷贝进 Skill，也不要用裸 HTTP 请求替代 CLI 调用。

在 Codex 仓库级配置中，将整个目录放置于消费项目的 `.agents/skills/wallhaven/` 下即可被自动发现。

## 开发与验证

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
wallhaven --version
```

单元测试仅依赖标准库，对 HTTP 网络请求进行了完整模拟。执行实时冒烟测试可运行常规 SFW 查询：

```bash
wallhaven search --q "+tokyo +night" --ratios 16x9 --sorting favorites
```

GitHub Actions CI 流水线会在 Windows 和 Ubuntu（Python 3.9 与 3.13）环境下先安装包再执行完整测试与冒烟验证。

**发布前检查清单**：

1. 运行离线单测套件并在已安装环境中执行 SFW 实时搜索；
2. 在全新虚拟环境中安装包，验证 `wallhaven --version`、JSON 参数错误输出和单张图片下载；
3. 若 CLI 的命令行参数或 JSON 契约发生变动，同步更新 Skill 中的版本约束并重新运行验证；
4. 确认未暂存任何本地绝对路径、真实 API Key 或下载的壁纸文件。

## 架构与设计原则

CLI 负责处理 API 通信、参数校验、JSON 输出契约、Key 解析、重试退避与文件下载；Skill 仅负责将用户的自然语言意图转换为安全的 CLI 调用。

```text
Agent skill   ──依赖──>  wallhaven CLI
wallhaven CLI ──不依赖──> Agent skill
```

### 设计边界：提供原语，而非复合工作流

CLI 为每个 Wallhaven API 端点提供且仅提供一个原语命令。由基础原语组合即可实现的功能（如批量下载、收藏夹导出、桌面壁纸设置）属于调用方/Agent 的职责，不内置进 CLI：

- **批量下载**：通过 Shell 或 PowerShell 管道连接 `search` 与 `download`。
  ```powershell
  $r = wallhaven search --q "+tokyo +night" --sorting favorites | ConvertFrom-Json
  $r.items | Select-Object -First 5 -ExpandProperty id | ForEach-Object { wallhaven download $_ -o ./artifacts }
  ```
- **设为桌面壁纸**：Agent 可直接调用操作系统原生接口（如 Windows 的 `SystemParametersInfo`），无需让 API 客户端强耦合桌面环境。
- **全量收藏夹导出**：通过脚本循环请求 `collections --user X --id Y --page N`；CLI 内部每进程自带限速器，确保调用安全。

这使得公共命令面始终保持 6 个核心命令，代码精简，并赋予调用方与 Agent 自由编排的能力。

## 合规与免责

请遵守 Wallhaven 的 API 规则、速率限制与壁纸原作者的版权权益。请勿将搜索结果用于大规模商业训练集抓取。CLI 在遭遇 HTTP 429 或瞬时网络连接错误时会自动等待 2 秒并最多重试 2 次；调用方仍应避免高并发突发请求。

## 开源协议

[MIT](LICENSE)。

