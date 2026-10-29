#!/bin/bash
# 初始化 Lima 虚拟机（ARM64 Ubuntu）：装 HCNetSDK、ffmpeg、人形检测环境、YOLOv8n 模型。
# 只需运行一次。用法: scripts/setup_vm.sh
set -euo pipefail
VM=ezviz
SDK_REPO="https://codeload.github.com/dmvevents/HCNetSDKV6.1.9.45_ArmLinux64_EN/tar.gz/refs/heads/main"
YOLO_URL="https://huggingface.co/salim4n/yolov8n-detect-onnx/resolve/main/yolov8n-onnx-web/yolov8n.onnx"

echo "==> 确保 lima 已安装"
if ! command -v limactl >/dev/null; then
  brew install lima
fi

echo "==> 创建/启动虚拟机 $VM"
if ! limactl list -q | grep -qx "$VM"; then
  # 下载 Ubuntu ARM64 云镜像（约 945MB，只下一次）
  IMG=/tmp/ubuntu-arm64.img
  if [ ! -f "$IMG" ]; then
    echo "下载 Ubuntu ARM64 镜像..."
    curl -s -C - -o "$IMG" "https://cloud-images.ubuntu.com/releases/resolute/release-20260927/ubuntu-26.04-server-cloudimg-arm64.img"
  fi
  cat > /tmp/ezviz-lima.yaml <<YAML
vmType: vz
arch: aarch64
images:
  - location: $IMG
    arch: aarch64
cpus: 4
memory: 4GiB
disk: 40GiB
containerd:
  system: false
  user: false
YAML
  limactl create --name "$VM" /tmp/ezviz-lima.yaml
fi
limactl start "$VM"
for i in $(seq 1 30); do limactl shell "$VM" -- true 2>/dev/null && break; sleep 2; done

echo "==> 虚拟机内安装依赖（ffmpeg / python 库 / 检测 venv）"
limactl shell "$VM" -- bash -c '
  sudo apt-get update -qq
  sudo apt-get install -y -qq ffmpeg python3-pip python3-venv strace >/dev/null
  python3 -m pip install --quiet pyyaml 2>/dev/null || sudo python3 -m pip install --quiet pyyaml
  [ -d ~/detenv ] || python3 -m venv ~/detenv
  ~/detenv/bin/pip install --quiet --upgrade pip
  ~/detenv/bin/pip install --quiet onnxruntime opencv-python-headless numpy pyyaml
'

echo "==> 下载海康 HCNetSDK（ARM64 Linux 版）"
limactl shell "$VM" -- bash -c "
  [ -f ~/hcnetsdk/MakeAll/libhcnetsdk.so ] || {
    mkdir -p /tmp/sdk && curl -sL --max-time 180 -o /tmp/sdk/sdk.tar.gz '$SDK_REPO'
    mkdir -p ~/hcnetsdk && tar xzf /tmp/sdk.tar.gz -C ~/hcnetsdk --strip-components=1
    rm -rf /tmp/sdk
  }
  ls ~/hcnetsdk/MakeAll/libhcnetsdk.so
"

echo "==> 下载 YOLOv8n 人形检测模型"
limactl shell "$VM" -- bash -c "
  mkdir -p ~/models ~/work ~/footage
  [ -f ~/models/yolov8n.onnx ] || curl -sL --max-time 180 -o ~/models/yolov8n.onnx '$YOLO_URL'
  ls -la ~/models/yolov8n.onnx
"

echo "==> 完成。验证: limactl shell $VM -- uname -m"
