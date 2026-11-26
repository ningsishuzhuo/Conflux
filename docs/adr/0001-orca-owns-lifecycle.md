# ADR 0001 · Orca 独占生命周期

状态：已决定。

Orca 管理 Run、Task、Worker、Dispatch、完成事件、接管与资源回收。Conflux 仅记录派单准入和用量所需事实，禁止镜像生命周期或终态。

已知请求 ID 使用原身份和原参数重放。缺 ID 或查不到时停止重发，交原 owner 核实。同 runtime 普通 Run 使用 `run-use` 并核对 owner 与 generation，跨 runtime 固定原 owner。

交接采用六行 Markdown。同目录临时文件经 fsync 后用 `os.link` 防覆盖，再读回核验。

本机普通 Run 已验证。远端、真实断连与 legacy 纳入升级回归。
