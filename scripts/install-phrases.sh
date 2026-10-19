#!/usr/bin/env bash
# 把主機上挑好、裁好的固定短句複製進 App 的本機資源資料夾（被 git 忽略，不會入庫）。
# 用法：scripts/install-phrases.sh [來源資料夾，預設 ~/.buddy-host/out/phrases-final]
set -euo pipefail

src="${1:-$HOME/.buddy-host/out/phrases-final}"
dst="$(cd "$(dirname "$0")/.." && pwd)/app/assets/phrases"
mkdir -p "$dst"

count=0
for n in 1 2 3 4 6 7; do
  if [[ -f "$src/$n.wav" ]]; then
    cp "$src/$n.wav" "$dst/$n.wav"
    count=$((count + 1))
  else
    echo "找不到 $src/$n.wav（略過）" >&2
  fi
done
echo "已複製 $count 句到 $dst"
