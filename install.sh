#!/bin/sh
set -eu

dry_run=false
skip_orca=false
for arg in "$@"; do
  case "$arg" in
    --dry-run) dry_run=true ;;
    --skip-orca-check) skip_orca=true ;;
    *) echo "未知选项: $arg" >&2; exit 2 ;;
  esac
done
root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
command -v python3 >/dev/null 2>&1 && python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))' || { echo '需要 Python 3.10 或更新版本。' >&2; exit 1; }
if ! $skip_orca && ! command -v orca >/dev/null 2>&1; then
  echo '未找到 Orca CLI，请安装并加入 PATH；临时测试可使用 --skip-orca-check。' >&2
  exit 1
fi
check_link() {
  dest=$1 target=$2
  if [ -L "$dest" ]; then
    [ "$(readlink "$dest")" = "$target" ] || { echo "目标已存在且指向其他位置: $dest" >&2; exit 1; }
  elif [ -e "$dest" ]; then
    echo "目标已存在: $dest" >&2; exit 1
  fi
}
command_link="$HOME/.local/bin/conflux"
skill_link="$HOME/.agents/skills/conflux-dispatch"
check_link "$command_link" "$root/bin/conflux"
check_link "$skill_link" "$root/.agents/skills/dispatch"
if $dry_run; then
  echo '试运行：检查通过，不写入文件。'
else
  mkdir -p "$HOME/.config/conflux" "$HOME/.local/state/conflux" "$HOME/.local/bin" "$HOME/.agents/skills"
  policy="$HOME/.config/conflux/policy.json"
  if [ ! -e "$policy" ] && [ ! -L "$policy" ]; then
    (set -C; sed 's/"example"/"default"/g' "$root/policy.json" > "$policy")
  fi
  [ -L "$command_link" ] || ln -s "$root/bin/conflux" "$command_link"
  [ -L "$skill_link" ] || ln -s "$root/.agents/skills/dispatch" "$skill_link"
  echo '安装完成。'
fi
case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) echo 'export PATH="$HOME/.local/bin:$PATH"' ;; esac
echo '验证命令: conflux usage'
