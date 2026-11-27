---
name: conflux-autonomy
description: "按契约推进代码、文案、PPT 或科研协作时按需加载。"
---

# 自主推进

0. 预检：读 `conflux-dispatch`、`orca skills get orchestration`、`~/.config/conflux/policy.json`，运行 `conflux usage`。
1. 打磨期不催冻结，不改文件。用户明确敲定或开干后冻结四项：任务 DAG（含依赖与工作区）、协调者持有的验收标准、执行安全红线、按 AGENTS.md 执行 Claude 点名免二次确认策略。
2. 强动作门以本 Skill 实际加载目录为基准，读取同级 references：
   - 派发实施或验收单前，必读 `references/review-checklists.md` 对应场景段和通用段。
   - 遇 409/429/502 重试、Claude gate、打回收口细则、handoff/release 异常前，必读 `references/edge-cases.md` 对应段。
   - 读取成功后才继续。冷层缺失、不可读或找不到对应段落时，停止相关动作并报告。
3. 实施单要求交付前自检与实测。客观初筛交 DSH，使用同一产物快照和冻结验收标准。按实测输出与本次 Task/Dispatch ID 对应的 `worker_done` 验收，缺证据标未验证。
4. 零看门狗：禁止 schedule 定时检查及阻塞轮询。派单后零后台任务，立即结束回合，靠 Orca 原生推唤醒接收 `worker_done`、`ask`、`escalation`。仅在用户唤回或会话恢复时做一次 `inbox` + `worker-list` 终态对账，按 `dispatchId`/`messageId` 去重。
5. 失败分级：纯机械交 DSH 清理；逻辑硬伤先原 Codex 修一次，失败集合严格缩小且无新增失败才换全新 Codex 再修一次。触及红线、超出返工边界或无收敛时停机 `gate-create`。
6. 通过后释放一次性终端，按契约收尾并发布及核验 handoff，报告实测证据和可复制的续跑指令。
