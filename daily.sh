#!/bin/bash
# 每日"有人画面"集锦一键流水线（在本机 Mac 运行）。
#
# 用法: ./daily.sh [YYYY-MM-DD]   (默认昨天)
# 流程: 拉报警事件 → Lima 虚拟机里 HCNetSDK 下载片段（无事件的摄像头走本地识人）
#       → 拼接集锦 → bypy 传百度网盘 → 删本地 → Bark 通知
#
# 敏感信息全部从 .secrets.yml 读（ezviz_common），本脚本和代码里都没有硬编码密钥。
set -euo pipefail

# bypy 可能装在 ~/.local/bin（uv tool），确保在 PATH 里
export PATH="$HOME/.local/bin:/opt/homebrew/bin:$PATH"

if [ "${1:-}" = "today" ]; then
  DATE="$(date +%F)"          # 当天（傍晚 6 点用）
elif [ -n "${1:-}" ]; then
  DATE="$1"                   # 指定日期
else
  DATE="$(date -v-1d +%F)"    # 默认昨天（早上 6 点用）
fi
HERE="$(cd "$(dirname "$0")" && pwd)"
VM=ezviz
VCLIPS="\$HOME/clips_${DATE}"            # 虚拟机内片段目录（\$HOME 在虚拟机展开）
VREEL="\$HOME/highlights_${DATE}.mp4"    # 虚拟机内集锦路径

cd "$HERE"

# 从 .secrets.yml 读 bark_key / netdisk_dir
eval "$(python3 -c "import ezviz_common as ec; print('BARK_KEY='+ec.bark_key()); print('NETDISK_DIR='+ec.netdisk_dir())")"

echo "=== [1/6] 确保虚拟机运行 ==="
if ! limactl list -q | grep -qx "$VM"; then
  echo "虚拟机 $VM 不存在，请先运行 scripts/setup_vm.sh 初始化"; exit 1
fi
limactl start "$VM" >/dev/null 2>&1 || true
for i in $(seq 1 30); do
  limactl shell "$VM" -- true 2>/dev/null && break
  sleep 2
done

echo "=== [2/6] 拉取 $DATE 报警事件 ==="
python3 fetch_events.py "$DATE"

echo "=== [3/6] 同步代码与配置到虚拟机 ==="
limactl copy "$HERE"/*.py "$HERE/.secrets.yml" "$HERE/clips_${DATE}.json" "$VM":~/ >/dev/null

echo "=== [4/6] 下载/检测片段 ==="
limactl shell "$VM" -- bash -c "
  export LD_LIBRARY_PATH=\$HOME/hcnetsdk/MakeAll
  export SDK_DIR=\$HOME/hcnetsdk/MakeAll
  export EZVIZ_SECRETS=\$HOME/.secrets.yml
  rm -rf $VCLIPS && mkdir -p $VCLIPS
  python3 download_all.py '${DATE}' '$VCLIPS'
"

echo "=== [5/6] 拼接集锦 ==="
limactl shell "$VM" -- bash -c "
  export EZVIZ_SECRETS=\$HOME/.secrets.yml
  python3 concat_reel.py '$VCLIPS' '$VREEL'
"

echo "=== [6/6] 上传网盘 + 清理 + 通知 ==="
TMP_REEL="$(mktemp -t highlights_${DATE}).mp4"
if limactl shell "$VM" -- bash -c "test -f $VREEL" 2>/dev/null; then
  limactl copy "$VM:highlights_${DATE}.mp4" "$TMP_REEL" >/dev/null
  # 上传百度网盘（-s 2GB 规避分片授权问题）
  bypy -s 2GB upload "$TMP_REEL" "${NETDISK_DIR}/" >/dev/null 2>&1 && UP_OK=1 || UP_OK=0
  # 清理虚拟机中间产物
  limactl shell "$VM" -- bash -c "rm -rf $VCLIPS $VREEL" >/dev/null 2>&1 || true
  if [ "$UP_OK" = "1" ]; then
    rm -f "$TMP_REEL"
    MSG="✅ ${DATE} 集锦已生成并上传网盘（${NETDISK_DIR}/highlights_${DATE}.mp4）"
  else
    MSG="⚠️ ${DATE} 集锦已生成但网盘上传失败，暂存本地: $TMP_REEL"
  fi
else
  MSG="❌ ${DATE} 没有生成集锦（可能都没有侦测到人或录像被覆盖）"
fi
# Bark 通知
if [ -n "$BARK_KEY" ]; then
  curl -s --max-time 15 "https://api.day.app/${BARK_KEY}/ezviz/$(python3 -c "import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1]))" "$MSG")?group=ezviz" >/dev/null || true
fi
echo "$MSG"
