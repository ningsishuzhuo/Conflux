# Conflux

[![Tests](https://github.com/ningsishuzhuo/Conflux/actions/workflows/test.yml/badge.svg)](https://github.com/ningsishuzhuo/Conflux/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**状态：Alpha，当前版本 v0.3.1，接口可能调整。**

Conflux 是一个采用 MIT 许可的开源协作工具，由仅依赖 Python 标准库的轻量命令行工具（CLI）、共用协作规则和按需加载的技能组成。协调者可以用它控制 Antigravity（AGY）在五小时滚动窗口内的派单量，防止误用付费模型，并把已验收的任务交给新会话继续推进。Conflux 检查派单、记录成功回执和核验交接文件，任务执行与会话生命周期由 [Orca](https://github.com/stablyai/orca) 负责。

## 核心能力与适用场景

如果你已经在 Orca 中用多个客户端协作，需要让协调会话把工作交给合适的执行者，又希望每次派单和交接都有据可查，可以从 Conflux 的三项能力入手。

- **控制订阅消耗与付费准入**。为可用代理配置路由，限制 AGY 派单占比，并要求付费路由携带明确的本次授权。
- **按阶段分工**。协调者先和用户对齐方案，再把调研、实施和验收分给不同角色。所有执行者直接向协调者回报，避免多层派单。
- **跨会话续跑**。用统一格式记录 Orca 标识和下一步。接手会话读回交接单，核对 Orca 状态后继续。

## 安装与配置

macOS、Linux 和 Windows Subsystem for Linux（WSL）需要 Python 3.10 或更新版本，以及已加入 `PATH` 的 Orca CLI。

```sh
git clone https://github.com/ningsishuzhuo/Conflux.git
cd Conflux
./install.sh --dry-run
./install.sh
```

`--dry-run` 只检查依赖和软链冲突，不写文件。临时测试时可用 `--skip-orca-check` 跳过安装阶段的 Orca 检查，实际派单仍需要 Orca。

安装脚本创建账本目录 `~/.local/state/conflux/`，并建立三个软链。软链直接指向克隆目录，请保留克隆目录及其位置。

| 软链 | 仓库内目标 |
| --- | --- |
| `~/.local/bin/conflux` | `bin/conflux` |
| `~/.agents/skills/conflux-dispatch` | `.agents/skills/dispatch/` |
| `~/.agents/skills/conflux-autonomy` | `.agents/skills/autonomy/` |

如果终端找不到 `conflux`，把下面的 `export` 行加入 `~/.zshrc` 或 `~/.bashrc`，重开终端后运行 `conflux usage` 验证。

```sh
export PATH="$HOME/.local/bin:$PATH"
conflux usage
```

首次安装时，脚本把仓库 [示例策略](policy.json) 中的 `"example"` 替换为 `"default"`，写入 `~/.config/conflux/policy.json`。已有策略会保留。顶层 `routes` 是路由数组，每条路由包含以下字段。

| 字段 | 含义 |
| --- | --- |
| `agent`、`profile`、`model` | 共同构成精确匹配的三元组。当前的 `profile` 是本地策略标签。 |
| `billing` | `subscription`、`low_cost` 或 `paid`。 |
| `keep_open_default` | 布尔值。为真时默认传入 Orca 的 `--keep-open`。 |

重复三元组、重复键或不符合结构的字段会使整个策略加载失败。安装入口支持以下环境变量，显式命令参数优先。

- `CONFLUX_POLICY` 指定策略文件，默认 `~/.config/conflux/policy.json`。
- `CONFLUX_LEDGER` 指定账本文件，默认 `~/.local/state/conflux/ledger.jsonl`。
- `CONFLUX_AGY_BRAIN_DIR` 指定 AGY 会话日志根目录。未设置或为空时入口尝试 `~/.gemini/antigravity-cli/brain`，目录存在时才自动启用。

<details>
<summary>原生 Windows</summary>

在仓库根目录打开 PowerShell，使用已安装的 Python。下面的 `PATH` 设置只对当前会话生效。原生 Windows 已通过持续集成（CI）测试，真实 Orca 会话仍待实测。

```powershell
New-Item -ItemType Directory -Force "$HOME/.config/conflux", "$HOME/.local/state/conflux" | Out-Null
$policy = "$HOME/.config/conflux/policy.json"
if (!(Test-Path $policy)) { [IO.File]::WriteAllText($policy, (Get-Content -Raw policy.json).Replace('"example"', '"default"'), [Text.UTF8Encoding]::new($false)) }
$env:PATH = "$(Join-Path (Get-Location) 'bin');$env:PATH"
conflux usage
```

</details>

## 日常怎么用

### 两个按需技能

技能为协调者 AI 提供工作流程和命令规范。CLI 执行准入硬校验、成功回执记账和交接核验，日常由 AI 自动调用。

- [`conflux-autonomy`](.agents/skills/autonomy/SKILL.md) 是日常主入口。在对话中触发 `/conflux-autonomy`，或直接用自然语言提出代码、文案、演示文稿或科研需求。协调者 AI 依次推进预检、打磨、冻结、实施与审写分离验收，最后办理交接。
- [`conflux-dispatch`](.agents/skills/dispatch/SKILL.md) 用于单次派单、查用量和交接。例如，把一项已冻结的测试任务派给 Codex，再核对 Orca 回执。

技能入口位于 `.agents/skills/`，只在相应任务触发时加载。协调者按当前动作加载自主推进技能同级 `references/` 冷层中的场景化验收与异常处理说明。实施或验收派单前读 [审查清单](.agents/skills/autonomy/references/review-checklists.md)，涉及授权门、已覆盖的重试或交接异常时读 [边界情况](.agents/skills/autonomy/references/edge-cases.md)。所需段落无法读取时，停在相关动作并报告。

### 端到端工作流

1. **在对话中提需求**。触发 `/conflux-autonomy`，由协调者检查本机路由、依赖和工作区。
2. **在打磨期对齐方案**。和协调者明确目标、任务依赖、工作区和验收方式。需要查证时，由协调者派只读调研，再结合证据形成草案。
3. **确认完整契约后执行**。你明确拍板后，协调者安排执行者，按契约指定的审查安排及实测证据验收。
4. **随时查看用量**。手动运行 `conflux usage`，查看最近五小时的派单量、下一次 AGY 派单是否允许，以及可用的会话用量数据。
5. **在新会话续跑**。里程碑验收后，协调者发布并读回交接单。新会话核对 Orca 中的 Run、Task 和 Dispatch，再按 `Next` 继续。

### 协作模型

| 角色 | 职责与约束 |
| --- | --- |
| AGY（Antigravity） | 负责定契约、做决策和验收。联网检索、扫仓、读至少两个业务文件或运行业务命令时，首步交给 DeepSeek Harness（DSH）。拟派 AGY 前，当前窗口的计数须满足 `2 × (AGY + 1) < Codex`。 |
| DSH（DeepSeek Harness） | 做只读调研和客观验收。冻结后也可在干净工作区做小范围机械改动，并附 `git status`。只给一次机会，证据不足或失败即转 Codex。 |
| Codex | 承担主要实施，包括语义设计、多文件改造、文案、演示文稿和科研。 |
| Claude | 用于定点审查或重大裁决，默认拒绝。本轮明确点名 Claude、Claude Code 或 cc 且意图清晰时免二次确认，仍通过 `--authorize-paid` 记账。协调者主动提议或意图模糊时走 Orca 确认门。 |

#### 打磨与冻结

打磨期先出草案，协调者保持零状态改动，包括禁止改文件和执行 `git fetch`、`git pull`、`git switch`。用户明确拍板前，只派 DSH 做只读调研，或由用户点名做只读评审。触发自主推进技能或说「按你的下一步来做」仍属于打磨期。

冻结需要四项齐备：含依赖关系和工作区的任务图、由协调者持有的验收标准、执行安全红线、按共用规则执行的 Claude 点名授权策略。契约还须明确是否安排独立语义审查，安排时写明审查人，省略时记录原因。

草案应为 `git push`、拉取请求（PR）、Issue（包括 `Refs` 和 `Closes`）及发版等外部写操作写明唯一默认值和执行者。所有未决项须在冻结前拍板，外部写默认值须经明确确认。已冻结的默认值仅在参数或目标变化时重批。冻结后，执行者按授权范围交付，协调者依据约定证据验收。派单采用单层结构，执行者禁止继续派生执行者。

#### 写保护与客户端入口

| 档位 | 做法 |
| --- | --- |
| 硬隔离 | Codex 协调端用 `-s read-only -a never`，也可用只读工作区或只读挂载。执行者使用独立可写工作区。 |
| 辅助检测 | Gemini CLI 保留 Orca hook，追加 `BeforeTool` 写工具拦截。间接写入依靠工作区权限兜底。 |
| 软约束 | Antigravity、SSH 和 WSL 协调端遵守会话规则，能隔离时优先用硬隔离。 |

Codex 使用共用规则并从 `.agents/skills/` 发现技能。Claude Code 和 Gemini CLI 分别通过各自的入口文件引用共用规则，再按路径读取技能。Antigravity 由派单显式提供规则或技能路径。入口参见 [AGENTS.md](AGENTS.md)、[CLAUDE.md](CLAUDE.md)、[GEMINI.md](GEMINI.md)。

## CLI 命令参考

日常派单与交接主要由 AI 自动调用 CLI。你可以随时运行 `conflux usage`，通常只在排查报错、验证策略或手工补做交接时查阅本节。

### `conflux dispatch` · 检查并派单

使用安装生成的默认策略，在 Orca 聊天会话中可派 Codex 到当前工作区运行测试。

```sh
conflux dispatch --agent codex --profile default --model default --cwd . -- \
  --spec "运行单测并报告结果" --worktree current --environment local --json
```

- `--model` 必填，和 `--agent`、`--profile` 一起精确匹配策略。匹配到 `model: default` 时，Conflux 省略传给 Orca 的 `--model`，由客户端选用默认模型。
- 付费路由须传 `--authorize-paid <reason>`，理由不能为空白。AGY 派单还要求账本并接受配比检查。
- `--cwd` 必须是已有目录，它设定 Orca 子进程的工作目录。工作区由 `--worktree` 等 Orca 参数指定。分隔符 `--` 后禁止出现 `--agent`、`--model`、`--profile`、`--cwd`，包括等号写法。准入检查不通过时返回退出码 2，不调用 Orca。
- 从 Orca 终端派单且 `$ORCA_SESSION` 非空时，在分隔符之后加上 `--from "$ORCA_SESSION"`。聊天会话省略该参数。
- 启用账本时用 `--json` 取得回执。仅当 Orca 退出码为 0 且回执包含有效 `dispatchId` 时才记账，同一个 ID 在全账本只记一次。

### `conflux usage` · 查看窗口内用量

```sh
conflux usage
```

命令只读输出 JSON。窗口以协调世界时（UTC）计算，取 `now − 5h < ts ≤ now` 的记录，按 `dispatchId` 去重，重复时取窗口内最后一条。

| 输出 | 如何解读 |
| --- | --- |
| `window_hours`、`metric_kind` | 窗口长度为 5，指标类型为 `conflux_dispatch_proxy`。 |
| `agy_calls`、`codex_calls`、`other_calls` | 按代理归类的派单数。 |
| `agy_allowed_next` | 当前账本可见记录是否允许下一次 AGY 派单。 |
| `paid_calls`、`total_dispatches` | 付费派单数和全部派单数。 |
| `agy_coordinator` | 启用 AGY 日志读取时，额外展示协调会话数、轮次、各类 token 计数及最新轮次的最大上下文 token 数。 |
| `codex_tokens` | 显式提供 `--codex-jsonl <path>` 时，展示该会话的窗口 token 用量或统计状态。 |

例如，窗口内有 3 次 Codex 派单、0 次 AGY 派单时，`agy_allowed_next` 为 `true`。实际订阅额度以服务商显示为准。

### `conflux handoff` · 发布并核验交接单

里程碑验收后或准备切换会话时，先写好交接单，再发布到已存在的目录。源文件须为 UTF-8 编码的六行 Markdown，每行有非空内容并以换行符（LF）结尾，最后一行也需要 LF。

```markdown
# <Title>
ID: <id>
Run: <run>
Task: <task>
Dispatch: <dispatch>
Next: <next>
```

交接标识（ID）必须完全匹配 `^[A-Za-z0-9._-]+$`，且不能是 `.` 或 `..`。以下示例把 `handoff.md` 发布为 `handoffs/<ID>.md`，再按字节核验。

```sh
conflux handoff publish --dir handoffs --file handoff.md
conflux handoff verify --dir handoffs --file handoff.md
```

| 命令 | 退出码 |
| --- | --- |
| `publish` | `0` 新建，`10` 同名同内容，`11` 同名但内容冲突，`2` 输入无效或缺少所需文件、目录。 |
| `verify` | `0` 内容匹配，`11` 内容冲突，`2` 输入无效或缺少所需文件、目录。 |

`conflux --help` 的顶层列表只显示 `dispatch`，因为入口单独分流 `usage` 和 `handoff`。完整帮助请分别运行 `conflux dispatch --help`、`conflux usage --help` 和 `conflux handoff --help`。参数和错误处理见 [CLI 契约](docs/cli-contract.md)。

## 术语速查

| 术语 | 含义 |
| --- | --- |
| AGY / DSH | Antigravity 协调角色 / DeepSeek Harness 调研与验收角色。 |
| 五小时滚动窗口 | 从查询时间往前推五小时，左端点排除，右端点包含。 |
| `dispatchId` | Orca 派单回执中的唯一标识，用于账本去重和对照执行结果。 |
| `handoff` / `Next` | 记录跨会话接手信息的文件 / 接手后的具体下一步。 |
| 打磨期 / 冻结期 | 对齐方案并查证的阶段 / 用户拍板后按契约执行的阶段。 |
| `worker_done` | Orca 执行者主动送达的完成回报，协调者据此核对终态与验收证据。 |
| `keep-open` | 保留执行者终端所用的 Orca 选项。 |

## 项目结构与文档导航

| 路径 | 内容 |
| --- | --- |
| [`bin/conflux`](bin/conflux)、[`bin/conflux.cmd`](bin/conflux.cmd)、[`install.sh`](install.sh) | Unix 和 Windows 入口、Unix 安装脚本。 |
| [`conflux.py`](conflux.py)、[`conflux_usage.py`](conflux_usage.py)、[`conflux_handoff.py`](conflux_handoff.py) | 派单与入口分流、用量统计、交接发布和核验。 |
| [`policy.json`](policy.json)、[`examples/`](examples/) | 路由示例与客户端配置示例。 |
| [`.agents/skills/`](.agents/skills/)、[`tests/`](tests/) | 按需技能与自动化测试。 |
| [`AGENTS.md`](AGENTS.md)、[`CLAUDE.md`](CLAUDE.md)、[`GEMINI.md`](GEMINI.md) | 共用规则、Claude Code 和 Gemini CLI 的规则入口。 |

- **契约与设计**：[CLI 契约](docs/cli-contract.md)、[设计说明](docs/design.md)、[发布清单](docs/release-checklist.md)。
- **架构决策记录（ADR）**：[Orca 管理生命周期](docs/adr/0001-orca-owns-lifecycle.md)、[轻量 CLI 与五小时配额](docs/adr/0002-thin-cli-billing-and-5h-quota.md)、[客户端写保护与回退](docs/adr/0003-client-native-guards-and-fallbacks.md)、[共用规则与按需技能](docs/adr/0004-agents-md-and-ondemand-skills.md)。
- **前置调研**：维护工作区的 `docs/research` 有五份本地资料，发布树未收录。文件为 `01-local-to-vs-orca.md`、`02-oss-benchmark.md`、`03-spike-a-orca-lifecycle.md`、`04-spike-b1-guard-and-skills.md`、`05-spike-b2-billing-otel-dsh.md`。
- **实测记录**：[协作摩擦日志](docs/friction-log.md)。

## 边界、测试与版本演进

Conflux 负责派单准入、成功回执记账、只读统计及交接文件。Orca 管理 Run、Task、Worker 和 Dispatch 的状态、恢复与资源回收。客户端与工作区权限负责实际写保护。如果直接调用 Orca 绕过 Conflux 入口，则不会经过准入检查。

在仓库根目录运行测试。原生 Windows 将 `python3` 换成 `python`。

```sh
python3 -m unittest discover -s tests -v
```

- **v0.1.0** 发布 Alpha，提供派单准入、五小时窗口和交接命令。
- **v0.2.0** 加入默认 DSH 路由和按需自主推进技能。**v0.2.1** 收紧派单与自主推进规则，并加入五小时 AGY 协调会话 token 统计。
- **v0.3.0** 精简共用协作规则，按动作加载验收与异常处理说明。**v0.3.1** 收紧执行边界与会话交接流程。

项目采用 [MIT License](LICENSE)。
