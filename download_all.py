#!/usr/bin/env python3
"""按摄像头分发下载：有云端事件的走事件下载，无事件的走本地识人。在 Lima 虚拟机里跑。

用法: python3 download_all.py <YYYY-MM-DD> <clips_out_dir>
"""
import json, os, subprocess, sys
import ezviz_common as ec

# c7_reel 用系统 python（有 pyyaml 读配置），它内部再调 detenv 的 detect_people（有 onnxruntime）
DETENV = os.path.expanduser("~/detenv/bin/python")

def main():
    date, clips_dir = sys.argv[1], os.path.expanduser(sys.argv[2])
    os.makedirs(clips_dir, exist_ok=True)
    clips = json.load(open(f"clips_{date}.json"))
    by_cam = {}
    for c in clips:
        by_cam.setdefault(c["serial"], []).append(c)
    for cam in ec.cameras():
        serial = cam["serial"]
        name = cam["name"]
        if serial in by_cam and by_cam[serial]:
            print(f"=== {name} {serial}: {len(by_cam[serial])} 个事件片段，按事件下载 ===", flush=True)
            subprocess.run(["python3", "hik_downloader.py", f"clips_{date}.json", clips_dir, serial])
        else:
            print(f"=== {name} {serial}: 无云端事件，走本地识人 ===", flush=True)
            subprocess.run(["python3", "c7_reel.py", serial, date, clips_dir])

if __name__ == "__main__":
    main()
