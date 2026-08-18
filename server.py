"""Web UI for the people counter: switch camera and detector live in a browser.

  ./run.sh server.py                 then open http://localhost:8000
  ./run.sh server.py --host 0.0.0.0  to reach it from your phone on the LAN

A single worker thread owns the camera and produces annotated JPEGs; every
browser tab just reads the latest one. That keeps one capture/inference loop no
matter how many viewers there are -- the alternative, a loop per client, would
fight over the camera device and multiply GPU load.
"""

import argparse
import math
import shutil
import threading
import time
from collections import deque
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import uvicorn
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

from camera import DEFAULT_SOURCE, is_device_source, list_cameras, open_capture
from detectors import Result, build_detector

HERE = Path(__file__).parent
BOUNDARY = "frameboundary"
UPLOADS = HERE / "uploads"
VIDEO_EXTS = {".mp4", ".avi", ".mkv", ".mov", ".webm", ".m4v"}


VIRTUAL_CAMERAS = {
    "cam_01": {
        "camera_id": "cam_01",
        "location": "Bus Terminal - Gate A",
        "capacity": 120,
        "source": str((HERE / "uploads/vidssave.com Shopping, People, Commerce, Mall, Many, Crowd, Walking Free Stock video footage YouTube 720p.mp4").resolve()),
        "label": "📷 Cam 01: Bus Terminal - Gate A (Cap: 120)"
    },
    "cam_02": {
        "camera_id": "cam_02",
        "location": "Bus Terminal - Gate B",
        "capacity": 150,
        "source": str((HERE / "videos/vidssave.com Shopping, People, Commerce, Mall, Many, Crowd, Walking Free Stock video footage YouTube 720p.mp4").resolve()),
        "label": "📷 Cam 02: Bus Terminal - Gate B (Cap: 150)"
    },
    "cam_03": {
        "camera_id": "cam_03",
        "location": "Railway Station - Platform 1",
        "capacity": 800,
        "source": str((HERE / "uploads/vidssave.com Today crowd at Dombivli railway station #rushhour #indianrailways #dombivli 720P.mp4").resolve()),
        "label": "📷 Cam 03: Platform 1 - High Density (Cap: 800)"
    },
    "cam_04": {
        "camera_id": "cam_04",
        "location": "Metro Station - Concourse",
        "capacity": 300,
        "source": str((HERE / "videos/vidssave.com Delhi Metro Crowd #shorts 1080P.mp4").resolve()),
        "label": "📷 Cam 04: Metro Concourse (Cap: 300)"
    }
}


def render(frame, result, mode, detector_name, fps, infer_ms, location_name="Platform 1", capacity=1000, zone_polygon=None, zone_name=None):
    """Draw detections plus a HUD. `mode` is 'boxes', 'dots', or 'heatmap'."""
    out = frame.copy()
    h, w = out.shape[:2]
    total_count = result.count
    
    # Base scale factor relative to standard 720p height/width
    scale = max(0.5, min(w, h) / 720.0)
    thick = max(1, int(round(2 * scale)))
    
    # Check if custom ROI polygon zone is active
    pts_inside = []
    pts_outside = []
    zone_pts_px = None
    is_zone_active = False

    if zone_polygon is not None and len(zone_polygon) >= 3:
        try:
            zone_pts_px = np.array([[int(p[0] * w), int(p[1] * h)] for p in zone_polygon], dtype=np.int32)
            is_zone_active = True
        except Exception:
            is_zone_active = False

    if is_zone_active and len(result.points) > 0:
        for pt in result.points:
            px, py = float(pt[0]), float(pt[1])
            if cv2.pointPolygonTest(zone_pts_px, (px, py), False) >= 0:
                pts_inside.append(pt)
            else:
                pts_outside.append(pt)
        pts_inside = np.array(pts_inside, dtype=np.float32) if len(pts_inside) > 0 else np.zeros((0, 2), dtype=np.float32)
        pts_outside = np.array(pts_outside, dtype=np.float32) if len(pts_outside) > 0 else np.zeros((0, 2), dtype=np.float32)
        zone_count = len(pts_inside)
    else:
        pts_inside = result.points
        pts_outside = np.zeros((0, 2), dtype=np.float32)
        zone_count = total_count

    # Render Polygon ROI Overlay if active
    if is_zone_active and zone_pts_px is not None:
        overlay = out.copy()
        cv2.fillPoly(overlay, [zone_pts_px], (255, 230, 0)) # Soft translucent cyan/yellow fill
        cv2.addWeighted(overlay, 0.22, out, 0.78, 0, out)
        cv2.polylines(out, [zone_pts_px], isClosed=True, color=(0, 242, 255), thickness=max(2, int(2 * scale)))

        # Draw ROI Zone Header Tag
        z_label = zone_name or "Zone"
        min_x = int(np.min(zone_pts_px[:, 0]))
        min_y = int(np.min(zone_pts_px[:, 1]))
        cv2.putText(out, f"ZONE '{z_label.upper()}': {zone_count} PPL", (max(10, min_x), max(30, min_y - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6 * scale, (0, 242, 255), max(2, int(scale)), cv2.LINE_AA)

    # Render Heatmap / Boxes / Dots
    if mode == "heatmap" or result.density_map is not None:
        d_map = result.density_map
        if d_map is None:
            grid = np.zeros((h, w), dtype=np.float32)
            if len(pts_inside) > 0:
                for pt in pts_inside:
                    px, py = int(round(pt[0])), int(round(pt[1]))
                    if 0 <= px < w and 0 <= py < h:
                        grid[py, px] += 1.0
                ksize = int(round(15.0 * 4)) | 1
                d_map = cv2.GaussianBlur(grid, (ksize, ksize), 15.0)
                total_sum = np.sum(d_map)
                if total_sum > 0:
                    d_map = d_map * (len(pts_inside) / total_sum)
            else:
                d_map = grid
        
        d_max = d_map.max() if d_map.max() > 0 else 1.0
        d_norm = np.clip((d_map / (d_max * 0.5)) * 255.0, 0, 255).astype(np.uint8)
        heatmap = cv2.applyColorMap(d_norm, cv2.COLORMAP_JET)
        out = cv2.addWeighted(out, 0.55, heatmap, 0.45, 0)
        
        for x, y in pts_inside.astype(int):
            cv2.circle(out, (x, y), max(2, int(3 * scale)), (255, 255, 255), -1)

    elif mode == "boxes" and result.boxes is not None:
        for i, (x1, y1, x2, y2) in enumerate(result.boxes.astype(int)):
            cx, cy = (x1 + x2) / 2.0, y1 + (y2 - y1) * 0.25
            is_in_zone = not is_zone_active or (cv2.pointPolygonTest(zone_pts_px, (cx, cy), False) >= 0)
            box_color = (0, 230, 0) if is_in_zone else (100, 100, 100)
            cv2.rectangle(out, (x1, y1), (x2, y2), box_color, thick)
            if result.ids is not None and is_in_zone:
                font_scale = 0.4 * scale
                cv2.putText(out, f"#{result.ids[i]}", (x1, max(int(14 * scale), y1 - 6)),
                            cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0, 230, 0), max(1, int(scale)), cv2.LINE_AA)
    else:
        active_cnt = zone_count if is_zone_active else total_count
        base_r = 4 if active_cnt < 80 else (3 if active_cnt < 300 else 2)
        r = max(2, int(round(base_r * scale)))

        # Points inside ROI Zone
        for x, y in pts_inside.astype(int):
            cv2.circle(out, (x, y), r, (0, 0, 255), -1)
            if r >= 3:
                cv2.circle(out, (x, y), r + max(1, int(scale)), (255, 255, 255), max(1, int(scale)))

        # Points outside ROI Zone (Dimmed Gray)
        if is_zone_active and len(pts_outside) > 0:
            for x, y in pts_outside.astype(int):
                cv2.circle(out, (x, y), max(2, r - 1), (100, 100, 100), -1)

    # HUD Bar
    hud_h = int(48 * scale)
    cv2.rectangle(out, (0, 0), (w, hud_h), (0, 0, 0), -1)
    
    font_main = 0.8 * scale
    font_sub = 0.55 * scale
    y_main = int(32 * scale)
    
    # Calculate occupancy & crowd density status level
    occ_cnt = zone_count if is_zone_active else total_count
    occ_pct = min(100, int(round((occ_cnt / max(1, capacity)) * 100)))
    if occ_pct < 35:
        status_str = f"LOW ({occ_pct}%)"
        status_color = (0, 255, 0)       # Green
    elif occ_pct < 75:
        status_str = f"MODERATE ({occ_pct}%)"
        status_color = (0, 215, 255)     # Yellow/Cyan
    else:
        status_str = f"HIGH CROWD ({occ_pct}%)"
        status_color = (0, 0, 255)       # Red Warning

    if is_zone_active:
        hud_text = f"{location_name.upper()} | TOTAL: {total_count} | [{zone_name or 'Zone'}: {zone_count}/{capacity}] [{status_str}]"
    else:
        hud_text = f"{location_name.upper()} | {total_count}/{capacity}  [{status_str}]"

    cv2.putText(out, hud_text, (int(12 * scale), y_main),
                cv2.FONT_HERSHEY_SIMPLEX, font_main, status_color, max(2, int(round(2 * scale))), cv2.LINE_AA)
    
    # Right text: Detector stats
    stats_str = f"{detector_name.upper()}  |  {infer_ms:5.1f} ms  |  {fps:4.1f} FPS"
    (text_w, _), _ = cv2.getTextSize(stats_str, cv2.FONT_HERSHEY_SIMPLEX, font_sub, max(1, int(scale)))
    x_stats = max(int(240 * scale), w - text_w - int(12 * scale))
    cv2.putText(out, stats_str, (x_stats, y_main),
                cv2.FONT_HERSHEY_SIMPLEX, font_sub, (200, 200, 200), max(1, int(scale)), cv2.LINE_AA)
                
    return out, total_count, (zone_count if is_zone_active else None)


CV_LOCK = threading.Lock()


import queue
from detectors import Result, build_detector, clear_gpu_memory


class Pipeline:
    """Owns the camera and the active detector; all mutation happens under a lock
    so the worker never reads a half-swapped configuration."""

    def __init__(self, source=DEFAULT_SOURCE, detector="yolo"):
        self.lock = threading.Lock()
        self.source = source
        self.detector_kind = detector
        self.render_mode = "boxes"
        self.zone_polygon = None # Optional normalized 2D ROI shape points [[x, y], ...]
        self.zone_name = None
        self.total_count = 0
        self.zone_count = None
        
        # Location metadata & camera ID
        self.camera_id = "cam_03"
        self.location = "Railway Station - Platform 1"
        self.capacity = 800
        
        # Track estimated counts across cameras for dynamic ranking
        self.camera_counts = {
            "cam_01": 22,   # Bus Terminal Gate A
            "cam_02": 45,   # Bus Terminal Gate B
            "cam_03": 650,  # Platform 1
            "cam_04": 85,   # Metro Concourse
        }

        with CV_LOCK:
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

        # Async Queue worker thread for 100% stable non-blocking AI inference
        self.latest_result = Result()
        self.infer_queue = queue.Queue(maxsize=1)
        threading.Thread(target=self._worker_loop, daemon=True).start()

    def _get_detector(self, kind):
        if kind not in self._detectors:
            clear_gpu_memory()
            self._detectors[kind] = build_detector(kind)
        return self._detectors[kind]

    def _note_source(self, source):
        """Record whether we are on a live camera or a file, plus the file's
        length and native rate, which drive looping and playback pacing."""
        self.is_video = not is_device_source(source)
        with CV_LOCK:
            self.video_fps = float(self.cap.get(cv2.CAP_PROP_FPS)) if self.is_video else 0.0
            if not (0 < self.video_fps < 240):      # some containers report 0 or nonsense
                self.video_fps = 25.0
            self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT)) if self.is_video else 0
        self.pos_frame = 0

    def configure(self, source=None, detector=None, render_mode=None,
                  camera_id=None, location=None, capacity=None,
                  conf=None, imgsz=None, threshold=None, sigma=None, track=None,
                  zone_polygon=None, zone_name=None, **kwargs):
        with self.lock:
            if "zone_polygon" in kwargs or zone_polygon is not None:
                self.zone_polygon = zone_polygon
            if "zone_name" in kwargs or zone_name is not None:
                self.zone_name = zone_name
            if location is not None:
                self.location = str(location)
            if capacity is not None:
                self.capacity = int(capacity)

            if camera_id is not None and camera_id in VIRTUAL_CAMERAS:
                cam_meta = VIRTUAL_CAMERAS[camera_id]
                self.camera_id = camera_id
                if location is None:
                    self.location = cam_meta["location"]
                if capacity is None:
                    self.capacity = cam_meta["capacity"]
                source = cam_meta["source"]

            if source is not None and source != self.source:
                with CV_LOCK:
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

    def get_rankings(self):
        """Rank all monitored locations from Least Crowded (Best option) to Most Crowded."""
        rankings = []
        for cid, meta in VIRTUAL_CAMERAS.items():
            cnt = self.count if cid == self.camera_id else self.camera_counts.get(cid, 0)
            cap = meta["capacity"]
            occ = min(100, int(round((cnt / max(1, cap)) * 100)))
            status = "LOW" if occ < 35 else ("MODERATE" if occ < 75 else "HIGH")
            rankings.append({
                "camera_id": cid,
                "location": meta["location"],
                "count": cnt,
                "capacity": cap,
                "occupancy_pct": occ,
                "status": status,
                "source": meta["source"]
            })
        # Sort ascending by occupancy percentage (least crowded first)
        rankings.sort(key=lambda x: x["occupancy_pct"])
        if rankings:
            rankings[0]["recommended"] = True
        return rankings

    def state(self):
        with self.lock:
            d = self.detector
            active_render = self.render_mode
            if not getattr(d, "supports_boxes", False) and active_render == "boxes":
                active_render = "dots"
            
            occ_pct = min(100, int(round((self.count / max(1, self.capacity)) * 100)))
            density_status = "LOW" if occ_pct < 35 else ("MODERATE" if occ_pct < 75 else "HIGH CONGESTION")
            
            # Keep current active camera count updated
            self.camera_counts[self.camera_id] = self.count
            
            return {
                "camera_id": self.camera_id,
                "location": self.location,
                "capacity": self.capacity,
                "occupancy_pct": occ_pct,
                "source": self.source,
                "detector": self.detector_kind,
                "render_mode": active_render,
                "supports_boxes": getattr(d, "supports_boxes", False),
                "supports_heatmap": getattr(d, "supports_heatmap", True),
                "count": self.count,
                "total_count": self.total_count,
                "zone_count": self.zone_count,
                "zone_name": self.zone_name,
                "zone_polygon": self.zone_polygon,
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
                "rankings": self.get_rankings()
            }

    def _worker_loop(self):
        while self._running:
            try:
                frame, det, mode, name, loc, cap_limit = self.infer_queue.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                t0 = time.perf_counter()
                res = det.infer(frame)
                ms = (time.perf_counter() - t0) * 1000

                active_mode = mode
                if not getattr(det, "supports_boxes", False) and active_mode == "boxes":
                    active_mode = "dots"

                # Render detection points & calculate zone ROI count
                annotated, tot_cnt, z_cnt = render(frame, res, active_mode, name, self.fps, ms,
                                                   location_name=loc, capacity=cap_limit,
                                                   zone_polygon=self.zone_polygon,
                                                   zone_name=self.zone_name)
                
                with self.lock:
                    if res is not None:
                        self.latest_result = res
                        self.count = z_cnt if z_cnt is not None else tot_cnt
                        self.total_count = tot_cnt
                        self.zone_count = z_cnt
                    self.infer_ms = ms

                ok, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 80])
                if ok:
                    with self.lock:
                        self.latest_jpeg = buf.tobytes()
                        self.frame_seq += 1
            finally:
                self.infer_queue.task_done()

    def run(self):
        while self._running:
            if auditor and auditor.is_running:
                time.sleep(0.05)
                continue

            tick = time.perf_counter()
            with self.lock:
                cap, det, mode, name = self.cap, self.detector, self.render_mode, self.detector_kind
                is_video, vfps = self.is_video, self.video_fps
                loc, cap_limit = self.location, self.capacity

            with CV_LOCK:
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

            # Normalize frame resolution to max 960px width for fast processing
            h, w = frame.shape[:2]
            if w > 960:
                scale = 960.0 / w
                frame_scaled = cv2.resize(frame, (960, int(h * scale)))
            else:
                frame_scaled = frame

            self._times.append(time.time())
            if len(self._times) > 1:
                self.fps = (len(self._times) - 1) / (self._times[-1] - self._times[0])

            # Push frame to worker queue for frame-synchronized AI inference & rendering
            try:
                self.infer_queue.put_nowait((frame_scaled, det, mode, name, loc, cap_limit))
            except queue.Full:
                pass

            # Pacing for video files to guarantee smooth playback rate
            if is_video and vfps > 0:
                target_dt = 1.0 / vfps
                elapsed = time.perf_counter() - tick
                if elapsed < target_dt:
                    time.sleep(target_dt - elapsed)

    def stop(self):
        self._running = False


class SequentialAuditManager:
    """Manages sequential multi-camera crowd scanning and timestamped flow logging."""
    def __init__(self):
        self.lock = threading.Lock()
        self.is_running = False
        self.current_camera = None
        self.progress_pct = 0
        self.sample_interval_ms = 10  # configurable sampling step in ms
        self.latest_live_log = None
        self.audit_results = {}
        self.verdict = None

    def start_audit(self, items=None, sample_interval_ms=10):
        with self.lock:
            if self.is_running:
                return False
            self.is_running = True
            self.sample_interval_ms = max(5, int(sample_interval_ms))
            self.progress_pct = 0
            self.latest_live_log = None
            self.audit_results = {}
            self.verdict = None

        if not items:
            items = [
                {
                    "camera_id": cid,
                    "location": meta["location"],
                    "capacity": meta["capacity"],
                    "source": meta["source"],
                    "detector": "yolo"
                }
                for cid, meta in VIRTUAL_CAMERAS.items()
            ]

        threading.Thread(target=self._run_audit_sequence, args=(items,), daemon=True).start()
        return True

    def _run_audit_sequence(self, feeds):
        total_feeds = len(feeds)

        for idx, feed in enumerate(feeds):
            cid = feed.get("camera_id") or f"feed_{idx+1}"
            loc = feed.get("location", f"Location {idx+1}")
            cap_limit = int(feed.get("capacity", 500))
            src = feed.get("source")
            det_kind = feed.get("detector", "yolo")

            with self.lock:
                self.current_camera = loc
                self.progress_pct = int((idx / max(1, total_feeds)) * 100)

            # Sync live streaming player on screen to current feed & selected detector model!
            if pipeline and src:
                try:
                    pipeline.configure(source=src, detector=det_kind, location=loc, capacity=cap_limit)
                except Exception:
                    pass

            det = pipeline._get_detector(det_kind) if pipeline else build_detector(det_kind)
            with CV_LOCK:
                cap = cv2.VideoCapture(src) if src else None
                is_ok = cap is not None and cap.isOpened()
                if is_ok:
                    cap_total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    vfps = float(cap.get(cv2.CAP_PROP_FPS))
                    if not (0 < vfps < 240):
                        vfps = 25.0

            if not is_ok:
                continue

            # Step interval in frames based on requested sample_interval_ms
            step_frames = max(1, int((self.sample_interval_ms / 1000.0) * vfps))
            
            logs = []
            frame_idx = 0
            start_time = datetime.datetime.now()
            max_frames = cap_total if cap_total > 0 else 180

            while frame_idx < max_frames:
                with CV_LOCK:
                    if not cap.isOpened():
                        break
                    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                    ok, frame = cap.read()
                if not ok:
                    break

                # Downscale frame for speed & low memory
                h, w = frame.shape[:2]
                if w > 960:
                    scale = 960.0 / w
                    frame_scaled = cv2.resize(frame, (960, int(h * scale)))
                else:
                    frame_scaled = frame

                try:
                    res = det.infer(frame_scaled)
                    cnt = res.count
                except Exception:
                    res = Result()
                    cnt = 0

                occ = min(100, int(round((cnt / max(1, cap_limit)) * 100)))
                status = "LOW" if occ < 35 else ("MODERATE" if occ < 75 else "HIGH")
                t_stamp = (start_time + datetime.timedelta(milliseconds=frame_idx * (1000.0 / vfps))).strftime("%H:%M:%S.%f")[:-3]

                # Render annotated frame directly to screen live player
                if pipeline:
                    pipeline.location = loc
                    pipeline.capacity = cap_limit
                    pipeline.count = cnt
                    annotated = render(frame_scaled, res, "boxes" if getattr(det, "supports_boxes", False) else "dots",
                                       det_kind, vfps, 10.0, location_name=loc, capacity=cap_limit)
                    ok_enc, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 80])
                    if ok_enc:
                        pipeline.latest_jpeg = buf.tobytes()
                        pipeline.frame_seq += 1

                log_entry = {
                    "timestamp": t_stamp,
                    "frame": frame_idx,
                    "count": cnt,
                    "occupancy_pct": occ,
                    "status": status,
                    "model": det_kind.upper()
                }
                logs.append(log_entry)

                with self.lock:
                    self.progress_pct = int(((idx + (frame_idx / max(1, max_frames))) / max(1, total_feeds)) * 100)
                    self.latest_live_log = {
                        "location": loc,
                        "feed_index": idx + 1,
                        "total_feeds": total_feeds,
                        "log": log_entry
                    }

                frame_idx += step_frames
                time.sleep(0.015) # Pacing so user watches live model output on screen!

            with CV_LOCK:
                cap.release()

            if logs:
                counts = [l["count"] for l in logs]
                occs = [l["occupancy_pct"] for l in logs]
                avg_cnt = int(round(np.mean(counts)))
                max_cnt = int(np.max(counts))
                avg_occ = int(round(np.mean(occs)))
                peak_occ = int(np.max(occs))

                with self.lock:
                    self.audit_results[cid] = {
                        "camera_id": cid,
                        "location": loc,
                        "capacity": cap_limit,
                        "detector": det_kind,
                        "source": src,
                        "avg_count": avg_cnt,
                        "max_count": max_cnt,
                        "avg_occupancy_pct": avg_occ,
                        "peak_occupancy_pct": peak_occ,
                        "status": "LOW" if avg_occ < 35 else ("MODERATE" if avg_occ < 75 else "HIGH"),
                        "sample_count": len(logs),
                        "logs": logs
                    }

        # Calculate Final Verdict Report & Conclusion
        with self.lock:
            self.progress_pct = 100
            self.is_running = False
            self.current_camera = None

            if self.audit_results:
                sorted_results = sorted(self.audit_results.values(), key=lambda x: x["avg_occupancy_pct"])
                best = sorted_results[0]
                worst = sorted_results[-1]

                self.verdict = {
                    "best_location": best["location"],
                    "best_avg_occupancy": best["avg_occupancy_pct"],
                    "best_detector": best["detector"].upper(),
                    "worst_location": worst["location"],
                    "worst_peak_occupancy": worst["peak_occupancy_pct"],
                    "recommendation": f"🏆 RECOMMENDED OPTION: {best['location']} (Avg Occupancy: {best['avg_occupancy_pct']}%, Model: {best['detector'].upper()}). Avoid {worst['location']} (Peak Occupancy: {worst['peak_occupancy_pct']}%).",
                    "sorted_summary": sorted_results
                }

    def state(self):
        with self.lock:
            return {
                "is_running": self.is_running,
                "current_camera": self.current_camera,
                "progress_pct": self.progress_pct,
                "sample_interval_ms": self.sample_interval_ms,
                "latest_live_log": self.latest_live_log,
                "verdict": self.verdict,
                "audit_results": self.audit_results
            }


import datetime

app = FastAPI()
pipeline_1: Optional[Pipeline] = None
pipeline_2: Optional[Pipeline] = None
auditor = SequentialAuditManager()


@app.get("/", response_class=HTMLResponse)
def index():
    return (HERE / "static" / "index.html").read_text()


@app.get("/api/sources")
def api_sources():
    cams = [c for c in list_cameras(probe=True, assume_working=pipeline_1.source if pipeline_1 else DEFAULT_SOURCE) if c["works"]]
    cam_opts = [{"value": c["stable_path"] or str(c["index"]),
                 "label": f"{c['index']}: {c['name']}"} for c in cams]

    vcam_opts = [{"camera_id": cid, "value": meta["source"], "label": meta["label"], "location": meta["location"], "capacity": meta["capacity"]}
                 for cid, meta in VIRTUAL_CAMERAS.items()]

    videos_dir = HERE / "videos"
    video_opts = []
    for d, tag in [(videos_dir, "Sample"), (UPLOADS, "Uploaded")]:
        if d.exists():
            for f in sorted(d.iterdir()):
                if f.is_file() and f.suffix.lower() in VIDEO_EXTS:
                    video_opts.append({"value": str(f.resolve()), "label": f"[{tag}] {f.name}"})

    return JSONResponse({"virtual_cameras": vcam_opts, "cameras": cam_opts, "videos": video_opts})


@app.get("/api/cameras")
def api_cameras():
    sources = api_sources()
    import json
    data = json.loads(sources.body)
    return JSONResponse(data["cameras"] + data["videos"])


@app.post("/api/cameras/assign")
async def api_assign_camera(data: dict):
    cid = data.get("camera_id") or f"cam_{len(VIRTUAL_CAMERAS)+1:02d}"
    loc = data.get("location", "Custom Location")
    cap = int(data.get("capacity", 500))
    src = data.get("source")
    stream_num = data.get("stream", 1)
    
    VIRTUAL_CAMERAS[cid] = {
        "camera_id": cid,
        "location": loc,
        "capacity": cap,
        "source": src,
        "label": f"📷 {cid}: {loc} (Cap: {cap})"
    }
    target_pipe = pipeline_1 if stream_num == 1 else pipeline_2
    if target_pipe:
        target_pipe.configure(camera_id=cid)
    return JSONResponse({"ok": True, "camera_id": cid, "virtual_cameras": VIRTUAL_CAMERAS})


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
        if pipeline_1:
            pipeline_1.configure(source=str(dest.resolve()))
    except Exception as exc:
        return JSONResponse({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, status_code=400)

    return JSONResponse({"ok": True, "source": str(dest.resolve())})


class TransitSimulationState:
    """Holds separate simulation state for Stream 1 and Stream 2 injected from Portal 3."""
    def __init__(self):
        self.lock = threading.Lock()
        self.s1 = {
            "vehicle_occupancy": 30,  # % full
            "vehicle_eta": 5,          # mins
            "boarding_rate": 40,       # passengers/min
            "alighting_rate": 15       # passengers/min
        }
        self.s2 = {
            "vehicle_occupancy": 85,  # % full
            "vehicle_eta": 3,          # mins
            "boarding_rate": 120,      # passengers/min
            "alighting_rate": 20       # passengers/min
        }
        self.scenario_name = "Standard Transit Peak Flow"

    def state(self):
        with self.lock:
            return {
                "s1": dict(self.s1),
                "s2": dict(self.s2),
                "scenario_name": self.scenario_name
            }

    def update(self, data: dict):
        with self.lock:
            stream_target = int(data.get("stream", 1))
            target = self.s1 if stream_target == 1 else self.s2
            if "vehicle_occupancy" in data:
                target["vehicle_occupancy"] = int(data["vehicle_occupancy"])
            if "vehicle_eta" in data:
                target["vehicle_eta"] = int(data["vehicle_eta"])
            if "boarding_rate" in data:
                target["boarding_rate"] = int(data["boarding_rate"])
            if "alighting_rate" in data:
                target["alighting_rate"] = int(data["alighting_rate"])
            if "scenario_name" in data:
                self.scenario_name = str(data["scenario_name"])


class CrowdTrendLogger:
    """Logs historical time-series data for crowd trends & predictive analysis."""
    def __init__(self):
        self.lock = threading.Lock()
        self.history = deque(maxlen=60)  # last 60 snapshot points
        self.last_log_time = 0

    def record(self, s1: dict, s2: dict, sim_state: dict):
        now = time.time()
        if now - self.last_log_time < 3.0:
            return
        self.last_log_time = now

        t_str = datetime.datetime.now().strftime("%H:%M:%S")
        c1 = s1.get("count", 0)
        c2 = s2.get("count", 0)
        cap1 = s1.get("capacity", 1)
        cap2 = s2.get("capacity", 1)
        occ1 = s1.get("occupancy_pct", 0)
        occ2 = s2.get("occupancy_pct", 0)

        net_flow = sim_state.get("boarding_rate", 0) - sim_state.get("alighting_rate", 0)
        pred_c1 = max(0, c1 + int(net_flow * (sim_state.get("inbound_train_eta", 3) / 2.0)))
        pred_occ1 = min(100, int(round((pred_c1 / max(1, cap1)) * 100)))

        entry = {
            "timestamp": t_str,
            "stream1_count": c1,
            "stream1_occ": occ1,
            "stream2_count": c2,
            "stream2_occ": occ2,
            "pred_stream1_occ": pred_occ1,
            "inbound_train_occ": sim_state.get("inbound_train_occupancy", 75)
        }
        with self.lock:
            self.history.append(entry)

    def get_history(self):
        with self.lock:
            return list(self.history)


simulation = TransitSimulationState()
trend_logger = CrowdTrendLogger()


def calc_effective_occ(pipe_state: dict, sim_state: dict):
    """Calculates combined real-time + simulated effective congestion percentage."""
    live_occ = pipe_state.get("occupancy_pct", 0)
    v_occ = sim_state.get("vehicle_occupancy", 50)
    net_flow = sim_state.get("boarding_rate", 50) - sim_state.get("alighting_rate", 20)
    cap = max(1, pipe_state.get("capacity", 100))
    flow_pct = (net_flow / cap) * 100.0 * 0.15
    effective = (live_occ * 0.4) + (v_occ * 0.4) + flow_pct
    return min(100, max(0, int(round(effective))))


def calc_predictive_analytics(s, sim):
    count = s.get("count", 0)
    cap = max(1, s.get("capacity", 100))
    b_rate = sim.get("boarding_rate", 40)
    a_rate = sim.get("alighting_rate", 15)
    net_inflow = b_rate - a_rate
    
    # 1. Overflow Countdown
    rem_cap = max(0, cap - count)
    if net_inflow > 0 and rem_cap > 0:
        overflow_min = round(rem_cap / net_inflow, 1)
        overflow_str = f"⏳ OVERFLOW IN {overflow_min} MINS" if overflow_min <= 15 else "🟢 STABLE (No Overflow Forecasted)"
    elif rem_cap <= 0:
        overflow_min = 0.0
        overflow_str = "🚨 CRITICAL: MAXIMUM CAPACITY!"
    else:
        overflow_min = 999.0
        overflow_str = "🟢 STABLE (Net Outflow)"

    # 2. Stranded Passenger Index
    v_occ_pct = sim.get("vehicle_occupancy", 75)
    v_total_cap = 200 if "Bus" in s.get("location", "") else 1000
    v_avail_seats = max(0, int(round(v_total_cap * (1.0 - (v_occ_pct / 100.0)))))
    stranded = max(0, count - v_avail_seats)
    
    return {
        "overflow_countdown_min": overflow_min,
        "overflow_status": overflow_str,
        "stranded_count": stranded,
        "v_avail_seats": v_avail_seats,
        "relief_buses_needed": (stranded + 44) // 45 if stranded > 0 else 0
    }


@app.get("/api/state")
def api_state():
    s1 = pipeline_1.state() if pipeline_1 else {}
    s2 = pipeline_2.state() if pipeline_2 else {}
    sim = simulation.state()
    trend_logger.record(s1, s2, sim)
    
    sim1 = sim.get("s1", {})
    sim2 = sim.get("s2", {})
    eff_occ1 = calc_effective_occ(s1, sim1)
    eff_occ2 = calc_effective_occ(s2, sim2)

    s1["effective_occ_pct"] = eff_occ1
    s2["effective_occ_pct"] = eff_occ2

    s1["explanation"] = f"Includes Live Camera ({s1.get('occupancy_pct',0)}%) + Incoming Transit ({sim1.get('vehicle_occupancy',0)}% Full)"
    s2["explanation"] = f"Includes Live Camera ({s2.get('occupancy_pct',0)}%) + Incoming Transit ({sim2.get('vehicle_occupancy',0)}% Full)"

    s1["analytics"] = calc_predictive_analytics(s1, sim1)
    s2["analytics"] = calc_predictive_analytics(s2, sim2)

    loc1 = s1.get("location", "Location 1")
    loc2 = s2.get("location", "Location 2")
    
    if eff_occ1 <= eff_occ2:
        rec = f"🏆 RECOMMENDED ROUTE: {loc1} ({eff_occ1}% Effective Congestion, Inbound Transit {sim1.get('vehicle_occupancy',0)}% Full) is LEAST CROWDED vs {loc2} ({eff_occ2}% Effective Congestion, Inbound Transit {sim2.get('vehicle_occupancy',0)}% Full)."
    else:
        rec = f"🏆 RECOMMENDED ROUTE: {loc2} ({eff_occ2}% Effective Congestion, Inbound Transit {sim2.get('vehicle_occupancy',0)}% Full) is LEAST CROWDED vs {loc1} ({eff_occ1}% Effective Congestion, Inbound Transit {sim1.get('vehicle_occupancy',0)}% Full)."

    return JSONResponse({
        "stream1": s1,
        "stream2": s2,
        "recommendation": rec,
        "simulation": sim,
        "audit": auditor.state()
    })


@app.get("/api/trends")
def api_trends():
    return JSONResponse({"history": trend_logger.get_history()})


@app.get("/api/passenger/status")
def api_passenger_status(selected_stream: int = 1, destination: str = "csmt"):
    s1 = pipeline_1.state() if pipeline_1 else {}
    s2 = pipeline_2.state() if pipeline_2 else {}
    sim = simulation.state()

    sim1 = sim.get("s1", {})
    sim2 = sim.get("s2", {})

    eff1 = calc_effective_occ(s1, sim1)
    eff2 = calc_effective_occ(s2, sim2)

    dest_map = {
        "csmt": {"bus_travel": 22, "train_travel": 14, "label": "CSMT Station"},
        "dadar": {"bus_travel": 18, "train_travel": 10, "label": "Dadar Center"},
        "andheri": {"bus_travel": 25, "train_travel": 15, "label": "Andheri Hub"},
        "thane": {"bus_travel": 45, "train_travel": 28, "label": "Thane Junction"}
    }
    d_info = dest_map.get(destination, dest_map["csmt"])

    bus_wait = max(1, int(round(s1.get("count", 0) / 30.0)) + sim1.get("vehicle_eta", 2))
    bus_total = d_info["bus_travel"] + bus_wait

    train_wait = max(1, int(round(s2.get("count", 0) / 40.0)) + sim2.get("vehicle_eta", 3))
    train_total = d_info["train_travel"] + train_wait

    options = [
        {
            "mode": "bus",
            "name": "🚍 Bus Transit Route",
            "location": s1.get("location", "Bus Terminal - Gate A").replace("Stream 1: ", "").replace("Stream 2: ", ""),
            "travel_time": d_info["bus_travel"],
            "wait_time": bus_wait,
            "total_time": bus_total,
            "occupancy_pct": eff1,
            "count": s1.get("count", 0),
            "capacity": s1.get("capacity", 120),
            "vehicle_occ": sim1.get("vehicle_occupancy", 30),
            "vehicle_eta": sim1.get("vehicle_eta", 5),
            "status": "HIGH CROWD" if eff1 > 75 else ("MODERATE" if eff1 > 35 else "LOW CROWD"),
            "trend": "-3% Clearing" if sim1.get("alighting_rate",0) > sim1.get("boarding_rate",0) else "+6% Influx",
            "score": bus_total + (eff1 * 0.25)
        },
        {
            "mode": "train",
            "name": "🚆 Local Rail Line",
            "location": s2.get("location", "Railway Station - Platform 1").replace("Stream 1: ", "").replace("Stream 2: ", ""),
            "travel_time": d_info["train_travel"],
            "wait_time": train_wait,
            "total_time": train_total,
            "occupancy_pct": eff2,
            "count": s2.get("count", 0),
            "capacity": s2.get("capacity", 800),
            "vehicle_occ": sim2.get("vehicle_occupancy", 85),
            "vehicle_eta": sim2.get("vehicle_eta", 3),
            "status": "HIGH CROWD" if eff2 > 75 else ("MODERATE" if eff2 > 35 else "LOW CROWD"),
            "trend": "+12% Heavy Surge" if sim2.get("boarding_rate",0) > 80 else "Stable",
            "score": train_total + (eff2 * 0.25)
        }
    ]

    # Unified single ranking rule: lowest composite score (time + weighted crowd) wins!
    options = sorted(options, key=lambda x: x["score"])
    best_opt = options[0]
    worst_opt = options[-1]

    # Only 1 single route gets the BEST badge
    options[0]["is_best"] = True
    options[1]["is_best"] = False

    return JSONResponse({
        "destination_label": d_info["label"],
        "options": options,
        "recommended_best": {
            "mode": best_opt["mode"],
            "name": best_opt["name"],
            "location": best_opt["location"],
            "total_time": best_opt["total_time"],
            "savings_min": max(0, worst_opt["total_time"] - best_opt["total_time"]),
            "occupancy_pct": best_opt["occupancy_pct"],
            "reason": f"Saves {max(0, worst_opt['total_time'] - best_opt['total_time'])} mins total over slower/crowded route with lowest congestion score."
        }
    })


@app.post("/api/config")
async def api_config(cfg: dict):
    stream_id = int(cfg.pop("stream", 1))
    target_pipe = pipeline_1 if stream_id == 1 else pipeline_2
    try:
        if target_pipe:
            target_pipe.configure(**cfg)
    except Exception as exc:
        print("CONFIG ERROR:", exc)
        return JSONResponse({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, 400)

    s1 = pipeline_1.state() if pipeline_1 else {}
    s2 = pipeline_2.state() if pipeline_2 else {}
    occ1 = s1.get("occupancy_pct", 0)
    occ2 = s2.get("occupancy_pct", 0)
    loc1 = s1.get("location", "Location 1")
    loc2 = s2.get("location", "Location 2")
    if occ1 <= occ2:
        rec = f"🏆 RECOMMENDED ROUTE: {loc1} ({occ1}% Occupancy, {s1.get('count',0)}/{s1.get('capacity',1)} people) is LEAST CROWDED vs {loc2} ({occ2}% Occupancy, {s2.get('count',0)}/{s2.get('capacity',1)} people)."
    else:
        rec = f"🏆 RECOMMENDED ROUTE: {loc2} ({occ2}% Occupancy, {s2.get('count',0)}/{s2.get('capacity',1)} people) is LEAST CROWDED vs {loc1} ({occ1}% Occupancy, {s1.get('count',0)}/{s1.get('capacity',1)} people)."

    return JSONResponse({"ok": True, "stream1": s1, "stream2": s2, "recommendation": rec})


@app.post("/api/simulation/update")
async def api_simulation_update(data: dict):
    simulation.update(data)
    return JSONResponse({"ok": True, "simulation": simulation.state()})


def mjpeg(pipe: Pipeline):
    """Emit each encoded frame exactly once for the specified pipeline."""
    last_seq = -1
    while True:
        if pipe is None:
            time.sleep(0.01)
            continue
        seq = pipe.frame_seq
        if seq == last_seq or pipe.latest_jpeg is None:
            time.sleep(0.005)
            continue
        last_seq = seq
        buf = pipe.latest_jpeg
        yield (b"--" + BOUNDARY.encode() + b"\r\nContent-Type: image/jpeg\r\n"
               b"Content-Length: " + str(len(buf)).encode() + b"\r\n\r\n" + buf + b"\r\n")


@app.get("/stream.mjpg")
@app.get("/stream1.mjpg")
def stream1():
    return StreamingResponse(mjpeg(pipeline_1), media_type=f"multipart/x-mixed-replace; boundary={BOUNDARY}")


@app.get("/stream2.mjpg")
def stream2():
    return StreamingResponse(mjpeg(pipeline_2), media_type=f"multipart/x-mixed-replace; boundary={BOUNDARY}")


def main():
    global pipeline_1, pipeline_2
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--host", default="127.0.0.1", help="0.0.0.0 to expose on the LAN")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--source1", default=VIRTUAL_CAMERAS["cam_01"]["source"])
    p.add_argument("--source2", default=VIRTUAL_CAMERAS["cam_03"]["source"])
    p.add_argument("--detector", default="p2pnet", choices=["yolo", "p2pnet", "density"])
    args = p.parse_args()

    pipeline_1 = Pipeline(args.source1, args.detector)
    pipeline_1.configure(camera_id="cam_01")
    threading.Thread(target=pipeline_1.run, daemon=True).start()

    pipeline_2 = Pipeline(args.source2, args.detector)
    pipeline_2.configure(camera_id="cam_03")
    threading.Thread(target=pipeline_2.run, daemon=True).start()

    print(f"\n  open http://{'localhost' if args.host=='127.0.0.1' else args.host}:{args.port}\n")
    try:
        uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    finally:
        pipeline_1.stop()
        pipeline_2.stop()


if __name__ == "__main__":
    main()
