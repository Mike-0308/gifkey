# -*- coding: utf-8 -*-
"""
GIF 去背景 —— 本地绿幕抠像工具
逐帧剔除指定背景色（默认 #00ff00），输出带透明通道的 GIF / WebP / PNG。
全部在本机处理，文件不外传。
"""
from __future__ import annotations

import atexit
import os
import queue
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import uuid
import webbrowser
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image
from flask import Flask, abort, jsonify, request, send_file

import keying

BASE = Path(__file__).resolve().parent
STATIC = BASE / "static"
WORK = BASE / "work"
OUTPUT = BASE / "output"
for _p in (STATIC, WORK, OUTPUT):
    _p.mkdir(parents=True, exist_ok=True)

app = Flask(__name__, static_folder=str(STATIC), static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = 300 * 1024 * 1024

MAX_FRAMES = 2000
MAX_PIXELS = 40_000_000  # 单帧像素上限

JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()
Q: "queue.Queue[str]" = queue.Queue()


# ------------------------------------------------------------------ 工具
def guess_corner_color(frames: list[Image.Image]) -> str:
    """取四角 + 边框的众数颜色，作为推荐的背景色。"""
    if not frames:
        return "#00ff00"
    im = frames[0].convert("RGB")
    w, h = im.size
    px = im.load()
    samples = []
    step_x = max(1, w // 40)
    step_y = max(1, h // 40)
    for x in range(0, w, step_x):
        samples.append(px[x, 0])
        samples.append(px[x, h - 1])
    for y in range(0, h, step_y):
        samples.append(px[0, y])
        samples.append(px[w - 1, y])
    counts = Counter(samples)
    color = counts.most_common(1)[0][0]
    return keying.rgb_to_hex(color)


def safe_stem(name: str) -> str:
    stem = Path(name).stem
    stem = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", stem).strip(" .")
    return (stem or "anim")[:50]


def prune_work(keep: int = 1, max_age_sec: float = 1800.0) -> None:
    """清理 work/ 里的上传缓存，最多留最近 keep 个任务的源文件。

    源文件要留一份给「换个参数再来」（同一次上传反复调参不会重传），但绝不该
    按时间攒着：一个 70MB 的素材就能让整个文件夹从 89MB 变成 160MB。
    所以策略是「只留最近 keep 个，其余立刻删」，超龄的也一并收掉。
    正在排队/处理中的任务永远不动。
    """
    if not WORK.exists():
        return
    with JOBS_LOCK:
        busy = {j["src"] for j in JOBS.values()
                if j.get("status") in ("queued", "running")}
    dirs = []
    for d in WORK.iterdir():
        try:
            if not d.is_dir():
                continue
            if any(Path(s).parent == d for s in busy):
                continue
            dirs.append((d.stat().st_mtime, d))
        except OSError:
            continue
    dirs.sort(key=lambda x: x[0], reverse=True)
    now = time.time()
    for i, (mtime, d) in enumerate(dirs):
        if i < keep and now - mtime <= max_age_sec:
            continue
        shutil.rmtree(d, ignore_errors=True)


def read_frames(path: Path):
    im = Image.open(path)
    n = getattr(im, "n_frames", 1)
    frames: list[Image.Image] = []
    durations: list[int] = []
    for i in range(n):
        im.seek(i)
        try:
            d = int(im.info.get("duration", 100) or 100)
        except Exception:
            d = 100
        durations.append(max(20, d))
        frames.append(im.convert("RGBA").copy())
    loop = int(im.info.get("loop", 0) or 0)
    return frames, durations, loop, im.size


def public_job(job: dict) -> dict:
    elapsed = 0.0
    if job["started"]:
        elapsed = (job["finished"] or time.time()) - job["started"]
    return {
        "id": job["id"],
        "status": job["status"],
        "progress": round(job["progress"], 1),
        "stage": job["stage"],
        "error": job["error"],
        "elapsed": round(elapsed, 2),
        "result": job["result"],
    }


# ------------------------------------------------------------------ 处理
def do_process(job: dict, params: dict):
    src = Path(job["src"])
    frames, durations, loop, size = read_frames(src)
    total = len(frames)
    if total > MAX_FRAMES:
        raise RuntimeError(f"帧数太多（{total} 帧），建议先压缩到 {MAX_FRAMES} 帧以内。")

    key_rgb = keying.hex_to_rgb(params["color"])
    tol = float(params["tolerance"])
    soft = float(params["softness"])
    despill = bool(params["despill"])
    shrink = bool(params["shrink"])
    fmt = params["format"]
    tier = params.get("tier", "original")
    scale = float(params.get("scale", 1.0) or 1.0)

    # 缩放放在抠像之前：像素少一半，后面的计算和编码都跟着省一半
    if abs(scale - 1.0) > 1e-6:
        job["stage"] = "调整尺寸…"
        frames = keying.scale_frames(frames, scale)
        size = frames[0].size

    out_dir = OUTPUT / f"{time.strftime('%Y%m%d-%H%M%S')}_{safe_stem(job['filename'])}"
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = safe_stem(job["filename"])

    out_frames: list[Image.Image] = []
    for i, f in enumerate(frames):
        out_frames.append(keying.key_frame(f, key_rgb, tol, soft, despill, shrink))
        job["progress"] = (i + 1) / total * 88.0
        if i % 5 == 0:
            job["stage"] = f"抠像中… 第 {i + 1}/{total} 帧"

    job["stage"] = "编码输出…"
    job["progress"] = 90.0

    animated = total > 1
    encoded = total
    if fmt == "webp" and animated:
        dst = out_dir / f"{stem}_透明.webp"
        encoded = keying.save_webp(out_frames, str(dst), durations, loop, tier=tier)
        kind = "webp"
    elif fmt == "gif" or animated:
        dst = out_dir / f"{stem}_透明.gif"
        encoded = keying.save_gif(out_frames, str(dst), durations, loop, tier=tier)
        kind = "gif"
    else:
        dst = out_dir / f"{stem}_透明.png"
        out_frames[0].save(dst, format="PNG")
        kind = "png"

    job["progress"] = 100.0
    job["stage"] = "完成"
    job["result"] = {
        "kind": kind,
        "name": dst.name,
        "path": str(dst),
        "size": dst.stat().st_size,
        "dir": str(out_dir),
        "frames": total,
        "encoded_frames": encoded,
        "width": size[0],
        "height": size[1],
        "duration_ms": sum(durations) if animated else 0,
        "tier": tier,
        "scale": scale,
    }


def worker():
    while True:
        jid = Q.get()
        job = JOBS.get(jid)
        if not job:
            continue
        job["status"] = "running"
        job["started"] = time.time()
        params = job.pop("params", None)
        try:
            do_process(job, params or {})
            job["status"] = "done"
        except Exception as e:  # noqa: BLE001
            job["status"] = "error"
            job["error"] = str(e) or "处理失败"
            job["stage"] = "出错了"
        finally:
            job["finished"] = time.time()
            # 处理完立刻收拾：只保当前这一个任务的源文件，别让 70MB 素材堆着
            prune_work(keep=1)


threading.Thread(target=worker, daemon=True).start()


# ------------------------------------------------------------------ 路由
@app.get("/")
def index():
    return send_file(STATIC / "index.html")


@app.get("/api/info")
def api_info():
    return jsonify({
        "output_dir": str(OUTPUT),
        "max_frames": MAX_FRAMES,
        "tiers": keying.TIER_LABELS,
        "scales": [1.0, 0.75, 0.5, 0.35],
        "container": os.environ.get("GIFKEY_CONTAINER") == "1",
    })


@app.post("/api/preview")
def api_preview():
    """只处理第 1 帧，返回 PNG，用于实时调参。"""
    data = request.get_json(silent=True) or {}
    job = JOBS.get(data.get("job_id"))
    if not job:
        return jsonify({"error": "任务不存在"}), 404
    try:
        key_rgb = keying.hex_to_rgb((data.get("color") or "#00ff00").strip())
    except Exception:
        return jsonify({"error": "颜色格式不对"}), 400
    try:
        im = Image.open(job["src"])
        im.seek(0)
        frame = im.convert("RGBA")
        idx = int(data.get("frame", 0) or 0)
        if 0 <= idx < getattr(im, "n_frames", 1):
            im.seek(idx)
            frame = im.convert("RGBA")
        out = keying.key_frame(
            frame, key_rgb,
            float(data.get("tolerance", 45)),
            float(data.get("softness", 20)),
            bool(data.get("despill", True)),
            bool(data.get("shrink", False)),
        )
        import io
        buf = io.BytesIO()
        out.save(buf, format="PNG", optimize=True)
        buf.seek(0)
        resp = send_file(buf, mimetype="image/png", max_age=0)
        resp.headers["Cache-Control"] = "no-store"
        return resp
    except Exception as e:  # noqa: BLE001
        return jsonify({"error": str(e)}), 500


@app.post("/api/upload")
def api_upload():
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"error": "没有收到文件"}), 400
    ext = Path(f.filename).suffix.lower()
    if ext not in (".gif", ".webp", ".png", ".jpg", ".jpeg", ".bmp"):
        return jsonify({"error": "只支持 gif / webp / png / jpg / bmp"}), 400

    jid = uuid.uuid4().hex[:12]
    d = WORK / jid
    d.mkdir(parents=True, exist_ok=True)
    src = d / ("source" + ext)
    f.save(str(src))

    try:
        frames, durations, loop, size = read_frames(src)
    except Exception as e:  # noqa: BLE001
        shutil.rmtree(d, ignore_errors=True)
        return jsonify({"error": f"这个文件读不出来：{e}"}), 400

    if len(frames) > MAX_FRAMES:
        shutil.rmtree(d, ignore_errors=True)
        return jsonify({"error": f"帧数太多（{len(frames)} 帧），请先压缩"}), 400
    if size[0] * size[1] > MAX_PIXELS:
        shutil.rmtree(d, ignore_errors=True)
        return jsonify({"error": f"尺寸太大（{size[0]}×{size[1]}），请先缩小"}), 400

    job = {
        "id": jid, "filename": f.filename, "src": str(src), "ext": ext,
        "status": "ready", "progress": 0.0, "stage": "待处理", "error": "",
        "created": time.time(), "started": 0.0, "finished": 0.0, "result": None,
        "frames": len(frames), "durations": durations, "loop": loop, "size": size,
    }
    with JOBS_LOCK:
        JOBS[jid] = job
    prune_work(keep=1)  # 新素材已落地，上一个任务的源文件就可以扔了

    return jsonify({
        "job_id": jid,
        "frames": len(frames),
        "width": size[0],
        "height": size[1],
        "duration_ms": sum(durations) if len(frames) > 1 else 0,
        "bytes": src.stat().st_size,
        "animated": len(frames) > 1,
        "suggest_color": guess_corner_color(frames),
        "loop": loop,
    })


@app.post("/api/process")
def api_process():
    data = request.get_json(silent=True) or {}
    jid = data.get("job_id")
    job = JOBS.get(jid)
    if not job:
        return jsonify({"error": "任务不存在，请重新上传"}), 404
    if job["status"] == "running":
        return jsonify({"error": "正在处理中，请稍候"}), 400
    if not Path(job["src"]).exists():
        return jsonify({"error": "临时文件已被清理，请重新选择文件上传"}), 410

    color = (data.get("color") or "#00ff00").strip()
    try:
        keying.hex_to_rgb(color)
    except Exception:
        return jsonify({"error": "背景色格式不对，例如 #00ff00"}), 400

    fmt = data.get("format", "gif")
    if fmt not in ("gif", "webp"):
        fmt = "gif"

    tier = data.get("tier", "original")
    if tier not in keying.TIERS:
        tier = "original"

    try:
        scale = float(data.get("scale", 1.0) or 1.0)
    except (TypeError, ValueError):
        scale = 1.0
    if scale not in (1.0, 0.75, 0.5, 0.35):
        scale = 1.0

    job.update({
        "status": "queued", "progress": 0.0, "stage": "排队中…", "error": "",
        "result": None,
        "params": {
            "color": color,
            "tolerance": min(255, max(0, float(data.get("tolerance", 45)))),
            "softness": min(200, max(1, float(data.get("softness", 20)))),
            "despill": bool(data.get("despill", True)),
            "shrink": bool(data.get("shrink", False)),
            "format": fmt,
            "tier": tier,
            "scale": scale,
        },
    })
    Q.put(jid)
    return jsonify({"job_id": jid})


@app.get("/api/job/<jid>")
def api_job(jid: str):
    job = JOBS.get(jid)
    if not job:
        return jsonify({"error": "任务不存在"}), 404
    return jsonify(public_job(job))


@app.get("/api/file/<jid>/<which>")
def api_file(jid: str, which: str):
    job = JOBS.get(jid)
    if not job:
        abort(404)
    if which == "source":
        path, name = job["src"], "source" + job["ext"]
    elif which == "result" and job["result"]:
        path, name = job["result"]["path"], job["result"]["name"]
    else:
        abort(404)
    return send_file(
        path,
        as_attachment=request.args.get("download") == "1",
        download_name=name,
        conditional=True,
        max_age=0,
    )


@app.post("/api/reveal")
def api_reveal():
    data = request.get_json(silent=True) or {}
    d = data.get("dir") or str(OUTPUT)
    opener = "open" if sys.platform == "darwin" else "xdg-open"
    if os.name != "nt" and not shutil.which(opener):
        return jsonify({"error": "容器里没有文件管理器，请点「下载文件」存到本地"}), 400
    try:
        if os.name == "nt":
            os.startfile(d)  # noqa: S606
        else:
            subprocess.Popen([opener, d])
    except Exception as e:  # noqa: BLE001
        return jsonify({"error": str(e)}), 500
    return jsonify({"ok": True})


@app.post("/api/quit")
def api_quit():
    def bye():
        time.sleep(0.35)
        prune_work(keep=0)  # 关掉就把上传缓存清干净，别留 70MB 垃圾
        os._exit(0)
    threading.Thread(target=bye, daemon=True).start()
    return jsonify({"ok": True})


@app.errorhandler(413)
def too_large(_):
    return jsonify({"error": "文件太大（上限 300MB）"}), 413


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def main():
    base_port = int(os.environ.get("GIFKEY_PORT", "8849"))
    host = os.environ.get("GIFKEY_HOST", "127.0.0.1")
    port = base_port
    # 容器里端口由 docker 映射死了，自己挪端口会连不上，所以只在本地版自动找空位
    if os.environ.get("GIFKEY_CONTAINER") != "1":
        for p in range(base_port, base_port + 12):
            if port_free(p):
                port = p
                break
    # 进程重启后旧任务的目录已经没人引用，全部收掉
    prune_work(keep=0)
    atexit.register(lambda: prune_work(keep=0))  # 关窗口 / Ctrl+C 也清
    url = f"http://{'127.0.0.1' if host in ('0.0.0.0', '::') else host}:{port}/"
    if os.environ.get("GIFKEY_NO_BROWSER") != "1":
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    print(f"\n  GIF 去背景已启动：{url}")
    print(f"  监听：{host}:{port}")
    print(f"  输出目录：{OUTPUT}")
    print("  关闭本窗口（或点网页里的「退出」）即可停止服务。\n")
    app.run(host=host, port=port, threaded=True, debug=False)


if __name__ == "__main__":
    main()
