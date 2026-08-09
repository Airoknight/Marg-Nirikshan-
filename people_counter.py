"""Live people counter: YOLO person detection + optional ByteTrack.

Examples
--------
  # live view, built-in webcam
  python people_counter.py

  # external webcam once plugged in, higher res, bigger model
  python people_counter.py --source 2 --model yolo11m.pt --imgsz 1280

  # headless smoke test, dump annotated frames to look at afterwards
  python people_counter.py --headless --max-frames 150 --save-frames out/frames
"""

import argparse
import statistics
import time
from collections import deque
from pathlib import Path

import cv2
from ultralytics import YOLO

from camera import DEFAULT_SOURCE, open_capture

PERSON_CLASS = 0  # COCO class id for "person"
WARMUP_FRAMES = 10  # excluded from latency stats; see the timing call below


def parse_args():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--source", default=DEFAULT_SOURCE,
                   help="camera index, /dev/video* path, /dev/v4l/by-id/* symlink, or a "
                        "video file. Defaults to DEFAULT_SOURCE in camera.py. "
                        "Run list_cameras.py to see the options.")
    p.add_argument("--model", default="yolo11s.pt",
                   help="ultralytics weights, e.g. yolo11n/s/m/l.pt (default: yolo11s.pt)")
    p.add_argument("--imgsz", type=int, default=640,
                   help="inference resolution; raise to 960/1280 for small or distant people")
    p.add_argument("--conf", type=float, default=0.35,
                   help="confidence threshold (default: 0.35)")
    p.add_argument("--iou", type=float, default=0.7,
                   help="NMS IoU threshold; raise toward 0.8-0.9 for crowded, overlapping people")
    p.add_argument("--device", default="0", help="'0' for the RTX 4060, or 'cpu'")
    p.add_argument("--half", action="store_true", default=True,
                   help="FP16 inference (default on; Ada handles it natively)")
    p.add_argument("--no-track", dest="track", action="store_false",
                   help="disable ByteTrack and count raw detections instead")
    p.add_argument("--smooth", type=int, default=5,
                   help="median-filter the count over N frames to kill flicker; 1 disables")
    p.add_argument("--cap-width", type=int, default=1280)
    p.add_argument("--cap-height", type=int, default=720)
    p.add_argument("--headless", action="store_true", help="no GUI window")
    p.add_argument("--max-frames", type=int, default=0, help="stop after N frames (0 = unlimited)")
    p.add_argument("--save-video", default="", help="write annotated video to this .mp4")
    p.add_argument("--save-frames", default="",
                   help="directory to dump annotated frames into (every --frame-every frames)")
    p.add_argument("--frame-every", type=int, default=25)
    return p.parse_args()


def draw_hud(frame, lines):
    y = 10
    for text, scale, color in lines:
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, 2)
        cv2.rectangle(frame, (10, y), (10 + tw + 12, y + th + 12), (0, 0, 0), -1)
        cv2.putText(frame, text, (16, y + th + 4),
                    cv2.FONT_HERSHEY_SIMPLEX, scale, color, 2, cv2.LINE_AA)
        y += th + 18


def main():
    args = parse_args()
    model = YOLO(args.model)
    cap = open_capture(args.source, args.cap_width, args.cap_height)

    writer = None
    frames_dir = Path(args.save_frames) if args.save_frames else None
    if frames_dir:
        frames_dir.mkdir(parents=True, exist_ok=True)

    recent = deque(maxlen=max(1, args.smooth))
    latencies = deque(maxlen=60)
    counts_log = []
    n = 0
    t_start = time.time()

    # Shared inference kwargs. classes=[0] restricts the model to "person" --
    # cheaper than post-filtering and stops non-person boxes reaching the tracker.
    kw = dict(imgsz=args.imgsz, conf=args.conf, iou=args.iou, classes=[PERSON_CLASS],
              device=args.device, half=args.half, verbose=False)

    while True:
        ok, frame = cap.read()
        if not ok:
            break

        t0 = time.perf_counter()
        if args.track:
            # persist=True carries track state across calls; ByteTrack's low-score
            # association recovers people through brief occlusion.
            results = model.track(frame, tracker="bytetrack.yaml", persist=True, **kw)
        else:
            results = model.predict(frame, **kw)
        # The first frames pay for CUDA context setup and cuDNN autotuning and can
        # be 10x slower; averaging them in makes short runs look terrible.
        if n >= WARMUP_FRAMES:
            latencies.append((time.perf_counter() - t0) * 1000)

        boxes = results[0].boxes
        raw_count = 0 if boxes is None else len(boxes)
        recent.append(raw_count)
        smooth_count = int(statistics.median(recent))
        counts_log.append((raw_count, smooth_count))

        annotated = results[0].plot()
        hud = [(f"PEOPLE: {smooth_count}", 1.1, (0, 255, 0))]
        if latencies:  # still warming up for the first few frames
            infer_ms = statistics.mean(latencies)
            hud.append((f"raw {raw_count}  |  {infer_ms:5.1f} ms  |  {1000 / infer_ms:4.1f} FPS",
                        0.6, (200, 200, 200)))
        else:
            hud.append((f"raw {raw_count}  |  warming up", 0.6, (200, 200, 200)))
        draw_hud(annotated, hud)

        if args.save_video:
            if writer is None:
                h, w = annotated.shape[:2]
                writer = cv2.VideoWriter(args.save_video,
                                         cv2.VideoWriter_fourcc(*"mp4v"), 25, (w, h))
            writer.write(annotated)
        if frames_dir and n % args.frame_every == 0:
            cv2.imwrite(str(frames_dir / f"frame_{n:05d}_count{smooth_count}.jpg"), annotated)

        if not args.headless:
            cv2.imshow("people counter  [q to quit]", annotated)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

        n += 1
        if args.max_frames and n >= args.max_frames:
            break

    cap.release()
    if writer:
        writer.release()
    if not args.headless:
        cv2.destroyAllWindows()

    if counts_log:
        raws = [c for c, _ in counts_log]
        wall = time.time() - t_start
        changes = sum(1 for a, b in zip(raws, raws[1:]) if a != b)
        print(f"\nframes            {n}  ({n / wall:.1f} FPS end-to-end over {wall:.1f}s)")
        if latencies:
            print(f"inference         {statistics.mean(latencies):.1f} ms avg "
                  f"(first {WARMUP_FRAMES} frames excluded as warmup)")
        print(f"count  min/med/max {min(raws)} / {int(statistics.median(raws))} / {max(raws)}")
        # High flicker on a scene with a stable number of people means the
        # detector is at its confidence boundary -- lower --conf or raise --imgsz.
        print(f"flicker           {changes} count changes ({100 * changes / max(1, n - 1):.0f}% of frames)")


if __name__ == "__main__":
    main()
