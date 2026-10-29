#!/usr/bin/env python3
"""拉取摄像头某天的人形/移动报警事件，合并成待下载片段清单。在本机 Mac 跑。

用法: python3 fetch_events.py [YYYY-MM-DD]   (默认昨天)
输出: clips_<date>.json -> [{serial, name, start, end}, ...]  (epoch ms)

片段参数可用环境变量调:
  MERGE_GAP_MS   相邻报警合并间隔，默认 90000
  PRE_PAD_MS     片段前预留，默认 10000
  POST_PAD_MS    片段后预留，默认 15000
  MAX_CLIP_MS    单片段最长毫秒数（0 不限制）
"""
import json, os, sys, time
import ezviz_common as ec

MERGE_GAP_MS = int(os.environ.get("MERGE_GAP_MS", "90000"))
PRE_PAD_MS = int(os.environ.get("PRE_PAD_MS", "10000"))
POST_PAD_MS = int(os.environ.get("POST_PAD_MS", "15000"))
MAX_CLIP_MS = int(os.environ.get("MAX_CLIP_MS", "0"))

def alarms(token, serial, s, e):
    rows = []
    for h in range(0, 24, 3):  # 3 小时切片，规避接口单页 50 条上限
        hs = s + h*3600_000
        he = min(e, hs + 3*3600_000)
        for page in range(20):
            r = ec.api_post("/api/lapp/alarm/list", {
                "accessToken": token, "deviceSerial": serial, "startTime": hs, "endTime": he,
                "pageStart": page, "pageSize": 50})
            batch = r.get("data") or []
            rows.extend(batch)
            if len(batch) < 50:
                break
    # 该接口 deviceSerial 参数不生效，返回账号级事件，需客户端过滤
    return [x for x in rows if x.get("deviceSerial") == serial]

def merge(times):
    times = sorted(times)
    clips = []
    for t in times:
        if clips and t - clips[-1]["end"] <= MERGE_GAP_MS:
            clips[-1]["end"] = t
        else:
            clips.append({"start": t, "end": t})
    return clips

def main():
    date = sys.argv[1] if len(sys.argv) > 1 else time.strftime("%Y-%m-%d", time.localtime(time.time()-86400))
    s, e = ec.day_range_ms(date)
    token = ec.get_token()
    out = []
    for cam in ec.cameras():
        serial = cam["serial"]
        evs = alarms(token, serial, s, e)
        clips = merge([x["alarmTime"] for x in evs])
        total = 0
        for c in clips:
            st = c["start"] - PRE_PAD_MS
            en = c["end"] + POST_PAD_MS
            if MAX_CLIP_MS and en - st > MAX_CLIP_MS:
                en = st + MAX_CLIP_MS
            total += en - st
            out.append({"serial": serial, "name": cam["name"], "start": st, "end": en})
        print(f"{cam['name']} {serial}: {len(evs)} 事件 -> {len(clips)} 片段, {total/60000:.1f} 分钟")
    out.sort(key=lambda x: x["start"])
    fn = f"clips_{date}.json"
    json.dump(out, open(fn, "w"), ensure_ascii=False, indent=1)
    print(f"共 {len(out)} 片段 -> {fn}")

if __name__ == "__main__":
    main()
