# ADR 0004 · 共用 AGENTS.md 与按需技能

状态：已决定。

根 `AGENTS.md` 维护角色权限、派单条件和技能索引。沿用 Superpowers 与 OpenHands microagents 的按需思路，短 `SKILL.md` 只写触发条件、步骤和验收。

Codex 使用原生发现，Claude Code 和 Gemini CLI 用薄入口读取共用规则。派单按需指明技能路径，Antigravity 使用明确路径。无需常驻注入器。

