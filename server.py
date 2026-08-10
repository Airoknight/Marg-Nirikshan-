"""Web UI for the people counter: switch camera and detector live in a browser.

  ./run.sh server.py                 then open http://localhost:8000
  ./run.sh server.py --host 0.0.0.0  to reach it from your phone on the LAN

A single worker thread owns the camera and produces annotated JPEGs; every
browser tab just reads the latest one. That keeps one capture/inference loop no
matter how many viewers there are -- the alternative, a loop per client, would
fight over the camera device and multiply GPU load.
"""

import argparse
import shutil
import threading
import time
from collections import deque
from pathlib import Path

import cv2
import numpy as np
import uvicorn
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

from camera import DEFAULT_SOURCE, is_device_source, list_cameras, open_capture
from detectors import build_detector

HERE = Path(__file__).parent
BOUNDARY = "frameboundary"
UPLOADS = HERE / "uploads"
VIDEO_EXTS = {".mp4", ".avi", ".mkv", ".mov", ".webm", ".m4v"}


def render(frame, result, mode, detector_name, fps, infer_ms):
    """Draw detections plus a HUD. `mode` is 'boxes', 'dots', or 'heatmap'."""
    out = frame.copy()
    h, w = out.shape[:2]
    
    # Base scale factor relative to standard 720p height/width
    scale = max(0.5, min(w, h) / 720.0)
    thick = max(1, int(round(2 * scale)))
    
    # Heatmap Overlay Mode
    if mode == "heatmap" or result.density_map is not None:
        d_map = result.density_map
        if d_map is None:
            # Generate continuous spatial density surface on the fly if needed
            grid = np.zeros((h, w), dtype=np.float32)
            if len(result.points) > 0:
                for pt in result.points:
                    px, py = int(round(pt[0])), int(round(pt[1]))
                    if 0 <= px < w and 0 <= py < h:
                        grid[py, px] += 1.0
                ksize = int(round(15.0 * 4)) | 1
                d_map = cv2.GaussianBlur(grid, (ksize, ksize), 15.0)
                total_sum = np.sum(d_map)
                if total_sum > 0:
                    d_map = d_map * (len(result.points) / total_sum)
            else:
                d_map = grid
        
        d_max = d_map.max() if d_map.max() > 0 else 1.0
        d_norm = np.clip((d_map / (d_max * 0.5)) * 255.0, 0, 255).astype(np.uint8)
        heatmap = cv2.applyColorMap(d_norm, cv2.COLORMAP_JET)
        out = cv2.addWeighted(out, 0.55, heatmap, 0.45, 0)
        
        # Subtle white dots over density peaks
        for x, y in result.points.astype(int):
            cv2.circle(out, (x, y), max(2, int(3 * scale)), (255, 255, 255), -1)

    elif mode == "boxes" and result.boxes is not None:
        for i, (x1, y1, x2, y2) in enumerate(result.boxes.astype(int)):
            cv2.rectangle(out, (x1, y1), (x2, y2), (0, 230, 0), thick)
            if result.ids is not None:
                font_scale = 0.4 * scale
                cv2.putText(out, f"#{result.ids[i]}", (x1, max(int(14 * scale), y1 - 6)),
                            cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0, 230, 0), max(1, int(scale)), cv2.LINE_AA)
    else:
        # Scale dot radius proportionally to image resolution & crowd density
        base_r = 4 if result.count < 80 else (3 if result.count < 300 else 2)
        r = max(2, int(round(base_r * scale)))
        for x, y in result.points.astype(int):
            cv2.circle(out, (x, y), r, (0, 0, 255), -1)
            if r >= 3:
                cv2.circle(out, (x, y), r + max(1, int(scale)), (255, 255, 255), max(1, int(scale)))

    # HUD Bar
    hud_h = int(48 * scale)
    cv2.rectangle(out, (0, 0), (w, hud_h), (0, 0, 0), -1)
    
    font_main = 0.9 * scale
    font_sub = 0.55 * scale
    y_main = int(33 * scale)
    
    # Calculate crowd density status level
    if result.count < 15:
        status_str = "LOW DENSITY"
        status_color = (0, 255, 0)       # Green
    elif result.count < 50:
        status_str = "MODERATE"
        status_color = (0, 215, 255)     # Yellow/Cyan
    else:
        status_str = "HIGH CROWD"
        status_color = (0, 0, 255)       # Red Warning

    # Left text: Count + Density Status
    cv2.putText(out, f"PEOPLE: {result.count}  [{status_str}]", (int(12 * scale), y_main),
                cv2.FONT_HERSHEY_SIMPLEX, font_main, status_color, max(2, int(round(2 * scale))), cv2.LINE_AA)
    
    # Right text: Detector stats
    stats_str = f"{detector_name}  |  {infer_ms:5.1f} ms  |  {fps:4.1f} FPS"
    (text_w, _), _ = cv2.getTextSize(stats_str, cv2.FONT_HERSHEY_SIMPLEX, font_sub, max(1, int(scale)))
    x_stats = max(int(240 * scale), w - text_w - int(12 * scale))
    cv2.putText(out, stats_str, (x_stats, y_main),
                cv2.FONT_HERSHEY_SIMPLEX, font_sub, (200, 200, 200), max(1, int(scale)), cv2.LINE_AA)
    return out


class Pipeline:
    """Owns the camera and the active detector; all mutation happens under a lock
    so the worker never reads a half-swapped configuration."""

    def __init__(self, source=DEFAULT_SOURCE, detector="yolo"):
        self.lock = threading.Lock()
        self.source = source
        self.detector_kind = detector
        self.render_mode = "boxes"
        self.cap = open_capture(source)
        self._detectors = {}  # kind -> instance, cached; building one costs seconds
        self.detector = self._get_detector(detector)
        self._note_source(source)

        self.latest_jpeg = None
        self.frame_seq = 0        # bumped per encoded frame so viewers can skip duplicates
        self.count = 0
        self.infer_ms = 0.0
        self.fps = 0.0
        self.error = None
        self._times = deque(maxlen=30)
        self._running = True

    def _get_detector(self, kind):
        if kind not in self._detectors:
            self._detectors[kind] = build_detector(kind)
        return self._detectors[kind]

    def _note_source(self, source):
        """Record whether we are on a live camera or a file, plus the file's
        length and native rate, which drive looping and playback pacing."""
        self.is_video = not is_device_source(source)
        self.video_fps = float(self.cap.get(cv2.CAP_PROP_FPS)) if self.is_video else 0.0
        if not (0 < self.video_fps < 240):      # some containers report 0 or nonsense
            self.video_fps = 25.0
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT)) if self.is_video else 0
        self.pos_frame = 0

    def configure(self, source=None, detector=None, render_mode=None,
                  conf=None, imgsz=None, threshold=None, sigma=None, track=None):
        with self.lock:
            if source is not None and source != self.source:
                self.cap.release()
                self.cap = open_capture(source)
                self.source = source
                self._note_source(source)
            if detector is not None and detector != self.detector_kind:
                self.detector = self._get_detector(detector)
                self.detector_kind = detector
                if render_mode is None and detector in ("csrnet", "density"):
                    self.render_mode = "heatmap"
            if render_mode is not None:
                self.render_mode = render_mode
            d = self.detector
            if conf is not None and hasattr(d, "conf"):
                d.conf = float(conf)
            if imgsz is not None and hasattr(d, "imgsz"):
                d.imgsz = int(imgsz)
            if threshold is not None and hasattr(d, "threshold"):
                d.threshold = float(threshold)
            if sigma is not None and hasattr(d, "sigma"):
                d.sigma = float(sigma)
            if track is not None and hasattr(d, "track"):
                d.track = bool(track)

    def state(self):
        with self.lock:
            d = self.detector
            active_render = self.render_mode
            if not d.supports_boxes and active_render == "boxes":
                active_render = "dots"
            
            density_status = "LOW" if self.count < 15 else ("MODERATE" if self.count < 50 else "HIGH CONGESTION")
            return {
                "source": self.source,
                "detector": self.detector_kind,
                "render_mode": active_render,
                "supports_boxes": getattr(d, "supports_boxes", False),
                "supports_heatmap": getattr(d, "supports_heatmap", True),
                "count": self.count,
                "density_status": density_status,
                "fps": round(self.fps, 1),
                "infer_ms": round(self.infer_ms, 1),
                "conf": getattr(d, "conf", None),
                "imgsz": getattr(d, "imgsz", None),
                "threshold": getattr(d, "threshold", None),
                "sigma": getattr(d, "sigma", None),
                "track": getattr(d, "track", None),
                "error": self.error,
                "is_video": self.is_video,
                "pos_frame": self.pos_frame,
                "total_frames": self.total_frames,
            }

    def run(self):
        while self._running:
            tick = time.perf_counter()
            with self.lock:
                cap, det, mode, name = self.cap, self.detector, self.render_mode, self.detector_kind
                is_video, vfps = self.is_video, self.video_fps
            ok, frame = cap.read()
            if not ok:
                if is_video:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)   # loop the clip
                    self.pos_frame = 0
                    continue
                self.error = "camera read failed"
                time.sleep(0.5)
                continue
            self.error = None
            if is_video:
                self.pos_frame = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
            try:
                t0 = time.perf_counter()
                result = det.infer(frame)
                self.infer_ms = (time.perf_counter() - t0) * 1000
            except Exception as exc:                      # keep the stream alive
                self.error = f"{type(exc).__name__}: {exc}"
                time.sleep(0.3)
                continue

            self._times.append(time.time())
            if len(self._times) > 1:
                self.fps = (len(self._times) - 1) / (self._times[-1] - self._times[0])
            self.count = result.count

            active_mode = mode
            if not det.supports_boxes and active_mode == "boxes":
                active_mode = "dots"

            annotated = render(frame, result, active_mode,
                               name, self.fps, self.infer_ms)
            ok, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if ok:
                self.latest_jpeg = buf.tobytes()
                self.frame_seq += 1

    def stop(self):
        self._running = False


app = FastAPI()
pipeline: Pipeline | None = None


@app.get("/", response_class=HTMLResponse)
def index():
    return (HERE / "static" / "index.html").read_text()


@app.get("/api/sources")
def api_sources():
    cams = [c for c in list_cameras(probe=True, assume_working=pipeline.source) if c["works"]]
    cam_opts = [{"value": c["stable_path"] or str(c["index"]),
                 "label": f"{c['index']}: {c['name']}"} for c in cams]

    videos_dir = HERE / "videos"
    video_opts = []
    for d, tag in [(videos_dir, "Sample"), (UPLOADS, "Uploaded")]:
        if d.exists():
            for f in sorted(d.iterdir()):
                if f.is_file() and f.suffix.lower() in VIDEO_EXTS:
                    video_opts.append({"value": str(f.resolve()), "label": f"[{tag}] {f.name}"})

    return JSONResponse({"cameras": cam_opts, "videos": video_opts})


@app.get("/api/cameras")
def api_cameras():
    sources = api_sources()
    # Flatten for backward compatibility if any client expects a simple array
    import json
    data = json.loads(sources.body)
    return JSONResponse(data["cameras"] + data["videos"])


@app.post("/api/upload")
async def api_upload(file: UploadFile = File(...)):
    ext = Path(file.filename).suffix.lower()
    if ext not in VIDEO_EXTS:
        return JSONResponse({"ok": False, "error": f"Invalid video file extension '{ext}'. Allowed: {', '.join(sorted(VIDEO_EXTS))}"}, status_code=400)

    UPLOADS.mkdir(parents=True, exist_ok=True)
    dest = UPLOADS / file.filename
    try:
        with open(dest, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        pipeline.configure(source=str(dest.resolve()))
    except Exception as exc:
        return JSONResponse({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, status_code=400)

    return JSONResponse({"ok": True, "source": str(dest.resolve()), **pipeline.state()})


@app.get("/api/state")
def api_state():
    return JSONResponse(pipeline.state())


@app.post("/api/config")
async def api_config(cfg: dict):
    try:
        pipeline.configure(**cfg)
    except Exception as exc:
        return JSONResponse({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, 400)
    return JSONResponse({"ok": True, **pipeline.state()})


def mjpeg():
    """Emit each encoded frame exactly once. Polling the buffer on a fixed timer
    instead would resend whatever is current, wasting several times the bandwidth
    when inference runs slower than the poll rate -- which it always does."""
    last_seq = -1
    while True:
        seq = pipeline.frame_seq
        if seq == last_seq or pipeline.latest_jpeg is None:
            time.sleep(0.005)
            continue
        last_seq = seq
        buf = pipeline.latest_jpeg
        yield (b"--" + BOUNDARY.encode() + b"\r\nContent-Type: image/jpeg\r\n"
               b"Content-Length: " + str(len(buf)).encode() + b"\r\n\r\n" + buf + b"\r\n")


@app.get("/stream.mjpg")
def stream():
    return StreamingResponse(mjpeg(),
                             media_type=f"multipart/x-mixed-replace; boundary={BOUNDARY}")


def main():
    global pipeline
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--host", default="127.0.0.1", help="0.0.0.0 to expose on the LAN")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--source", default=DEFAULT_SOURCE)
    p.add_argument("--detector", default="yolo", choices=["yolo", "p2pnet", "density", "csrnet"])
    args = p.parse_args()

    pipeline = Pipeline(args.source, args.detector)
    threading.Thread(target=pipeline.run, daemon=True).start()
    print(f"\n  open http://{'localhost' if args.host=='127.0.0.1' else args.host}:{args.port}\n")
    try:
        uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    finally:
        pipeline.stop()


if __name__ == "__main__":
    main()
