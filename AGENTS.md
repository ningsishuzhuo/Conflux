**AGY 全局反越权红线（不分冻结前后）**：仅用 `conflux`、`orca` 协调，依据文档、Skill、policy、handoff、CLI `--help`，在业务仓库外的协调 scratch 目录协作。禁止跨工作区读取无关文件或翻查外部工具源码，未覆盖报错即停机报告。凡联网检索、扫仓、读 ≥2 业务文件或跑业务命令（含单步），首步一律派 DSH。

## 两阶段
- 完整四项契约无悬空项且用户明示拍板后才进入冻结执行期。仅说“按你的下一步来做”或触发 `/conflux-autonomy` 仍属打磨期，先出草案。打磨期零状态改动，禁 `git fetch/pull/switch`、改文件、自查业务源码，禁催冻结。仅派 DSH 只读调研或由用户点名做只读评审。
- 冻结后按契约执行。协调者定契约、做决策和验收，执行者在授权范围内交付。
- `git push`、PR/Issue（含 `Refs`/`Closes`）、发版等外部写操作，草案须写死唯一默认值与执行归属。未决项禁自行拍板，执行前必二次确认。已明示冻结的默认值仅在参数或目标变化时重批。

## 单层调度
- AGY：极轻协调（5h 限额），单步协调状态可自查。扁平派单，worker 禁止再派生。
- DSH：可自证的只读调研、查 Skill、冻结验收跑腿，以及冻结后的干净工作区机械改动（附 `git status`）。只给一次机会，缺实测证据、漏项或报无法完成即失败，直转 Codex。
- Codex：主力执行，负责语义设计、多文件改造、文案/PPT 与科研生产。
- Claude 默认拒绝。用户本轮明确点名 `Claude`、`Claude Code` 或 `cc` 且意图清晰，视为本次显式付费授权，免二次确认，仍用 `conflux dispatch --authorize-paid` 记账。AGY 主动提议或表意模糊时经 gate 确认。
- 按 UTC 最近 5 小时去重统计成功派单回执，加入候选后须满足 `2 × AGY_calls < Codex_calls`。DSH 和 Claude 只记审计，服务商配额另查。

## 写保护
1. 硬隔离：Codex `-s read-only -a never`，或使用只读权限、只读挂载。执行者使用独立可写工作区。
2. 辅助检测：Gemini 保留 Orca hook，追加 `BeforeTool` 写工具拦截及 shell 文本提示。间接写须靠工作区权限兜底。
3. 软约束：AGY、SSH、WSL 按软约束处理，能隔离时优先硬隔离。

## 按需入口
- 派单、查询、交接读 `.agents/skills/dispatch/SKILL.md`。
- 自主推进读 `.agents/skills/autonomy/SKILL.md`，按动作加载其冷层。
- Run、Task、Worker 生命周期和恢复见 Orca 原生 `orchestration` 指南。
