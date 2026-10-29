#!/usr/bin/env python3
"""下载摄像头一整天录像（用于无云端事件的摄像头做本地人形检测）。在 Lima 虚拟机里跑。

用法: python3 grab_day.py <serial> <YYYY-MM-DD> <out.ps> [main|sub]
  serial 决定连哪台（IP/验证码从 .secrets.yml 读）。
环境变量: SDK_DIR 指向 HCNetSDK 库目录。
"""
import ctypes, hashlib, os, sys, time
from ctypes import CDLL, Structure, byref, c_uint, c_byte, c_char_p
import ezviz_common as ec
from hik_downloader import NET_DVR_TIME, NET_DVR_PLAYCOND, sdk_pwd

def main():
    serial, date, out = sys.argv[1:4]
    stream = sys.argv[4] if len(sys.argv) > 4 else "sub"
    cam = ec.camera_by_serial(serial)
    if not cam:
        print(f"cameras 里找不到 {serial}"); sys.exit(1)
    y, m, d = map(int, date.split("-"))
    sdk_dir = os.environ.get("SDK_DIR", os.path.expanduser("~/hcnetsdk/MakeAll"))
    sdk = CDLL(f"{sdk_dir}/libhcnetsdk.so")
    sdk.NET_DVR_SetSDKInitCfg(2, c_char_p(sdk_dir.encode()))
    sdk.NET_DVR_Init()
    sdk.NET_DVR_SetConnectTime(5000, 1)
    info = ctypes.create_string_buffer(248)
    uid = sdk.NET_DVR_Login_V30(cam["ip"].encode(), 8000, b"EZ_LOCAL_USER",
                                sdk_pwd(cam["code"]).encode(), byref(info))
    if uid < 0:
        print("登录失败", sdk.NET_DVR_GetLastError()); sys.exit(1)
    cond = NET_DVR_PLAYCOND()
    cond.dwChannel = 1
    cond.struStartTime = NET_DVR_TIME(y, m, d, 0, 0, 0)
    cond.struStopTime = NET_DVR_TIME(y, m, d, 23, 59, 59)
    cond.byDownload = 1
    cond.byVODFileType = 0
    if stream == "sub":
        cond.byStreamType = 1
    dh = sdk.NET_DVR_GetFileByTime_V40(uid, out.encode(), byref(cond))
    if dh < 0:
        print("GetFileByTime 失败", sdk.NET_DVR_GetLastError()); sys.exit(1)
    sdk.NET_DVR_PlayBackControl(dh, 1, 0, None)
    last, stall, t0 = 0, 0, time.time()
    while True:
        time.sleep(2)
        sz = os.path.getsize(out) if os.path.exists(out) else 0
        el = time.time() - t0
        print(f"\r{sz/1e6:.0f}MB {el:.0f}s {sz/1e6/max(el,1):.1f}MB/s", end="", flush=True)
        if sz == last:
            stall += 1
            if stall >= 20:
                break
        else:
            stall = 0
        last = sz
    sdk.NET_DVR_StopGetFile(dh)
    sdk.NET_DVR_Logout(uid)
    print(f"\ndone {os.path.getsize(out)/1e6:.0f}MB -> {out}")

if __name__ == "__main__":
    main()
