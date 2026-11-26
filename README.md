# Conflux

Conflux 是面向 Orca 多客户端协作的薄策略层。它用 Python 3 标准库实现派单准入、五小时用量查询和可核验的六行交接。

## 为什么更轻

对比旧私有实现（约 4.3k 行），Conflux 两个生产模块合计最多 270 个非空、非注释行，按门禁上限计算约少 94%。Run、Task、Worker、终态和资源回收由 Orca 原生管理。客户端权限负责协调者写保护，仓库只保留共用规则和按需加载的技能。这个数字衡量代码规模。

## 快速开始

需要 Python ≥ 3.8（海象运算符）和 POSIX 环境（macOS / Linux，使用 `fcntl`），以及可用的 Orca CLI 和当前 Orca 会话。升级验证以 Orca 1.4.273 为对照。用 `orca orchestration worker-start --help` 核对当前版本原生参数。

1. 编辑 [策略表](policy.json)，把示例模型替换为客户端可用模型。每条路由精确匹配 `agent`、`profile`、`model`。Claude 路由保持 `paid`，每次付费派单须显式授权。
2. 设置 `CODEX_MODEL`、`ORCA_SESSION` 和 `LEDGER`，其中 `LEDGER` 指向现有目录内的账本文件。

```sh
python3 conflux.py dispatch --policy policy.json --agent codex --profile default \
  --model "$CODEX_MODEL" --cwd . --ledger "$LEDGER" -- \
  --from "$ORCA_SESSION" --spec "运行单测并报告结果" --worktree current --json
python3 conflux.py usage --ledger "$LEDGER"
```

`usage` 统计最近五小时取得唯一 Dispatch ID 的成功派单，另可用 `--codex-jsonl` 读取指定会话的 token 用量。Antigravity 派单带同一账本，计入候选后须满足 `2 × AGY_calls < Codex_calls`。实际订阅配额以服务商显示为准。`--now` 是测试用的固定时钟开关，默认使用当前 UTC 时间。

3. 创建 UTF-8 文件 `handoff.md`，用此格式填写真实 ID 和下一步，保留末尾换行。

```markdown
# 接手测试
ID: sample
Run: example-run
Task: example-task
Dispatch: example-dispatch
Next: 核对 Worker 的终态和测试输出
```

```sh
mkdir -p handoffs
python3 conflux.py handoff publish --dir handoffs --file handoff.md
python3 conflux.py handoff verify --dir handoffs --file handoff.md
```

4. Codex 读 [AGENTS.md](AGENTS.md)，协调会话使用 `-s read-only -a never`。Claude Code 和 Gemini CLI 从各自的 [Claude 入口](CLAUDE.md) 和 [Gemini 入口](GEMINI.md) 加载共用规则。将 [Gemini Hook 示例](examples/gemini-before-tool.json) 的独立拒绝项追加到现有配置，保留既有 Orca 钩子，核对脚本路径并用工作区权限限制 shell。Antigravity 派单显式提供 [技能路径](.agents/skills/dispatch/SKILL.md)。

## 边界

- 策略与比例门禁覆盖经 Conflux 入口的派单。五小时比例以当前已落账记录计算，并发准入可读到同一快照。
- 生命周期、断连恢复、请求重试和权限归 Orca 与客户端管理。Antigravity、SSH、WSL 缺少已验证的拒绝链路时按软约束处理。
- Conflux 的范围限于单个薄 CLI 和协作规则。供应商计费、跨 runtime 统一所有权、状态迁移和自动重放超出范围。
- 内部研究、会话与账号数据属于本地资料。按发布清单审查公开文件树和历史。

## 测试与许可

```sh
python3 -m unittest discover -s tests -v
```

详见 [CLI 契约](docs/cli-contract.md) 和 [发布与迁移清单](docs/release-checklist.md)。手工 Orca 回归在隔离 Run 中执行。

[MIT License](LICENSE)
