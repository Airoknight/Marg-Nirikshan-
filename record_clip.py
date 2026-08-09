"""Record a raw clip from the webcam to benchmark against.

Record footage of the real scene -- real people, real angle, real lighting --
then every model in benchmark_models.py is scored on identical frames.

  python record_clip.py --seconds 30 --out clip.mp4
"""

import argparse
import time

import cv2

from camera import DEFAULT_SOURCE, open_capture


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--source", default=DEFAULT_SOURCE,
                   help="camera index or /dev/... path; defaults to DEFAULT_SOURCE in camera.py")
    p.add_argument("--out", default="clip.mp4")
    p.add_argument("--seconds", type=float, default=30)
    p.add_argument("--fps", type=float, default=25)
    p.add_argument("--width", type=int, default=1280)
    p.add_argument("--height", type=int, default=720)
    p.add_argument("--headless", action="store_true")
    args = p.parse_args()

    cap = open_capture(args.source, args.width, args.height)

    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    writer = cv2.VideoWriter(args.out, cv2.VideoWriter_fourcc(*"mp4v"), args.fps, (w, h))
    print(f"recording {w}x{h} -> {args.out} for {args.seconds:.0f}s (q to stop early)")

    t_end = time.time() + args.seconds
    n = 0
    while time.time() < t_end:
        ok, frame = cap.read()
        if not ok:
            break
        writer.write(frame)
        n += 1
        if not args.headless:
            left = t_end - time.time()
            preview = frame.copy()
            cv2.putText(preview, f"REC {left:4.1f}s", (20, 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3, cv2.LINE_AA)
            cv2.imshow("recording  [q to stop]", preview)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    cap.release()
    writer.release()
    cv2.destroyAllWindows()
    print(f"wrote {n} frames to {args.out}")


if __name__ == "__main__":
    main()


