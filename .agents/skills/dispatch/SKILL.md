---
name: conflux-dispatch
description: "Use when dispatching Orca workers, checking the five-hour dispatch window, or publishing and verifying a Conflux handoff."
---

只在准备派单、查询五小时窗口或交接时加载。按当前 Run 和策略填写参数。
默认策略为 `~/.config/conflux/policy.json`，默认账本为 `~/.local/state/conflux/ledger.jsonl`。

```sh
conflux dispatch --agent codex --profile default \
  --model "$CODEX_MODEL" --cwd . -- \
  --from "$ORCA_SESSION" --spec "执行任务契约并报告实测结果" \
  --worktree current --environment local --json
conflux dispatch --agent dsh --profile default --model default --cwd . -- \
  --from "$ORCA_SESSION" --spec "只读并行调研并汇总结果（禁止改文件与再派生）" \
  --worktree current --environment local --json
conflux usage
conflux handoff publish --dir "$HANDOFF_DIR" --file handoff.md
conflux handoff verify --dir "$HANDOFF_DIR" --file handoff.md
```

- 禁止绕过策略入口和付费授权。协调者禁止写业务代码，DSH 禁止再派生。
- 回执未知时，先用 Orca 原生 `request-show` 核查，再按原生恢复流程处理。
- 凭成功回执和唯一 Dispatch ID 核对派单。交接须读回验证，冲突须保留原件并报告。
- 凭实际测试输出和 Orca `worker_done` 终态验收。缺少证据时如实标明未验证项。
- `--environment local` 把派单固定在本机 Orca，覆盖 `ORCA_ENVIRONMENT`。远端按 Orca 原生 placement 指南，不与 `--on` 混用。
- `$CODEX_MODEL` 须精确匹配用户级 `policy.json` 中对应 agent/profile 的 model（model 为 `default` 时不传 `--model`），否则报 `unknown policy route`。`$ORCA_SESSION` 填自己的 orca_session_id。`--json` 不可省，账本只在退出码 0 且回执含 `dispatchId` 时记账。
- 跨项目派单时，核心实现交 Codex，spec 写明文件范围，同工作树同文件只允许一个写入者，冲突用原生独立 worktree。
- handoff 文件须为 LF 结尾的 6 行 Markdown，`--dir` 须已存在，文件名由 ID 决定。`publish` 退出码 `0` 新建、`10` 同内容已存在、`11` 冲突；`verify` 为 `0`/`11`，缺文件或目录为 `2`。`0` 和 `10` 都算成功，可继续 `verify`。
