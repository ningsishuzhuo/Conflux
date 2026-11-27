# Conflux v0.3.1

Conflux 为 [Orca](https://github.com/stablyai/orca) 检查派单策略，记录成功派单，并提供交接文件的发布和核验。Orca 和客户端负责执行、恢复和权限管理。
先和协调会话里的 AI 商量方案。你明确冻结契约后，AI 再按分工开工。里程碑验收通过后，发布并核验交接单，切到新会话按 `Next` 续跑。

状态：Alpha，接口可能调整。

## 快速安装

macOS、Linux 和 WSL 需要 Python 3.10 或更新版本，以及已加入 PATH 的 Orca CLI。

```sh
git clone https://github.com/ningsishuzhuo/Conflux.git && cd Conflux
./install.sh --dry-run  # 可选，预览安装
./install.sh
```

默认路由配置在 `~/.config/conflux/policy.json`。安装脚本从仓库示例生成默认策略，保留已有配置。命令和两个技能通过软链接指向仓库，请保留克隆目录。

如果 `~/.local/bin` 还在 PATH 之外，可将下面这行加入 `~/.zshrc` 或 `~/.bashrc` 后重开终端，再用 `conflux usage` 检查安装。

```sh
export PATH="$HOME/.local/bin:$PATH"
```

<details>
<summary>原生 Windows</summary>

原生 Windows 已通过 CI 验证，真实 Orca 会话尚待实测。在仓库根目录打开 PowerShell，使用已安装的 Python：

```powershell
New-Item -ItemType Directory -Force "$HOME/.config/conflux", "$HOME/.local/state/conflux" | Out-Null
$policy = "$HOME/.config/conflux/policy.json"
if (!(Test-Path $policy)) { [IO.File]::WriteAllText($policy, (Get-Content -Raw policy.json).Replace('"example"', '"default"'), [Text.UTF8Encoding]::new($false)) }
$env:PATH = "$(Join-Path (Get-Location) 'bin');$env:PATH"
conflux usage
```

这里设置的 PATH 只对当前 PowerShell 会话有效。

</details>

## 第一次派单与 CLI 速览

在 Orca 聊天会话中对 AI 说「请用 Codex 运行本项目的测试并报告结果」。AI 可用下面的命令派单，默认策略提供示例中的路由。

```sh
conflux dispatch --agent codex --profile default --model default --cwd . -- --spec "运行单测并报告失败项" --worktree current --environment local --json
```

- `dispatch` 检查策略后调用 Orca。`--` 后是 Orca 参数。终端会话中，若 `$ORCA_SESSION` 非空，在 `--` 后加上 `--from "$ORCA_SESSION"`。聊天会话省略 `--from`。
- `conflux usage` 查看最近 5 小时的成功派单统计。实际订阅配额以服务商显示为准。
- `conflux handoff publish --dir handoffs --file handoff.md` 把准备好的交接文件发布到已有目录，随后用相同参数运行 `conflux handoff verify` 核验。

交接格式有误时，命令会说明原因并给出模板。可运行 `conflux handoff --help`，完整参数、六行模板和退出码见 [CLI 契约](docs/cli-contract.md)。

## 角色与核心边界

| 角色 | 分工 |
| --- | --- |
| AGY（Antigravity） | 轻量协调。联网检索、扫仓、读两个及以上业务文件或运行业务命令，首步交 DSH。 |
| DSH | 做只读调研和客观验收。冻结后可在干净工作区做小范围机械改动，并附 `git status`。只试一次，证据不足或失败就转 Codex。 |
| Codex | 负责主要实施，包括设计、多文件改造、文案、PPT 和科研。 |
| Claude | 用于定点审查或重大裁决。默认拒绝。用户本轮明确点名且意图清晰时免二次确认，传 `--authorize-paid` 记账。其余情况须经 gate 确认。 |

- 用户明示冻结前，协调者保持零状态改动。
- 涉及 `git push`、PR/Issue（含 `Refs` / `Closes`）、发版等外部写操作，冻结草案须写明唯一默认值与执行归属。所有未决项须在冻结前拍板。已冻结的默认值仅在参数或目标变化时重新审批。
- 冻结草案要写明是否安排独立语义审查。安排时写审查人，省略时写原因。

## 两个按需技能

- [`conflux-dispatch`](.agents/skills/dispatch/SKILL.md) 用于单次派单、查用量或交接。
- [`conflux-autonomy`](.agents/skills/autonomy/SKILL.md) 用于从需求打磨推进到冻结实施和验收。实施与验收参见 [审查清单](.agents/skills/autonomy/references/review-checklists.md)，异常和交接处理参见 [边界情况](.agents/skills/autonomy/references/edge-cases.md)。

## 延伸文档

- [协作规则与写保护](AGENTS.md)
- [CLI 契约](docs/cli-contract.md) · [设计说明](docs/design.md) · [发布清单](docs/release-checklist.md)
- [Gemini BeforeTool 配置示例](examples/gemini-before-tool.json)

## 测试

```sh
python3 -m unittest discover -s tests -v
```

原生 Windows 使用 `python -m unittest discover -s tests -v`。

## 许可

[MIT License](LICENSE) · [Issue](https://github.com/ningsishuzhuo/Conflux/issues)
