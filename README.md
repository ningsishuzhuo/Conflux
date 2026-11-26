# Conflux

Conflux 是构建在 **Orca 原生编排**之上的极薄多 Agent 策略层，负责跨模型派单、额外付费硬护栏、5 小时滚动窗口配比，以及可核验的六行原子交接。

核心由 251 行有效 Python 代码组成（不计空行和注释），仅使用 Python 3.8+ 标准库，零第三方依赖。跨项目 Bash 包装器共 38 行。

```text
Coordinator --> Conflux (route / paid / ratio) --> Orca (Run / Task / Worker)
                    |                                  |
                    +<-------- dispatch receipt -------+
                    +--------> ledger / usage
                    +--------> atomic handoff / verify
```

Run、Task、Worker 的生命周期、终态和资源回收由 Orca 原生管理。

## 1. 派单速查

简单任务由当前 Agent 直接回答。需要派单时，按下表选择角色。

| 角色（`agent`） | 何时使用 | 约束 |
| --- | --- | --- |
| Codex（`codex`） | 主力厚委派，一次交付完整的规划、实现、调试、测试和证据 | 成功回执计入配比的 Codex 次数 |
| DSH（`dsh`） | 独立、低风险、可并行，且净收益高于协调成本 | 示例策略自动追加 Orca 的 `--keep-open`。叶节点禁止再派生 |
| Claude Code（`claude`） | 定点审查或重大裁决 | 默认拒绝付费派单。每次须显式传入 `--authorize-paid <理由>` |
| Antigravity（`antigravity`） | 极轻协调，负责定契约、重大决策和验收 | 使用同一账本，近 5 小时须满足 `2 × (AGY + 1) < Codex` |

配比以 UTC 滚动窗口内成功派单的唯一 Dispatch ID 计数，式中的 `+ 1` 代表候选派单。DSH 和 Claude Code 只计审计。

## 2. 五分钟安装

准备 **Python ≥ 3.8**、**POSIX 环境（macOS / Linux，含 Bash）** 和可用的 **Orca CLI**。升级对照版本为 **1.4.273**。派单需要当前 Orca 会话，可用 `orca orchestration worker-start --help` 核对原生参数。

**第一步：准备用户级策略与状态目录。** 在 Conflux 仓库根目录执行，已有用户级策略会保留。

```sh
mkdir -p "$HOME/.config/conflux" "$HOME/.local/state/conflux"
test -e "$HOME/.config/conflux/policy.json" ||
  sed 's/"example"/"default"/g' policy.json > "$HOME/.config/conflux/policy.json"
```

默认命令已把 `example` 替换为 `default`（跟随客户端默认模型）；如需固定模型，编辑 `~/.config/conflux/policy.json` 并保持 Claude 路由的 `billing` 为 `paid`。路由精确匹配 `agent`、`profile`、`model` 三元组。这里的 `profile` 是 Conflux 策略标签。

**第二步：软链命令与全局 Skill。** 仍在 Conflux 仓库根目录执行。

```sh
mkdir -p "$HOME/.local/bin" "$HOME/.agents/skills"
ln -sfn "$(pwd -P)/bin/conflux" "$HOME/.local/bin/conflux"
ln -sfn "$(pwd -P)/.agents/skills/dispatch" "$HOME/.agents/skills/conflux-dispatch"
export PATH="$HOME/.local/bin:$PATH"
```

如需新终端也能使用，把最后一行加入 Shell 启动配置。随后可在任意项目目录调用 `conflux`。

策略和账本的查找优先级依次是显式参数、`CONFLUX_POLICY` / `CONFLUX_LEDGER`、用户级默认路径。默认策略为 `~/.config/conflux/policy.json`，默认账本为 `~/.local/state/conflux/ledger.jsonl`。为防止外部仓库伪造策略，`bin/conflux` 绝不回退到当前目录的 `./policy.json`。

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
- 内部研究、会话和账号数据留在本地。公开前按 [发布与迁移清单](docs/release-checklist.md) 审查文件树与历史。

```sh
python3 -m unittest discover -s tests -v
```

手工 Orca 回归在隔离 Run 中执行。项目采用 [MIT License](LICENSE)。
