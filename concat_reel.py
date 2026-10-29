#!/usr/bin/env python3
"""把片段目录里的 mp4 按时间顺序拼成当日集锦。在 Lima 虚拟机里跑。

用法: python3 concat_reel.py <clips_dir> <out.mp4>
片段文件名形如 <serial>_<HHMMSS>.mp4，按 HHMMSS 跨摄像头时间排序。
"""
import os, re, subprocess, sys

def main():
    clips_dir, out = sys.argv[1], sys.argv[2]
    files = [f for f in os.listdir(clips_dir) if f.endswith(".mp4")]
    def ts(f):
        m = re.search(r"_(\d{6})\.mp4$", f)
        return m.group(1) if m else f
    files.sort(key=ts)
    if not files:
        print("没有可拼接的片段"); sys.exit(1)
    lst = os.path.join(clips_dir, "_list.txt")
    with open(lst, "w") as fp:
        for f in files:
            fp.write(f"file '{os.path.join(clips_dir, f)}'\n")
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", lst, "-c", "copy", "-movflags", "+faststart", out], check=True)
    os.remove(lst)
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=noprint_wrappers=1:nokey=1", out], capture_output=True, text=True)
    print(f"集锦 {out} 时长 {r.stdout.strip()}s 片段数 {len(files)}")

if __name__ == "__main__":
    main()
