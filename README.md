# People counting prototype

Laptop-stage prototype: YOLO person detection + ByteTrack, on an RTX 4060 Laptop GPU (8 GB).
Jetson deployment is deliberately out of scope for now.

## Setup

Always launch via `./run.sh`, never `python` directly. This machine has ROS 2
Humble sourced, which puts `/opt/ros/humble/...` into `PYTHONPATH` — and
`PYTHONPATH` sits *ahead* of the venv's `site-packages` in `sys.path`. A venv
does not filter it, so a colliding package name resolves to the ROS copy.
`run.sh` strips it per-process; your shell's ROS setup is unaffected.

Weights download automatically on first use.

## Cameras

```bash
./run.sh list_cameras.py
```

Each UVC camera exposes two `/dev/video*` nodes; only the first yields frames,
the second is metadata. On this machine:

| src | device | max res | notes |
|-----|--------|---------|-------|
| `0` | Integrated_Webcam_HD | 1280×720 | built-in |
| `2` | Generic HD camera | **640×480** | external USB; lower res than built-in |

```bash
./run.sh people_counter.py --source 0    # internal
./run.sh people_counter.py --source 2    # external
```

Index numbers shift on replug/reboot. For anything you want to keep working,
use the stable by-id path instead:

```bash
./run.sh people_counter.py --source /dev/v4l/by-id/usb-Generic_HD_camera_20181212000000-video-index0
```

## Usage

```bash
# live counter
./run.sh people_counter.py

# record 30s of the real scene to benchmark against
./run.sh record_clip.py --seconds 30 --out clip.mp4

# compare models on identical frames
./run.sh benchmark_models.py --source clip.mp4 --truth 3
```

`--truth N` is the actual number of people in the clip; it turns the comparison into
a real mean-absolute-count-error number instead of a vibe check.

## The knobs that matter, in order

1. **`--imgsz`** — biggest lever for distant or small people. `yolo11s --imgsz 1280`
   usually beats `yolo11l --imgsz 640` on small subjects, and runs faster.
2. **`--conf`** — lower it if people are being missed, raise it if furniture is
   being counted. Default 0.35.
3. **`--iou`** — NMS threshold. Raise toward 0.85 for crowded scenes where
   overlapping people get merged into one box.
4. **Model size** — try last. Usually the smallest real gain per millisecond.

## Reading the output

Both scripts print a `flicker` percentage: how often the count changed between
consecutive frames. On footage with a fixed number of people, **all flicker is
error** — it means detections are sitting right at the confidence boundary.
Fix it with `--imgsz`/`--conf`, not by cranking `--smooth`, which only hides it.

## Known limits of COCO-pretrained YOLO

- **Overhead camera angles** are the common failure. COCO is eye-level
  photography; a ceiling-mounted view is close to out-of-distribution.
- **Heavy occlusion** causes undercounting — NMS merges overlapping people.
  If this dominates, the fix is CrowdHuman-trained weights rather than a
  bigger COCO model.
- **Dense crowds** (50+, heads only) are the wrong problem for a detector
  entirely; that calls for a density-estimation model (P2PNet, DM-Count).
