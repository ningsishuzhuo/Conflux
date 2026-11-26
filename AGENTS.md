# Conflux 协作规则

| 角色 | 派单原则 |
| --- | --- |
| Antigravity | 极轻协调，受 5 小时滚动限额约束。负责定契约、重大决策、验收。 |
| Codex | 主力执行。一次交付完整契约，涵盖细节规划、实现、调试、测试和证据。 |
| DSH | 只接独立、低风险、有高净收益的并行任务。需保留终端时用 Orca 原生 `--keep-open`。叶节点禁止再派生。 |
| Claude Code | 默认拒绝。定点审查或重大裁决需要绑定本次派单的显式付费授权。 |

Antigravity 派单带账本，按 UTC 最近 5 小时去重统计成功回执。加入候选后须满足 `2 × AGY_calls < Codex_calls`。DSH 和 Claude 只记审计。派单次数是代理指标，服务商配额另查。

## 协调者写保护

- Codex 用 `-s read-only -a never`，执行者使用独立可写工作区。
- Gemini CLI 保留 Orca hook，追加独立 `BeforeTool` 拒绝条目。对 shell 等其他写入面使用工作区权限。
- Claude Code 使用原生工具权限和工作区隔离。
- Antigravity、SSH、WSL 在未确认同步拒绝时按软约束处理。能隔离时用文件权限或只读挂载，把写入交给可写执行者。

| 常见借口 | 现实 |
| --- | --- |
| 协调者顺手改几行更快 | 协调权限只覆盖定契约和验收，改动交给执行者。 |
| 看过差异就可以报完成 | 先取得实际验证输出，再核对 Orca 终态。缺证据就报告未验证。 |
| 多派个 DSH 总会更快 | 只有任务独立、能并行且净收益高于协调成本时才派。 |

## 按需入口

- 派单、查询和交接时读 `.agents/skills/dispatch/SKILL.md`。
- Run、Task、Worker 生命周期及恢复见 Orca 原生 `orchestration` 指南。
