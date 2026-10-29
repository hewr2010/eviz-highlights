#!/bin/bash
# 诊断摄像头访问问题。在本机 Mac 跑：scripts/diagnose.sh
set -uo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
cd "$HERE"

echo "=== 1. 本机 IP（应在摄像头同网段 192.168.123.x）==="
ifconfig | grep "inet " | grep -vE "127.0.0.1|198.19|10.8" | head -3

echo
echo "=== 2. .secrets.yml 里的摄像头 IP ==="
python3 -c "import ezviz_common as ec; [print(c['name'], c['serial'], c['ip']) for c in ec.cameras()]" 2>&1

echo
echo "=== 3. 逐个测摄像头 8000 端口连通性 ==="
python3 - <<'PY'
import socket, ezviz_common as ec
for c in ec.cameras():
    ip = c["ip"]
    try:
        socket.create_connection((ip, 8000), timeout=3).close()
        print(f"{c['name']} {ip}:8000 通")
    except Exception as e:
        print(f"{c['name']} {ip}:8000 不通 -> {e}")
PY

echo
echo "=== 4. 云端在线状态 + 当前实际 IP ==="
python3 - <<'PY'
import ezviz_common as ec
tok = ec.get_token()
for c in ec.cameras():
    r = ec.api_post("/api/lapp/device/info", {"accessToken": tok, "deviceSerial": c["serial"]})
    d = r.get("data", {})
    print(f"{c['name']} {c['serial']}: 在线={d.get('status')} 云端登记IP={d.get('localAddress')} 配置IP={c['ip']} 一致={d.get('localAddress')==c['ip']}")
PY

echo
echo "=== 5. Lima 虚拟机里测摄像头连通性 ==="
if limactl list -q | grep -qx ezviz; then
  limactl shell ezviz -- bash -c 'for ip in $(python3 -c "import ezviz_common as ec; print(\" \".join(c[\"ip\"] for c in ec.cameras()))" 2>/dev/null); do timeout 3 bash -c "echo > /dev/tcp/$ip/8000" 2>/dev/null && echo "$ip 通" || echo "$ip 不通"; done' 2>&1
else
  echo "虚拟机 ezviz 未运行"
fi
