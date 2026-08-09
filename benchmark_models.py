"""Compare YOLO variants on the same footage: speed vs. what they actually count.

Point it at a recorded clip so every model sees identical frames -- comparing on
a live webcam is meaningless because each model sees a different scene.

  python benchmark_models.py --source clip.mp4
  python benchmark_models.py --source clip.mp4 --models yolo11s.pt yolo11m.pt --imgsz 640 1280
"""

import argparse
import statistics
import time

import cv2
from ultralytics import YOLO

PERSON_CLASS = 0


def parse_args():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--source", required=True, help="video file (use record_clip.py to make one)")
    p.add_argument("--models", nargs="+",
                   default=["yolo11n.pt", "yolo11s.pt", "yolo11m.pt", "yolo11l.pt"])
    p.add_argument("--imgsz", nargs="+", type=int, default=[640])
    p.add_argument("--conf", type=float, default=0.35)
    p.add_argument("--iou", type=float, default=0.7)
    p.add_argument("--device", default="0")
    p.add_argument("--max-frames", type=int, default=300)
    p.add_argument("--truth", type=float, default=None,
                   help="known number of people in the clip; enables a count-error column")
    return p.parse_args()


def read_frames(source, limit):
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise SystemExit(f"could not open {source!r}")
    frames = []
    while len(frames) < limit:
        ok, f = cap.read()
        if not ok:
            break
        frames.append(f)
    cap.release()
    if not frames:
        raise SystemExit(f"no frames read from {source!r}")
    return frames


def run_one(model, frames, imgsz, args):
    counts, times = [], []
    # One untimed pass warms up CUDA context and cuDNN autotuning; without it
    # the first model measured looks artificially slow.
    model.predict(frames[0], imgsz=imgsz, conf=args.conf, iou=args.iou,
                  classes=[PERSON_CLASS], device=args.device, half=True, verbose=False)
    for f in frames:
        t0 = time.perf_counter()
        r = model.predict(f, imgsz=imgsz, conf=args.conf, iou=args.iou,
                          classes=[PERSON_CLASS], device=args.device, half=True, verbose=False)
        times.append((time.perf_counter() - t0) * 1000)
        counts.append(0 if r[0].boxes is None else len(r[0].boxes))
    return counts, times


def main():
    args = parse_args()
    frames = read_frames(args.source, args.max_frames)
    print(f"{len(frames)} frames from {args.source}\n")

    header = f"{'model':<14}{'imgsz':>6}{'ms':>8}{'FPS':>7}{'med':>6}{'min':>5}{'max':>5}{'flick':>7}"
    if args.truth is not None:
        header += f"{'MAE':>7}"
    print(header)
    print("-" * len(header))

    for name in args.models:
        model = YOLO(name)
        for imgsz in args.imgsz:
            counts, times = run_one(model, frames, imgsz, args)
            ms = statistics.mean(times)
            changes = sum(1 for a, b in zip(counts, counts[1:]) if a != b)
            flicker = 100 * changes / max(1, len(counts) - 1)
            row = (f"{name:<14}{imgsz:>6}{ms:>8.1f}{1000 / ms:>7.1f}"
                   f"{int(statistics.median(counts)):>6}{min(counts):>5}{max(counts):>5}{flicker:>6.0f}%")
            if args.truth is not None:
                mae = sum(abs(c - args.truth) for c in counts) / len(counts)
                row += f"{mae:>7.2f}"
            print(row)

    print("\nmed/min/max = people counted per frame.  flick = % of frames where the")
    print("count changed; on footage with a fixed number of people that is pure error.")
    if args.truth is None:
        print("Pass --truth N (actual people in the clip) to get mean absolute count error.")


if __name__ == "__main__":
    main()
