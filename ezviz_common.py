#!/usr/bin/env python3
"""共享工具：读取 .secrets.yml、萤石 API 取 token、查摄像头配置。

所有脚本都从这里读敏感信息，代码里不出现任何硬编码密钥。
"""
import json, os, time, urllib.request, urllib.parse

import yaml

_SECRET_CANDIDATES = [
    os.environ.get("EZVIZ_SECRETS", ""),
    os.path.expanduser("~/.secrets.yml"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), ".secrets.yml"),
]

_cache = None

def load_secrets():
    global _cache
    if _cache is not None:
        return _cache
    for path in _SECRET_CANDIDATES:
        if path and os.path.exists(path):
            with open(path) as f:
                _cache = yaml.safe_load(f)
            _cache["_path"] = path
            return _cache
    raise RuntimeError("找不到 .secrets.yml，请按 .secrets.example.yml 创建")

def cameras():
    return load_secrets().get("cameras", [])

def camera_by_serial(serial):
    for c in cameras():
        if c["serial"] == serial:
            return c
    return None

def app_key():
    return load_secrets()["ezviz_app_key"]

def app_secret():
    return load_secrets()["ezviz_app_secret"]

def bark_key():
    return load_secrets().get("bark_key", "")

def netdisk_dir():
    return load_secrets().get("netdisk_dir", "ezviz-highlights")

def request_with_retry(req, timeout=20, attempts=4):
    for attempt in range(attempts):
        try:
            return urllib.request.urlopen(req, timeout=timeout)
        except (urllib.error.URLError, TimeoutError):
            if attempt == attempts - 1:
                raise
            time.sleep(2 ** attempt)

def get_token():
    data = urllib.parse.urlencode({"appKey": app_key(), "appSecret": app_secret()}).encode()
    r = json.loads(request_with_retry(
        urllib.request.Request("https://open.ys7.com/api/lapp/token/get", data=data)).read().decode())
    if str(r.get("code")) != "200":
        raise RuntimeError(f"获取 accessToken 失败: {r}")
    return r["data"]["accessToken"]

def api_post(path, data, timeout=20):
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(f"https://open.ys7.com{path}", data=body,
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    return json.loads(request_with_retry(req, timeout=timeout).read().decode())

def day_range_ms(date_str):
    """'YYYY-MM-DD' -> (当天0点 ms, 当天结束 ms)（本地时区）"""
    y, m, d = map(int, date_str.split("-"))
    s = int(time.mktime((y, m, d, 0, 0, 0, 0, 0, -1)) * 1000)
    return s, s + 86400_000 - 1
