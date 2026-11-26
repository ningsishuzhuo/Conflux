---
name: conflux-dispatch
description: "Use when dispatching Orca workers, checking the five-hour dispatch window, or publishing and verifying a Conflux handoff."
---

只在准备派单、查询五小时窗口或交接时加载。按当前 Run 和策略填写参数。

```sh
python3 conflux.py dispatch --policy policy.json --agent codex --profile default \
  --model "$CODEX_MODEL" --cwd . --ledger "$LEDGER" -- \
  --from "$ORCA_SESSION" --spec "执行任务契约并报告实测结果" --worktree current --json
python3 conflux.py usage --ledger "$LEDGER"
python3 conflux.py handoff publish --dir "$HANDOFF_DIR" --file handoff.md
python3 conflux.py handoff verify --dir "$HANDOFF_DIR" --file handoff.md
```

- 禁止绕过策略入口和付费授权。协调者禁止写业务代码，DSH 禁止再派生。
- 回执未知时，先用 Orca 原生 `request-show` 核查，再按原生恢复流程处理。
- 凭成功回执和唯一 Dispatch ID 核对派单。交接须读回验证，冲突须保留原件并报告。
- 凭实际测试输出和 Orca `worker_done` 终态验收。缺少证据时如实标明未验证项。
