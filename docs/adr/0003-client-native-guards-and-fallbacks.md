# ADR 0003 · 客户端原生写保护与回退

状态：已决定。

- Codex 协调者使用 `-s read-only -a never`，本机已实测写入硬阻断。
- Gemini CLI 保留 Orca hook，独立追加 `BeforeTool` deny 条目。匹配工具由客户端拒绝，其他写入面用工作区权限覆盖。组合链路列入验收。
- Claude Code 使用原生工具权限与工作区隔离，弃用旧启发式 Guard。
- Antigravity、SSH、WSL 按软约束处理，工作区权限或只读挂载在执行端落实回退。

