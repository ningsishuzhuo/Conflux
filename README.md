# Conflux

[![Tests](https://github.com/ningsishuzhuo/Conflux/actions/workflows/test.yml/badge.svg)](https://github.com/ningsishuzhuo/Conflux/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Conflux 是给 [Orca](https://github.com/stablyai/orca) 用的派单小工具：按你写的策略检查每次派单是否允许并记录用量，避免超出订阅额度或误用付费模型。核心约 270 行纯 Python 标准库，执行生命周期全交 Orca，不重复造轮子。

状态：Alpha，接口可能调整。

安装 → 照常和 AI 聊天，需要派单时由 AI 自动调用 `conflux` → 用 `conflux usage` 看用量。

## 快速安装

需要 Python ≥ 3.10 和已加入 PATH 的 [Orca CLI](https://github.com/stablyai/orca)。在 macOS、Linux 或 WSL 中运行：

```sh
git clone https://github.com/ningsishuzhuo/Conflux.git && cd Conflux
./install.sh --dry-run  # 可选，检查但不写入
./install.sh
```

安装脚本将仓库示例策略中的 `"example"` 换成 `"default"`，写入 `~/.config/conflux/policy.json`；已有策略不会覆盖。它还会创建账本目录 `~/.local/state/conflux/`，以及指向本仓库的三个软链：`~/.local/bin/conflux`、`~/.agents/skills/conflux-dispatch` 和 `~/.agents/skills/conflux-autonomy`。移动或删除仓库后软链会失效；卸载时删除这三个软链即可。若软链位置已有其他文件，脚本会停止。

如果 `~/.local/bin` 不在 PATH 中，将下面一行写入 `~/.zshrc` 或 `~/.bashrc`，然后重开终端：

```sh
export PATH="$HOME/.local/bin:$PATH"
```

运行 `conflux usage` 验证安装。

<details>
<summary>原生 Windows</summary>

原生 Windows 目前仅通过 CI 验证，尚未对真实 Windows Orca 实测。在仓库根目录打开 PowerShell，确保使用真正的 Python，避开 Microsoft Store 的 `python` 占位程序，然后运行：

```powershell
New-Item -ItemType Directory -Force "$HOME/.config/conflux", "$HOME/.local/state/conflux" | Out-Null
$policy = "$HOME/.config/conflux/policy.json"
if (!(Test-Path $policy)) { [IO.File]::WriteAllText($policy, (Get-Content -Raw policy.json).Replace('"example"', '"default"'), [Text.UTF8Encoding]::new($false)) }
$env:PATH = "$(Join-Path (Get-Location) 'bin');$env:PATH"
conflux usage
```

这里的 PATH 修改仅对当前会话有效。

</details>

## 第一次派单

在 Orca 会话中直接对 AI 说：「请用 Codex 运行本项目的测试并报告结果。」AI 会按派单 Skill 调用 Conflux。

也可以手动试跑：将 `$ORCA_SESSION` 设为当前 Orca 会话 ID，使用下面的命令。示例策略需要有 `codex / default / default` 路由。

```sh
conflux dispatch --agent codex --profile default --model default --cwd . -- \
  --from "$ORCA_SESSION" --spec "运行单测并报告失败项" \
  --worktree current --environment local --json
conflux usage
```

成功派发一次 Codex 后，用量输出示例：`{"window_hours": 5, "agy_calls": 0, "codex_calls": 1, "other_calls": 0, "agy_allowed_next": false, "metric_kind": "conflux_dispatch_proxy"}`。实际值取决于近 5 小时的账本记录。

## 角色分工

| 角色 | 用途 | 约束 |
| --- | --- | --- |
| Codex | 主力执行 | 成功派单计入配比 |
| DSH（DeepSeek Harness） | 只读调研、确定性验收、小范围机械改动默认路由 | 仅一次机会，含糊或失败转 Codex；机械改动须附 `git status`，工作区脏时转 Codex。禁止再派生；默认关闭终端保留，按需显式传 `--keep-open` |
| Claude Code | 定点审查或重大裁决 | 每次付费派单需明确授权 |
| Antigravity（AGY） | 轻量协调与验收 | 受下述配比限制 |

派发 Antigravity 前，近 5 小时 Antigravity 成功次数的 2 倍必须小于 Codex 成功次数；检查时还会把这次准备派发的 Antigravity 算进去，即 `2 × (AGY + 1) < Codex`。这是针对滚动限额的内置规则，不用 `antigravity` 路由不受影响；需要其他配比可以提 Issue 或 fork。

## 命令参考

### `dispatch`

`conflux dispatch` 检查策略后调用 Orca。`--` 前面是 Conflux 参数，后面原样传给 Orca；上面的示例通过 `--environment local` 指定本机，并用 `--json` 提供记入账本所需的 Dispatch ID。策略中的 `"model": "default"` 会让 Orca 使用客户端默认模型。付费路由须在 `--` 之前添加 `--authorize-paid "具体授权理由"`。

### `usage`

`conflux usage` 输出最近 5 小时的派单统计。实际订阅配额以服务商显示为准；策略和账本路径可分别通过 `CONFLUX_POLICY` 和 `CONFLUX_LEDGER` 指定。

### `handoff`

换客户端接力时，`handoff` 把任务状态写成 6 行文件，防止重复发布或覆盖已有内容。创建 UTF-8 文件 `handoff.md`，每行使用 LF，并以换行结尾：

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

常见退出码：`0` 成功，`2` 策略拒绝或输入无效，`10` 交接内容重复，`11` 交接内容冲突；完整说明见 [CLI 契约](docs/cli-contract.md)。

## 跨客户端接入

| 客户端 | 规则入口 | 协调会话写保护 |
| --- | --- | --- |
| Codex | [AGENTS.md](AGENTS.md) | 以 `-s read-only -a never` 启动，执行者使用独立可写工作区 |
| Claude Code | [CLAUDE.md](CLAUDE.md) 导入共用规则 | 使用客户端原生工具权限与工作区隔离 |
| Gemini CLI | [GEMINI.md](GEMINI.md) 导入共用规则 | 保留 Orca hook，追加 [BeforeTool 示例](examples/gemini-before-tool.json) 中的独立拒绝条目，核对脚本路径，并用工作区权限覆盖 shell 等其他写入面 |
| Antigravity | 提供 [AGENTS.md](AGENTS.md) 与 [派单 Skill](.agents/skills/dispatch/SKILL.md) 的路径 | 能隔离时使用文件权限或只读挂载，写入交给可写执行者 |

## 仓库文件地图

| 路径 | 职责 |
| --- | --- |
| [`install.sh`](install.sh) | macOS、Linux 和 WSL 安装脚本 |
| [`bin/conflux`](bin/conflux) | 启动器，设置用户级策略与账本默认值 |
| [`bin/conflux.cmd`](bin/conflux.cmd) | Windows 启动器 |
| [`conflux.py`](conflux.py) | 策略校验、派单、账本和用量查询 |
| [`conflux_handoff.py`](conflux_handoff.py) | 六行交接格式、发布及核验 |
| [`policy.json`](policy.json) | 四类路由及计费和保留终端的示例配置 |
| [`AGENTS.md`](AGENTS.md) | 共用角色分工与协调者写保护规则 |
| [`.agents/skills/dispatch/SKILL.md`](.agents/skills/dispatch/SKILL.md) | 派单、查询与交接流程 |
| [`.agents/skills/autonomy/SKILL.md`](.agents/skills/autonomy/SKILL.md) | 需求确定后的无人值守推进 |
| [`docs/`](docs/) | CLI 契约、设计决策及发布清单 |
| [`tests/`](tests/) | 自动化测试和公开发布检查 |

## 做什么与不做什么

Conflux 检查经过它的派单，按成功回执记录用量，并提供交接文件的发布和核验。

Orca 和客户端负责执行、断连恢复、重试及权限。Conflux 不负责供应商计费、状态迁移或自动重放。Antigravity、SSH 和 WSL 无法在写入时立即拦截时，协调者写保护只能作为约定。

## 测试

macOS、Linux 和 WSL：

```sh
python3 -m unittest discover -s tests -v
```

Windows：

```powershell
python -m unittest discover -s tests -v
```

## 许可

[MIT License](LICENSE) · [Issue](https://github.com/ningsishuzhuo/Conflux/issues)

可选的 `spend.json` 可为付费路由启用本地 Claude 滚动花费粗护栏；`usage` 将附带 `claude_spend`。价格与日志仅为估算，参见 `docs/adr/0005-local-claude-spend-guard.md`。
