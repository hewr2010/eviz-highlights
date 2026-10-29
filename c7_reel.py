#!/usr/bin/env python3
"""无云端事件摄像头的本地人形集锦：下载全天录像 → 检测人形 → 剪出片段。在 Lima 虚拟机里跑。

用法: python3 c7_reel.py <serial> <YYYY-MM-DD> <clips_out_dir>
  从 .secrets.yml 读 IP/验证码。全天录像先由 grab_day.py 下到 ~/footage/<serial>_<date>*.ps，
  若不存在则自动先下载。产出的人形片段写入 clips_out_dir/<serial>_<HHMMSS>.mp4，供 daily.sh 统一拼接。
"""
import glob, json, os, subprocess, sys, time
import ezviz_common as ec

def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)

def ps_to_mp4(ps, mp4):
    r = sh(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-fflags", "+genpts", "-i", ps, "-c", "copy", mp4])
    return r.returncode == 0 and os.path.exists(mp4) and os.path.getsize(mp4) > 10000

def dur(mp4):
    r = sh(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", mp4])
    try:
        return float(r.stdout.strip())
    except Exception:
        return 0.0

def main():
    serial, date, out_dir = sys.argv[1:4]
    cam = ec.camera_by_serial(serial)
    if not cam:
        print(f"cameras 里找不到 {serial}"); sys.exit(1)
    os.makedirs(out_dir, exist_ok=True)
    work = os.path.expanduser(f"~/work/{serial}_{date}")
    os.makedirs(work, exist_ok=True)
    # 1. 找全天录像片段（.ps, _1.ps, _2.ps ...），没有就先下载
    segs = sorted(glob.glob(os.path.expanduser(f"~/footage/{serial}_{date}.ps")) +
                  glob.glob(os.path.expanduser(f"~/footage/{serial}_{date}_*.ps")))
    if not segs:
        print(f"未找到 {serial} {date} 录像，先下载", flush=True)
        base = os.path.expanduser(f"~/footage/{serial}_{date}.ps")
        r = sh([os.path.expanduser("~/detenv/bin/python"), os.path.expanduser("~/grab_day.py"), serial, date, base, "sub"])
        segs = sorted(glob.glob(os.path.expanduser(f"~/footage/{serial}_{date}.ps")) +
                      glob.glob(os.path.expanduser(f"~/footage/{serial}_{date}_*.ps")))
    if not segs:
        print(f"{serial} {date} 无录像可下载（可能 SD 卡已被覆盖）"); return
    # 2. 逐段转 mp4 + 检测 + 剪人形片段
    y, m, d = map(int, date.split("-"))
    day0 = time.mktime((y, m, d, 0, 0, 0, 0, 0, -1))
    offset = 0.0  # 已处理片段的累计时长（秒）
    total_clips = 0
    for si, ps in enumerate(segs):
        mp4 = f"{work}/seg{si}.mp4"
        if not os.path.exists(mp4):
            if not ps_to_mp4(ps, mp4):
                print(f"seg{si} 转码失败，跳过", flush=True); continue
        # 检测人形
        det = sh([os.path.expanduser("~/detenv/bin/python"), os.path.expanduser("~/detect_people.py"), mp4, "5", "0.35"])
        pj = mp4 + ".people.json"
        if not os.path.exists(pj):
            print(f"seg{si} 检测失败", flush=True)
            offset += dur(mp4); continue
        segs_info = json.load(open(pj))["segments"]
        print(f"seg{si}: {len(segs_info)} 个人形时段", flush=True)
        for ci, s in enumerate(segs_info):
            abs_st = day0 + offset + s["start"]
            abs_en = day0 + offset + s["end"] + 10
            hhmmss = time.strftime("%H%M%S", time.localtime(abs_st))
            clip = f"{out_dir}/{serial}_{hhmmss}.mp4"
            st_in_seg = max(0, s["start"] - 5)
            en_in_seg = s["end"] + 10
            sh(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", str(st_in_seg), "-to", str(en_in_seg),
                "-i", mp4, "-c", "copy", "-movflags", "+faststart", clip])
            if os.path.exists(clip) and os.path.getsize(clip) > 5000:
                total_clips += 1
        offset += dur(mp4)
    print(f"{serial} {date}: 共产出 {total_clips} 个人形片段", flush=True)

if __name__ == "__main__":
    main()
