#!/usr/bin/env python3
"""本地人形检测：从录像里找出"有人"的时段。在 Lima 虚拟机里跑（venv 的 onnxruntime+cv2）。

用法: python3 detect_people.py <video.mp4> <sample_sec> <conf> [model.onnx]
流程: ffmpeg 按 sample_sec 抽帧 -> YOLOv8n 检测 person -> 合并相邻命中为时段
输出: <video>.people.json  {"segments":[{start,end,n}...], "total_hits":N}  (秒)
"""
import json, os, subprocess, sys, tempfile, time
import numpy as np
import cv2
import onnxruntime as ort

PERSON_CLASS = 0  # COCO: person
NMS_THRESH = 0.45

def letterbox(img, size=640):
    h, w = img.shape[:2]
    r = min(size/h, size/w)
    nh, nw = int(h*r), int(w*r)
    img = cv2.resize(img, (nw, nh))
    canvas = np.full((size, size, 3), 114, dtype=np.uint8)
    canvas[:nh, :nw] = img
    return canvas

def detect(session, frame, conf_thres):
    x = letterbox(frame)[:, :, ::-1].transpose(2, 0, 1).astype(np.float32) / 255.0
    x = np.expand_dims(x, 0)
    out = session.run(None, {session.get_inputs()[0].name: x})[0][0].T
    boxes, scores = [], []
    for row in out:
        cs = row[4:]
        cid = int(np.argmax(cs))
        if cid != PERSON_CLASS or cs[cid] < conf_thres:
            continue
        cx, cy, w, h = row[0], row[1], row[2], row[3]
        boxes.append([float(cx-w/2), float(cy-h/2), float(w), float(h)])
        scores.append(float(cs[cid]))
    if not boxes:
        return 0
    idx = cv2.dnn.NMSBoxes(boxes, scores, conf_thres, NMS_THRESH)
    return len(idx) if len(idx) else 0

def main():
    video, sample_sec, conf = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
    model = sys.argv[4] if len(sys.argv) > 4 else os.path.expanduser("~/models/yolov8n.onnx")
    session = ort.InferenceSession(model, providers=["CPUExecutionProvider"])
    tmp = tempfile.mkdtemp(prefix="frames_", dir=os.path.expanduser("~/work"))
    try:
        subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", video,
                        "-vf", f"fps=1/{sample_sec}", os.path.join(tmp, "f_%06d.jpg")], check=True)
    except subprocess.CalledProcessError:
        print("抽帧失败"); sys.exit(1)
    frames = sorted(os.listdir(tmp))
    hits = []
    t0 = time.time()
    for i, fn in enumerate(frames):
        sec = i * sample_sec
        img = cv2.imread(os.path.join(tmp, fn))
        if img is None:
            continue
        n = detect(session, img, conf)
        if n:
            hits.append((sec, n))
        if i % 500 == 0:
            print(f"  {i}/{len(frames)} hits={len(hits)} {time.time()-t0:.0f}s", file=sys.stderr, flush=True)
    for fn in frames:
        os.remove(os.path.join(tmp, fn))
    os.rmdir(tmp)
    segs = []
    for sec, n in hits:
        if segs and sec - segs[-1]["end"] <= 2*sample_sec:
            segs[-1]["end"] = sec
            segs[-1]["n"] = max(segs[-1]["n"], n)
        else:
            segs.append({"start": sec, "end": sec, "n": n})
    out = {"video": video, "sample_sec": sample_sec, "segments": segs, "total_hits": len(hits)}
    json.dump(out, open(video + ".people.json", "w"), indent=1)
    print(json.dumps({"segments": segs, "total_hits": len(hits)}, ensure_ascii=False))

if __name__ == "__main__":
    main()
