#!/bin/bash
# 安装/卸载每天两次的定时任务（早 6 点昨天、晚 6 点当天）。
# 用法: scripts/install_launchd.sh [install|uninstall]
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
ACTION="${1:-install}"

case "$ACTION" in
  install)
    mkdir -p "$HOME/Library/LaunchAgents"
    for f in "$HERE"/launchd/com.ezviz.daily.*.plist; do
      cp "$f" "$HOME/Library/LaunchAgents/"
      launchctl unload "$HOME/Library/LaunchAgents/$(basename "$f")" 2>/dev/null || true
      launchctl load "$HOME/Library/LaunchAgents/$(basename "$f")"
      echo "已加载 $(basename "$f")"
    done
    echo "当前定时任务:"
    launchctl list | grep com.ezviz || true
    ;;
  uninstall)
    for f in "$HOME/Library/LaunchAgents"/com.ezviz.daily.*.plist; do
      [ -e "$f" ] || continue
      launchctl unload "$f" 2>/dev/null || true
      rm -f "$f"
      echo "已卸载 $(basename "$f")"
    done
    ;;
  *)
    echo "用法: $0 [install|uninstall]"; exit 1;;
esac
