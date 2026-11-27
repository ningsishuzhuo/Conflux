---
name: conflux-dispatch
description: "派发 Orca worker、查询五小时派单窗口，或发布与核验 Conflux 交接文件时按需加载。"
---

只在准备派单、查询五小时窗口或交接时加载。按当前 Run 和策略填写参数。
默认策略为 `~/.config/conflux/policy.json`，默认账本为 `~/.local/state/conflux/ledger.jsonl`。

```sh
conflux dispatch --agent codex --profile default \
  --model "$CODEX_MODEL" --cwd . -- \
  --from "$ORCA_SESSION" --spec "执行任务契约并报告实测结果" \
  --worktree current --environment local --json
conflux dispatch --agent dsh --profile default --model default --cwd . -- \
  --from "$ORCA_SESSION" --spec "执行只读调研、确定性验收或小范围机械改动（禁止再派生）" \
  --worktree current --environment local --json
conflux dispatch --agent claude --profile default --model default --cwd . \
  --authorize-paid "<授权理由>" -- \
  --from "$ORCA_SESSION" --spec "执行授权终审" \
  --worktree current --environment local --json
orca orchestration worker-release --environment local --dispatch <id> --json
orca orchestration worker-stop --environment local --dispatch <id> --json
conflux usage
conflux handoff publish --dir "$HANDOFF_DIR" --file handoff.md
conflux handoff verify --dir "$HANDOFF_DIR" --file handoff.md
```

- 禁止绕过策略入口和付费授权。协调者禁止写业务代码，DSH 禁止再派生。
- 回执未知时，先用 Orca 原生 `request-show` 核查，再按原生恢复流程处理。
- 凭成功回执和唯一 Dispatch ID 核对派单。交接须读回验证，冲突须保留原件并报告。
- 凭实际命令输出和 Orca `worker_done` 终态验收，Task/Dispatch ID 须与本次回执一致；启动 `idle` 或旧终态不算完成。缺少证据时如实标明未验证项。
- `--environment local` 把派单固定在本机 Orca，覆盖 `ORCA_ENVIRONMENT`。远端按 Orca 原生 placement 指南，不与 `--on` 混用。
- 所有路由的 `--model` 均必填，须精确匹配用户级 `policy.json` 中对应 agent/profile 的 model（值为 `default` 时由 `conflux.py` 内部省略透传给 Orca），否则报 `unknown policy route`。`$ORCA_SESSION` 填自己的 orca_session_id。`--json` 不可省，账本只在退出码 0 且回执含 `dispatchId` 时记账。
- 跨项目派单时，核心实现交 Codex，spec 写明依赖基线、唯一写入范围、验收命令及预期、范围外事项；同工作树同文件只允许一个写入者，冲突用原生独立 worktree。要求 worker 将关键结论与实测输出直接写入 `worker_done`。
- handoff 文件须为 LF 结尾的 6 行 Markdown，`--dir` 须已存在，文件名由 ID 决定。`publish` 退出码 `0` 新建、`10` 同内容已存在、`11` 冲突；`verify` 为 `0`/`11`，缺文件或目录为 `2`。`0` 和 `10` 都算成功，可继续 `verify`。

- `--worktree current` 固定指向协调者工作区，`--cwd` 不改变放置。派往已有子 worktree 用 `--worktree path:<child-dir>`，也可用 `name:`、`branch:`、`identity:`。
- 多行 spec 和 `gh` 评论一律落文件，分别用 `--spec-file` / `--body-file`，禁止 heredoc（`<<`）。
- 验收后用上述 release 命令关一次性终端，保留 worktree。遇 409/429 或限流重试立即用上述 stop 命令止损。
- spec 要求 `worker_done` ≤ 20 行结构化摘要。遇次要歧义按最简假设直接给结论并列明假设，禁止中途停下反问。
- Claude 须经 `gate` 逐次人工批准。spec 内联 DSH 摘要，标明审内联稿还是磁盘改动，禁业务/仓库 shell 与扫仓，仅放行最后的 `worker_done`，总输出 ≤ 25 行。
