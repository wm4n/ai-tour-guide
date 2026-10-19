#!/usr/bin/env bash
# 在 iOS 模擬器上播放 GPX 路線（模擬走路），供 App 端到端測試。
# 用法：scripts/play-gpx.sh [--speed 公尺/秒] [--device UDID|booted] [--dry-run] [GPX 檔]
#   預設：--speed 1.4（約 36 分鐘走完大稻埕到艋舺）、--device booted、scripts/gpx/dadaocheng-to-bangka.gpx
# 停止：xcrun simctl location booted clear
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
speed=1.4
device=booted
dry_run=0
gpx="$here/gpx/dadaocheng-to-bangka.gpx"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --speed) speed="$2"; shift 2 ;;
    --device) device="$2"; shift 2 ;;
    --dry-run) dry_run=1; shift ;;
    -h|--help) sed -n '2,6p' "$0"; exit 0 ;;
    *) gpx="$1"; shift ;;
  esac
done

[[ -f "$gpx" ]] || { echo "找不到 GPX：$gpx" >&2; exit 1; }

waypoints="$(python3 -I - "$gpx" <<'PY'
import sys
import xml.etree.ElementTree as ET

ns = {"g": "http://www.topografix.com/GPX/1/1"}
root = ET.parse(sys.argv[1]).getroot()
points = root.findall(".//g:trkpt", ns) or root.findall(".//g:rtept", ns) or root.findall(".//g:wpt", ns)
for p in points:
    print(f"{p.attrib['lat']},{p.attrib['lon']}")
PY
)"

count="$(printf '%s\n' "$waypoints" | wc -l | tr -d ' ')"
[[ "$count" -ge 2 ]] || { echo "GPX 至少要有兩個點（目前 $count）" >&2; exit 1; }
echo "路線：$(basename "$gpx")，$count 個點，速度 ${speed} 公尺/秒，裝置 $device"
[[ "$dry_run" -eq 1 ]] && { echo "（dry-run，不播放）"; exit 0; }

printf '%s\n' "$waypoints" | xcrun simctl location "$device" start --speed="$speed" --distance=5 -
echo "開始播放；停止請執行：xcrun simctl location $device clear"
