# Conflux CLI 契约

## 策略文件

`policy.json` 的结构如下。

```text
{"routes": [{"agent": str, "profile": str, "model": str,
             "billing": "subscription"|"low_cost"|"paid", "keep_open_default": bool}]}
```

精确匹配 `(agent, profile, model)` 元组。重复元组、重复 JSON 键、缺失或额外字段、类型错误、空白路由字段和非法计费值均拒绝加载整个策略表。

## dispatch

```text
python3 conflux.py dispatch --policy <path> --agent <agent> --profile <profile>
    --model <model> --cwd <directory> [--authorize-paid <reason>]
    [--orca-bin <path>] [--ledger <path>] [--now <iso8601>] -- [Orca 原生参数...]
```

- `--orca-bin` 默认 `orca`。`--cwd` 必须为现有目录，并作为 Orca 子进程的工作目录。
- 付费路由要求非空白理由。未知路由、非法策略、非法工作目录或透传冲突以状态码 2 拒绝，且不调用 Orca。
- 执行 `orca orchestration worker-start --agent <agent> --model <model>`，随后连接原生参数，保持其顺序和内容。匹配到 `model: default` 路由时，省略 Orca 的 `--model` 参数以跟随客户端默认模型。切片 1 的 `profile` 是本地策略标签，由调用者提供。Orca 的实际配置和工作区选择由 Orca 环境及原生参数决定。
- 原生参数禁止出现 `--agent`、`--model`、`--profile`、`--cwd`，包含 `--flag=val` 形式。匹配路由的 `keep_open_default` 为真且参数未含 `--keep-open` 时，在末尾追加一次。
- 透传 Orca 的 stdout、stderr 和退出码。启用账本时可传原生 `--json` 以获取 JSON 回执。只有退出码为 0 且顶层 `dispatchId` 或 `result.dispatchId` 为非空白字符串时才追加，账本全历史按 ID 去重。成功派单但缺少可解析的 ID 时向 stderr 告警。
- Antigravity 派单必须传入 `--ledger`。缺少该参数时退出码为 2，且不会调用 Orca。调用前只读检查 `now - 5h < ts <= now` 内去重派单。Antigravity 仅在 `2 * (agy_calls + 1) < codex_calls` 时放行，否则返回 2。其他代理照常派单，DSH、Claude 等只计审计。调用结束后才获取同目录 `<账本文件名>.lock` 的排他锁。
- `--now` 默认当前 UTC，可传 ISO 8601 固定时钟。账本不存在时视为空。不可解析的账本行会跳过并向 stderr 告警。账本追加失败时将原因写到 stderr，保留 Orca 退出码。

## usage

```text
python3 conflux.py usage --ledger <path> [--codex-jsonl <path> ...] [--agy-brain-dir <path>] [--now <iso8601>]
```

- 只读输出一个 JSON 对象，含 `window_hours`、`agy_calls`、`codex_calls`、`other_calls`、`agy_allowed_next` 和 `metric_kind`（`conflux_dispatch_proxy`）。
- `paid_calls` 统计 `billing == "paid"` 的派单，仅用于观测。 `total_dispatches` 统计全部派单。窗口为 `now - 5h < ts <= now`，按 dispatch ID 去重，重复 ID 取窗口内账本最后一条记录。
- 指定 `--agy-brain-dir` 后扫描 `<dir>/*/.system_generated/logs/transcript.jsonl`，对 `created_at` 落在同一窗口的 `PLANNER_RESPONSE` 计量，跳过损坏行与非法时间。实时查询跳过 mtime 早于窗口的文件，固定 `--now` 查询读取历史文件。
- `agy_coordinator` 包含整数 `sessions`（活跃会话数）、`turns`、`input_tokens`、`cache_read_tokens`、`output_tokens`、`total_tokens`（三类 token 之和）和 `max_turn_context_tokens`（各活跃会话时间最新轮的 input + cache read 最大值）。无活跃轮或指定目录不存在时全为 0。
- 直接调用 Python 入口且省略参数时省略 `agy_coordinator`。Unix 与 Windows 安装入口在无显式参数时尝试 `CONFLUX_AGY_BRAIN_DIR`，未设置或为空时尝试用户目录下的 `.gemini/antigravity-cli/brain`，仅目录存在时自动启用。
- 提供 Codex 会话 JSONL 时增加 `codex_tokens` 数组。同一路径只统计一次，每项含 `path` 和 `status`，成功时含 `total_tokens`。累计值使用窗口起点或之前的最后一条累计记录作基线，单独出现的 `last_token_usage` 按时间戳和总量去重。文件内最早事件晚于窗口起点时按基线 0 计算。若窗口起点或之前有事件、但没有 token_count 记录，窗口内的 token_count 返回 `missing_baseline`。缺基线或累计量回退时分别返回 `missing_baseline`、`counter_reset`。

## handoff（切片 3）

`python3 conflux.py handoff publish|verify --dir <dir> --file <path>` 使用 UTF-8 六行 Markdown，字段固定如下。每个字段值为单行非空文本，行以 LF 结尾。`--file -` 从标准输入读取。

```markdown
# <Title>
ID: <ID>
Run: <Run>
Task: <Task>
Dispatch: <Dispatch>
Next: <Next>
```

ID 必须完全匹配 `^[A-Za-z0-9._-]+$`且不能为 `.` 或 `..`。目标为 `<dir>/<ID>.md`，以同目录原子发布并按字节核验内容。发布结果为 `0`（created）、`10`（duplicate）、`11`（conflict）、`2`（invalid）。核验返回 `0` 表示匹配，`11` 表示内容冲突，`2` 表示输入无效或文件缺失。
