#!/usr/bin/env python3
"""用海康 HCNetSDK 从摄像头 SD 卡按时间段下载录像片段。在 Lima 虚拟机里跑。

用法: python3 hik_downloader.py <clips.json> <out_dir> <serial>
  clips.json 由 fetch_events.py 生成；serial 决定连哪台（IP/验证码从 .secrets.yml 读）。
环境变量: SDK_DIR 指向 HCNetSDK 库目录（含 libhcnetsdk.so 与 HCNetSDKCom/）。
"""
import ctypes, hashlib, json, os, subprocess, sys, time
from ctypes import CDLL, Structure, byref, c_uint, c_byte, c_char_p
import ezviz_common as ec

class NET_DVR_TIME(Structure):
    _fields_ = [("dwYear", c_uint), ("dwMonth", c_uint), ("dwDay", c_uint),
                ("dwHour", c_uint), ("dwMinute", c_uint), ("dwSecond", c_uint)]
class NET_DVR_PLAYCOND(Structure):
    _fields_ = [("dwChannel", c_uint), ("struStartTime", NET_DVR_TIME), ("struStopTime", NET_DVR_TIME),
                ("byDrawFrame", c_byte), ("byStreamType", c_byte), ("byStreamID", c_byte*32), ("byCourseFile", c_byte),
                ("byDownload", c_byte), ("byOptimalStreamType", c_byte), ("byVODFileType", c_byte), ("byRes", c_byte*26)]

def sdk_pwd(code):
    # 萤石消费级摄像头 SDK 登录密码：md5(验证码) 十六进制中段 16 位（小写）
    return hashlib.md5(code.encode()).hexdigest()[8:24].lower()

class Downloader:
    def __init__(self, sdk_dir, ip, code):
        self.sdk = CDLL(f"{sdk_dir}/libhcnetsdk.so")
        # SDK 会在该路径下再找 HCNetSDKCom/ 子目录，所以传父目录
        self.sdk.NET_DVR_SetSDKInitCfg(2, c_char_p(sdk_dir.encode()))
        if not self.sdk.NET_DVR_Init():
            raise RuntimeError(f"NET_DVR_Init failed err={self.sdk.NET_DVR_GetLastError()}")
        self.sdk.NET_DVR_SetConnectTime(5000, 1)
        info = ctypes.create_string_buffer(248)
        self.uid = self.sdk.NET_DVR_Login_V30(ip.encode(), 8000, b"EZ_LOCAL_USER",
                                              sdk_pwd(code).encode(), byref(info))
        if self.uid < 0:
            raise RuntimeError(f"登录失败 err={self.sdk.NET_DVR_GetLastError()}（检查验证码）")

    def download(self, start_ms, end_ms, out_ps, channel=1):
        st = time.localtime(start_ms/1000); en = time.localtime(end_ms/1000)
        cond = NET_DVR_PLAYCOND()
        cond.dwChannel = channel
        cond.struStartTime = NET_DVR_TIME(st.tm_year, st.tm_mon, st.tm_mday, st.tm_hour, st.tm_min, st.tm_sec)
        cond.struStopTime = NET_DVR_TIME(en.tm_year, en.tm_mon, en.tm_mday, en.tm_hour, en.tm_min, en.tm_sec)
        cond.byDownload = 1
        cond.byVODFileType = 0
        for attempt in range(3):
            dh = self.sdk.NET_DVR_GetFileByTime_V40(self.uid, out_ps.encode(), byref(cond))
            if dh < 0:
                if attempt == 2:
                    raise RuntimeError(f"GetFileByTime err={self.sdk.NET_DVR_GetLastError()}")
                time.sleep(1); continue
            try:
                self.sdk.NET_DVR_PlayBackControl(dh, 1, 0, None)
                last, stall = 0, 0
                while True:
                    time.sleep(0.5)
                    sz = os.path.getsize(out_ps) if os.path.exists(out_ps) else 0
                    if sz >= (end_ms - start_ms) and sz > 10000:
                        break
                    if sz == last:
                        stall += 1
                        if stall >= 20:
                            break
                    else:
                        stall = 0
                    last = sz
            finally:
                self.sdk.NET_DVR_StopGetFile(dh)
            if os.path.exists(out_ps) and os.path.getsize(out_ps) > 10000:
                return os.path.getsize(out_ps)
        raise RuntimeError("下载无数据")

def ps_to_mp4(ps, mp4):
    r = subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                        "-fflags", "+genpts", "-i", ps, "-c", "copy",
                        "-movflags", "+faststart", mp4], capture_output=True)
    return r.returncode == 0

def main():
    clips_fn, out_dir, serial = sys.argv[1:4]
    cam = ec.camera_by_serial(serial)
    if not cam:
        print(f"cameras 里找不到 {serial}"); sys.exit(1)
    os.makedirs(out_dir, exist_ok=True)
    clips = [c for c in json.load(open(clips_fn)) if c["serial"] == serial]
    dl = Downloader(os.environ.get("SDK_DIR", os.path.expanduser("~/hcnetsdk/MakeAll")),
                    cam["ip"], cam["code"])
    ok = 0
    for i, c in enumerate(clips):
        t = time.strftime("%H%M%S", time.localtime(c["start"]/1000))
        base = f"{out_dir}/{serial}_{t}"
        ps, mp4 = base + ".ps", base + ".mp4"
        if os.path.exists(mp4) and os.path.getsize(mp4) > 10000:
            ok += 1; continue
        try:
            dl.download(c["start"], c["end"], ps)
            if ps_to_mp4(ps, mp4):
                os.remove(ps); ok += 1
                print(f"[{i+1}/{len(clips)}] {t} ok", flush=True)
            else:
                print(f"[{i+1}/{len(clips)}] {t} 转码失败", flush=True)
        except Exception as e:
            print(f"[{i+1}/{len(clips)}] {t} ERROR {e}", flush=True)
    print(f"done {ok}/{len(clips)}", flush=True)

if __name__ == "__main__":
    main()
