# ADR 0002 · 薄 CLI、计费准入与五小时配比

状态：已决定。

按精确 `(agent, profile, model)` 匹配静态策略，另校验 cwd。未知或歧义路由拒绝，额外付费须显式授权。通过后原样透传已校验的 Orca 参数。真实启动 Hook 调用传入空 env，准入放在 CLI。[CLI 契约](../cli-contract.md)

UTC 窗口 `now − 5h < ts ≤ now` 仅统计成功取得唯一 `dispatchId` 的派单。失败、取消和未知结果不计。DSH 与 Claude 仅记审计，均排除出 `AGY:Codex` 分子和分母。若 `Codex_calls == 0`，拒绝派发 Antigravity Worker，否则加入候选后须满足 `2 × AGY_calls < Codex_calls`。该比例是 Conflux 派单代理指标。

先检查策略和已落账窗口，再在锁外调用 Orca。只有成功取得 `dispatchId` 才短暂加锁去重并原子追加一行。并行检查可见同一份账本快照。失败或未知结果原样透传 Orca 退出码及输出，交 Orca 原生 `request-show` 或 `--retry-request` 恢复。CLI 无预记、冻结和重放状态。

只读统计展示派单代理比和 Codex JSONL 实际 token 旁证。DSH 默认承接纯只读调研、确定性验收跑腿及小范围机械改动，无需事前核算净收益；仅一次机会，含糊或失败转 Codex，机械改动须附 `git status`，工作区脏时转 Codex，叶节点禁止再派生。默认不保留终端，按需显式透传 `--keep-open`。生产代码门禁为 `conflux.py` 非空非注释行 ≤ 200 行，排除 `tests/` 与 `policy.json`，从切片 1 起由单测校验。
