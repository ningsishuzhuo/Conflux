---
name: conflux-autonomy
description: "仅在需求确定后无人值守自动推进项目时按需加载。"
---

# 自主推进

## Step 0 · 强制预检

触发后第一步只读 `conflux-dispatch`、`orca skills get orchestration`、`~/.config/conflux/policy.json` 并运行 `conflux usage`。契约冻结前禁止读取业务源码、PR Diff 或执行业务命令，小任务及纯只读 PR 审核同样执行。

## 开工契约冻结

与用户确认四项：
1. 任务 DAG、依赖及 worktree 划分。
2. 验收命令由协调者持有，验收时核对命令与对应测试未遭篡改。
3. 禁止未授权 `git push`、删库、擅改需求或绕过付费授权。
4. Claude 默认拒绝，禁止开工一次性预授权。常规验收由 DSH + AGY 完成，仅高危架构/安全裁决或 Codex 熔断兜底可经 `gate` 取得用户逐次人工同意。批准后内联 DSH 摘要，标明审阅对象，禁业务 shell 与扫仓，仅放行 `worker_done`，输出 ≤ 25 行且结构化摘要 ≤ 20 行。

## 四角色静默闭环

- AGY 仅协调、决策与验收，禁包办只读调研、跑腿验收和业务编码。大粒度打包 Codex 契约，独立任务同轮以单命令并行派发，要求 `worker_done` ≤ 20 行结构化摘要。
- DSH 做只读调研、确定性验收跑腿、小范围机械改动，仅给一次机会，禁再派生，脏工作区交 Codex。
- Codex 做核心实现与修复，兼任 Claude 限流后的对抗式只读审查。
- Claude 仅承担逐次人工批准的高危终审或兜底。

## 看门狗、降级与熔断

- 派单后挂单次原生定时检查，轻量 Claude/DSH 90 秒、Codex 5 分钟。收到回执自动取消，禁止密集轮询。
- 到时用 `worker-show` 与 `worker-read --source auto` 检查。已完结或发问则直接拉回处理，正常推进则续订闹钟。见 409、429 或限流重试立即 `worker-stop`。
- Claude 审查、终审或拍砖限流后，立即用全新独立上下文的 Codex 交叉审查，由 AGY 拍板。常规验收交 DSH + AGY。若本次 Claude 用于 Codex 熔断救场，或替补 Codex 不可用，必须 `gate` 叫人，禁 AGY 下场。
- 验收失败附旧证据返工。同任务连续失败超过冻结上限（默认 2～3 次）或触及高危红线时调用 Orca 原生 `gate`。

## 收尾与交接

- 确认 `worker_done` 后立即释放不再复用的一次性终端：`orca orchestration worker-release --environment local --dispatch <id> --json`。只关终端，保留待审 PR 分支与 worktree。
- 里程碑验收通过后由执行者完成本地 `git commit`，协调者用 `handoff publish/verify` 发布并核验 6 行交接，默认存放在 `~/.local/state/conflux/handoffs/<项目名>/`。
- 汇报直接给出 handoff 绝对路径，并按实际路径提供可复制的新会话续跑指令，例如「读取 /绝对路径/handoff.md，按 Next 继续并沿用已冻结契约」。
- 每完成里程碑或 `conflux usage` 显示 `max_turn_context_tokens >= 80000`，主动提醒用户 `/compact` 或新开会话。
