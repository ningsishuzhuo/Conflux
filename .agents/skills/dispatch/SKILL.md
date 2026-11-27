---
name: conflux-dispatch
description: "派发 Orca worker、查询五小时窗口或交接时按需加载。"
---

```sh
conflux dispatch --agent "$AGENT" --profile "$PROFILE" --model "$MODEL" --cwd . -- --from "$ORCA_SESSION" --spec-file "$SPEC" --worktree current --environment local --json
conflux dispatch --agent claude --profile "$PROFILE" --model "$MODEL" --cwd . --authorize-paid "$REASON" -- --from "$ORCA_SESSION" --spec-file "$SPEC" --worktree current --environment local --json
conflux usage
orca orchestration inbox --environment local --terminal "run:$RUN" --full --json
orca orchestration worker-list --environment local --run "$RUN" --full --json
orca orchestration worker-release --environment local --dispatch "$DISPATCH" --json
orca orchestration worker-stop --environment local --dispatch "$DISPATCH" --json
conflux handoff publish --dir "$HANDOFF_DIR" --file handoff.md
conflux handoff verify --dir "$HANDOFF_DIR" --file handoff.md
```

- `--environment local` 固定本机，远端参照 Orca placement 指南。所有路由的 `--model` 精确匹配策略中 agent/profile；`--json` 必填，退出 0 且有 `dispatchId` 才记账。
- 终端会话且 `$ORCA_SESSION` 非空时传 `--from "$ORCA_SESSION"`，聊天会话省略 `--from`。
- `--spec-file` 放会话 scratch 或临时目录，禁写入未冻结的业务仓库，禁 heredoc。契约写明阶段、权限边界、目标、写入范围、验收证据及 ≤ 20 行的 worker_done 摘要。
- `--worktree current` 指协调者工作区；已有执行工作树用 `--worktree path:<child-dir>`。`--cwd` 不决定放置。需保留终端时传 `--keep-open`。
- 回执未知先查 `request-show`；释放和止损使用对应 Dispatch ID。
- handoff 为 LF 结尾的 6 行 Markdown，字段依次为 `# <Title>` / `ID: <id>` / `Run: <run>` / `Task: <task>` / `Dispatch: <dispatch>` / `Next: <next>`。目录须已存在。publish 为 0 新建、10 已存在且一致、11 冲突；verify 为 0 一致、11 冲突；缺文件或目录为 2。publish 返回 0 或 10 后继续 verify。
