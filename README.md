# Conflux

[![Tests](https://github.com/ningsishuzhuo/Conflux/actions/workflows/test.yml/badge.svg)](https://github.com/ningsishuzhuo/Conflux/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Conflux 帮你在 Orca 中安全地协调多个 AI Agent。

它用零第三方依赖的轻量代码处理付费护栏、限额配比和原子交接，执行生命周期交给 Orca。

装完后平时照常和 AI 聊天，需要派单时由 AI 按 Skill 调用 `conflux`。

## 快速安装

准备 Python ≥ 3.10 和已加入 PATH 的 Orca CLI。在 macOS、Linux 或 WSL 的仓库目录中运行：

```sh
./install.sh --dry-run  # 可选：先检查，不写入
./install.sh
```

脚本保留已有策略，遇到冲突文件或软链会停止；它不会修改 shell 配置。按输出提示设置 PATH，运行 `conflux usage` 验证。策略位于 `~/.config/conflux/policy.json`，账本位于 `~/.local/state/conflux/ledger.jsonl`；可用 `CONFLUX_POLICY` 和 `CONFLUX_LEDGER` 覆盖。

### 原生 Windows（PowerShell）

原生 Windows 目前仅经 CI 验证，`install.ps1` 推迟至 v0.1.1。以下命令在仓库根目录执行：

原生 Windows 从命令提示符运行 `bin\conflux.cmd`，需要将 Python 加入 PATH。
在仓库根目录使用 PowerShell 准备目录和策略，并将 `bin` 加入当前会话的 PATH：

```powershell
New-Item -ItemType Directory -Force "$HOME/.config/conflux", "$HOME/.local/state/conflux" | Out-Null
$policy = "$HOME/.config/conflux/policy.json"
if (!(Test-Path $policy)) { [IO.File]::WriteAllText($policy, (Get-Content -Raw policy.json).Replace('"example"', '"default"'), [Text.UTF8Encoding]::new($false)) }
$env:PATH = "$(Join-Path (Get-Location) 'bin');$env:PATH"
```

请避开 Microsoft Store 的 `python` 占位程序；编写 handoff 文件时避免使用可能写入 UTF-16 或 CRLF 的 PowerShell 重定向，须使用 UTF-8 和 LF。
可通过 `CONFLUX_POLICY` 和 `CONFLUX_LEDGER` 指定策略与账本。
默认使用 `%USERPROFILE%\.config\conflux\policy.json` 和 `%USERPROFILE%\.local\state\conflux\ledger.jsonl`。

### 第一次派单

在 Orca 协调会话中告诉 AI：“请用 Codex 运行本项目的测试并报告结果。” AI 应按派单 Skill 执行；也可以参考下面的命令。

## 进阶参考

### 4-AI 速查

| 角色 | 用途 | 约束 |
| --- | --- | --- |
| Codex | 主力执行 | 成功回执计入配比 |
| DSH | 独立低风险辅助 | 叶节点，默认保留终端 |
| Claude Code | 定点审查或重大裁决 | 每次付费派单需明确授权 |
| Antigravity | 轻量协调与验收 | 候选须满足 `2 × (AGY + 1) < Codex` |

该公式是针对滚动限额的内置代理指标，不使用 `antigravity` 路由完全不受影响。其他配比欢迎提 Issue，v0.2 将视需求考虑配置化。

## 3. 日常命令

### `conflux dispatch` · 派单

将 `ORCA_SESSION` 设为当前协调会话 ID。下例要求用户策略有 `codex / default / default` 路由。

```sh
conflux dispatch --agent codex --profile default --model default --cwd . -- \
  --from "$ORCA_SESSION" --spec "运行单测并报告失败项" \
  --worktree current --environment local --json
```

- 策略中的 `"model": "default"` 会让 Conflux 省略传给 Orca 的 `--model`，跟随客户端默认模型。
- 付费路由须在分隔符 `--` 之前添加 `--authorize-paid "具体授权理由"`。
- 本机入账派单保留分隔符之后的两个 Orca 参数。`--environment local` 固定在本机并覆盖 `ORCA_ENVIRONMENT`。`--json` 提供入账所需的 Dispatch ID。

### `conflux usage` · 查询最近 5 小时

```sh
conflux usage
conflux usage --codex-jsonl "$CODEX_SESSION_JSONL"
```

`--codex-jsonl` 可重复传入，用于查询指定 Codex 会话的 token 用量。`--now <ISO 8601 时间>` 可固定测试时钟，默认使用当前 UTC。实际订阅配额以服务商显示为准。

### `conflux handoff publish|verify` · 发布与核验

将下列六行写入 UTF-8 文件 `handoff.md`，填入真实 ID 和下一步。每行使用 LF，含末行。

```markdown
# 接手测试
ID: sample
Run: example-run
Task: example-task
Dispatch: example-dispatch
Next: 核对 Worker 终态和测试输出
```

```sh
mkdir -p handoffs
conflux handoff publish --dir handoffs --file handoff.md
conflux handoff verify --dir handoffs --file handoff.md
```

交接原子发布到 `<dir>/<ID>.md`（`ID` 须匹配 `^[A-Za-z0-9._-]+$` 且不能为 `.` 或 `..`），核验按字节比较内容。

| 退出码 | 含义 |
| --- | --- |
| `0` | 成功 |
| `2` | 策略拒绝、参数无效或所需文件缺失 |
| `10` | 交接发布重复，已有内容相同 |
| `11` | 交接内容冲突 |

`dispatch` 调用 Orca 后透传其退出码。完整参数与字段见 [CLI 契约](docs/cli-contract.md)。

## 4. 跨客户端接入

| 客户端 | 规则入口 | 协调会话写保护 |
| --- | --- | --- |
| Codex | [AGENTS.md](AGENTS.md) | 以 `-s read-only -a never` 启动，执行者使用独立可写工作区 |
| Claude Code | [CLAUDE.md](CLAUDE.md) 导入共用规则 | 使用客户端原生工具权限与工作区隔离 |
| Gemini CLI | [GEMINI.md](GEMINI.md) 导入共用规则 | 保留现有 Orca hook，追加 [BeforeTool 示例](examples/gemini-before-tool.json) 中的独立拒绝条目，核对脚本路径，并用工作区权限覆盖 shell 等其他写入面 |
| Antigravity | 提供 [AGENTS.md](AGENTS.md) 与 [派单 Skill](.agents/skills/dispatch/SKILL.md) 的路径 | 能隔离时使用文件权限或只读挂载，写入交给可写执行者 |

## 5. 仓库文件地图

| 路径 | 职责 |
| --- | --- |
| [`bin/conflux`](bin/conflux) | 跨项目启动器，注入用户级策略与账本默认值 |
| [`conflux.py`](conflux.py) | 策略校验、派单、账本和用量查询 |
| [`conflux_handoff.py`](conflux_handoff.py) | 六行交接格式、原子发布及核验 |
| [`policy.json`](policy.json) | 四类路由及计费和保留终端的示例配置 |
| [`AGENTS.md`](AGENTS.md) | 共用角色分工与协调者写保护规则 |
| [`.agents/skills/dispatch/SKILL.md`](.agents/skills/dispatch/SKILL.md) | 按需加载的派单、查询与交接流程 |
| [`docs/`](docs/) | CLI 契约、设计决策及发布清单 |
| [`tests/`](tests/) | 自动化测试和公开发布检查 |

## 6. 边界、测试与许可

- 策略和比例门禁覆盖经 Conflux 入口的派单。配比基于已落账记录，并发准入可能读取同一快照。
- 生命周期、断连恢复、请求重试和权限归 Orca 与客户端管理。Antigravity、SSH、WSL 缺少已验证的同步拒绝链路时，协调者写保护属于软约束。
- 供应商计费、跨运行时统一所有权、状态迁移和自动重放超出范围。
- 原生 Windows 当前仅通过三平台 CI 假 Orca 验证，尚未对真实 Windows Orca 端到端实测。

```sh
python3 -m unittest discover -s tests -v
```

手工 Orca 回归在隔离 Run 中执行。项目采用 [MIT License](LICENSE)。

项目目前处于 Alpha 阶段，接口和行为可能调整。
欢迎通过 [Issue](https://github.com/ningsishuzhuo/Conflux/issues) 反馈问题和建议。
