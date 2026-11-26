# Conflux 极简设计

## 定位

Conflux 是 MIT 许可的开源项目，由 Orca 原生执行底座、Python 标准库薄策略 CLI、共用 `AGENTS.md` 和按需短技能组成。面向单人维护，生产代码以非空非注释行计数，由单测校验 `conflux.py` ≤ 200 行、`conflux_handoff.py` ≤ 70 行，合计 ≤ 270 行。路径由调用方传入或从运行环境解析，禁止硬编码个人路径或密钥。

## 分工与额度

| 角色 | 派单规则 |
| --- | --- |
| Antigravity（Google AI Pro，5 小时滚动限额） | 极轻协调者，负责定契约、重大决策和验收。实现、细节规划与深挖交给执行者。 |
| Codex（ChatGPT Plus，无 5 小时硬限） | 主力执行者。以完整契约一次委派细节规划、实现、测试、调试与文档起草。 |
| DSH（低成本） | 仅承接独立、低风险且有净收益的并行辅助。作为叶节点禁止再派生。需保留可见终端时透传 Orca 原生 `--keep-open`，无需专用适配器。 |
| Claude Code（额外按需付费） | 默认拒绝。仅接受绑定本次派单的显式付费授权，用于定点 Review 或重大裁决。 |

UTC 滚动窗口为 `now − 5h < ts ≤ now`。只计首次取得唯一 `dispatchId` 的成功派单，失败、取消和结果未知均不计。DSH 与 Claude 仅记审计，均不进入 `AGY:Codex` 分子或分母。拟派 Antigravity Worker 时，若 `Codex_calls == 0` 则拒绝，否则加入候选后须满足 `2 × AGY_calls < Codex_calls`。该比例是 Conflux 派单代理指标。服务商配额与 Codex JSONL token 旁证分别展示。

## 派单与交接

- `dispatch` 依次执行静态策略与前置检查、原样派发 Orca、成功回执记账。精确匹配 `(agent, profile, model)`，验证工作目录，付费路由须有本次显式授权，拒绝透传参数覆盖已校验的字段。启动映射和透传边界见 [CLI 契约](cli-contract.md)。授权理由与日志均禁止携带密钥。
- 切片 2 用已落账记录检查窗口。Orca 调用在锁外执行，只有成功拿到 `dispatchId` 后才短暂加锁，按该 ID 去重并原子追加一行。并行准入可能看到同一账本快照，比例检查按各次准入可见的已完成记录执行。失败或未知原样返回 Orca 输出与退出码，由操作者通过 Orca 原生 `request-show` 与 `--retry-request` 恢复，Conflux 不预记、不冻结、不重放。
- Orca 独占 Run、Task、Worker、Dispatch 状态、终态、事件和资源回收。协调者以 `worker_done` 主动送达为准，从 Orca 核验终态。同一 runtime 的普通 Run 用 `run-use` 交权，原 owner 先停写，新 owner 回读 owner 和 generation。跨 runtime 固定原 owner，由接手方承接具体 Task。
- `usage` 只读输出窗口计数和实际比例，并可从指定 Codex JSONL 读取 `token_count`。按会话累计值的变化去重取增量，保留窗前基线，基线缺失或计数回退时标记缺失。Antigravity 暂无等价 token 口径。
- `handoff publish|verify` 接收六行 Markdown，字段依次为标题、ID、Run、Task、Dispatch、Next。按 ID 生成最终文件，限制 ID 为安全文件名。在同目录创建独占临时文件，写入并 flush、fsync，再以 `os.link` 发布，清理临时文件。核验仅消费最终文件并比对字节。同 ID 同内容返回 duplicate，异内容返回 conflict。
- 1.4.273 实测支持普通本机 Run 和已知请求重放。真实断连、跨身份、legacy、paired server 和终端跨创建者存活列入升级回归。若必须镜像 Orca 生命周期才能支持某个场景，停在原生可确认的边界。

## 客户端边界

- Codex 协调者用 `-s read-only -a never`，本机已实测写入硬阻断。执行者使用独立可写工作区。
- Gemini CLI 在 `hooks.BeforeTool` 追加独立 deny 条目，保留 Orca hook。匹配的写工具返回 `{"decision":"deny","reason":"read-only"}`。用工作区权限覆盖 shell 等写入面。实测已核对判定逻辑，合并后链路需验收。
- Claude Code 使用原生工具权限与工作区隔离，弃用旧启发式 Guard。Antigravity、SSH 和 WSL 的协调约束按软约束处理，执行端通过工作区权限或只读挂载回退。
- 付费准入和配比在薄 CLI 内执行。Orca 插件启动调用点传入空 env，恢复会话及绕过入口启动也超出 CLI 准入覆盖。

根 `AGENTS.md` 只放角色、权限、派单条件与技能索引。技能按 Superpowers / OpenHands microagents 风格，仅写触发条件、步骤与验收。Codex 从 `.agents/skills/` 发现，Claude 和 Gemini 通过薄入口读取共用规则并按明确路径读同一份技能。Antigravity 派单显式给路径。

## 垂直切片

每片先写失败用例，再以最小改动通过。测试使用临时目录、固定 UTC 时钟和假 Orca，真机复验使用隔离本机普通 Run，无付费授权时禁止启动付费会话。

| 切片与目标 | 变更文件 | TDD 验收命令与用例 | 依赖 |
| --- | --- | --- | --- |
| 1 · 静态准入并原样派发 | `conflux.py`、`policy.json`、`tests/test_dispatch.py` | `python3 -m unittest discover -s tests -p test_dispatch.py`。覆盖静态准入、argv 原样透传、Orca 退出码和生产代码行数门禁。 | 无 |
| 2 · 五小时窗口与只读统计 | `conflux.py`、`tests/test_usage.py` | `python3 -m unittest discover -s tests -p test_usage.py`。覆盖严格比例、窗口端点、零 Codex、并发去重追加、失败及未知回执透传、JSONL 跨窗基线。 | 1 |
| 3 · 六行交接 | `conflux_handoff.py`、`tests/test_handoff.py` | `python3 -m unittest discover -s tests -p test_handoff.py`。覆盖格式、路径逃逸、读回、并发发布、相同重复和冲突保留。 | 1，共用 CLI 入口 |
| 4 · 协调写保护与按需技能 | `AGENTS.md`、`CLAUDE.md`、`GEMINI.md`、`.agents/skills/dispatch/SKILL.md`、`examples/gemini-before-tool.json`、`tests/test_client_rules.py` | `python3 -m unittest discover -s tests -p test_client_rules.py`。覆盖入口引用、技能触发描述、Gemini 追加示例保留 Orca 条目。 | 1 的派单契约 |
| 5 · 开源与切换验收 | `README.md`、`LICENSE`、`docs/release-checklist.md`、`tests/test_release.py` | `python3 -m unittest discover -s tests`。检查 MIT 文件、`conflux.py` ≤ 200 行、`conflux_handoff.py` ≤ 70 行，合计 ≤ 270 个有效行及发布文件脱敏，执行下列真机清单与切换演练。 | 2、3、4 |

切片 4 手工验收清单：按照 B1 在真机复验各客户端协调写保护及按需技能入口。该清单独立于 `unittest`。

切片 5 以 Orca 1.4.273 为升级对照，复查单次派单、事件与终态、终端保留及回收、已知请求重放、断连 pending 与回执丢失、跨身份、交权围栏、legacy 和 paired server 权限、交接冲突及三端写保护。记录版本、命令和观测结果，审查发布树中的个人路径、密钥、原始日志和会话标识。

切换先保留旧 `~/.agents/skills/to` 原位运行至存量任务结束。新任务用独立 Orca Run 试跑 Conflux，验收通过后停用旧入口，并经操作者确认把旧技能及状态原样归档。回滚时停止新派单、保留已启动 Orca Run，由原 owner 收尾，然后恢复旧入口。旧状态无需导入 Conflux。
