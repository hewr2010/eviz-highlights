# 萤石摄像头每日"有人画面"集锦

每天自动把家里萤石摄像头一天里"有人活动"的片段剪成一段集锦，上传百度网盘并 Bark 通知，替代人肉翻 App 回放。

- **零费用**：只用萤石开放平台免费 API + 局域网直连下载，不开云存储、不买企业版
- **走局域网**：录像从摄像头 SD 卡经家里局域网直接拉到本机
- **全自动**：每天早 6 点（昨天）+ 晚 6 点（当天）各跑一次，传网盘 + Bark 通知

## 原理

```
萤石云 API（免费）拿到每台摄像头的人形/移动报警时间点
  → 合并相邻报警成片段清单
  → 本机 Lima 虚拟机里跑海康 HCNetSDK，局域网直连摄像头 8000 端口下载这些片段
  → 对没有云端事件的摄像头，改走"下载全天录像 + YOLOv8n 本地人形检测"
  → ffmpeg 按时间顺序拼成当日集锦 highlights_<date>.mp4
  → bypy 传百度网盘 → 删本地 → Bark 通知
```

## 目录结构

```
eviz-highlights/
├── daily.sh              # 一键流水线入口（本机 Mac 跑）
├── ezviz_common.py       # 共享：读 .secrets.yml、取 token、查摄像头
├── fetch_events.py       # 拉报警事件、合并片段清单（本机）
├── download_all.py       # 按摄像头分发：有事件走下载，无事件走本地识人（虚拟机）
├── hik_downloader.py     # 海康 HCNetSDK 按时间段下载片段（虚拟机）
├── grab_day.py           # 下载全天录像（虚拟机）
├── detect_people.py      # YOLOv8n 本地人形检测（虚拟机）
├── c7_reel.py            # 无事件摄像头：全天录像→检测→剪片段（虚拟机）
├── concat_reel.py        # 按时间拼接当日集锦（虚拟机）
├── .secrets.yml          # 敏感配置（gitignore，不进 git）
├── .secrets.example.yml  # 配置模板
├── scripts/
│   ├── setup_vm.sh       # 初始化 Lima 虚拟机（HCNetSDK/检测环境/模型）
│   └── install_launchd.sh# 安装/卸载每天两次的定时任务
└── launchd/
    ├── com.ezviz.daily.am.plist  # 早 6 点：昨天集锦
    └── com.ezviz.daily.pm.plist  # 晚 6 点：当天集锦
```

## 一次性安装

```bash
# 1. 装依赖（本机 Mac）：Lima、ffmpeg、bypy、pyyaml
brew install lima ffmpeg
uv tool install bypy          # 或 pip install bypy
python3 -m pip install pyyaml

# 2. 初始化 Lima 虚拟机（下载 Ubuntu 镜像 + 海康 SDK + 检测模型，约 10~20 分钟）
scripts/setup_vm.sh

# 3. 配置敏感信息
cp .secrets.example.yml .secrets.yml
#   编辑 .secrets.yml：填萤石 AppKey/AppSecret、Bark key、各摄像头序列号/IP/验证码

# 4. bypy 授权（百度网盘，浏览器扫码一次）
bypy quota        # 按提示打开链接授权

# 5. 手动跑一次验证（处理昨天）
./daily.sh

# 6. 装定时任务（早 6 点昨天、晚 6 点当天）
scripts/install_launchd.sh install
```

## 每天使用

```bash
./daily.sh              # 处理昨天
./daily.sh today        # 处理今天
./daily.sh 2026-10-27   # 处理指定日期
```

集锦生成后自动：传百度网盘（`netdisk_dir` 指定目录）→ 删本地 → Bark 通知。

## 敏感信息管理

- 所有密钥/验证码只在 `.secrets.yml`（已 gitignore），代码里零硬编码
- `.secrets.example.yml` 是模板，可复制填写
- bypy 的网盘 token 在 `~/.bypy/bypy.json`（bypy 标准位置，不在仓库里）

## 常见问题

**某台摄像头一直 0 事件？**
基本是它的人形/移动侦测没开或布防计划不是全天。去萤石 App → 设备 → 设置 → 侦测报警 打开。开了之后它会自动走事件下载（更快更稳）。没开也不慌，会自动走本地识人兜底（只是 SD 卡循环覆盖会导致能剪的时长不稳定）。

**集锦太长/太短？**
`fetch_events.py` 支持环境变量：`MERGE_GAP_MS`（合并间隔）、`PRE_PAD_MS`/`POST_PAD_MS`（前后预留）、`MAX_CLIP_MS`（单段上限）。例：`MAX_CLIP_MS=30000 ./daily.sh` 把每段截到 30s。

**虚拟机/网络？**
下载和检测都在 Lima 虚拟机里跑，虚拟机通过 NAT 共享本机网络，能直接访问局域网摄像头。`limactl shell ezviz` 可进虚拟机调试。

**换电脑/重装？**
`git clone` 本仓库 → `scripts/setup_vm.sh` → 填 `.secrets.yml` → `bypy quota` 授权 → `install_launchd.sh install`。
