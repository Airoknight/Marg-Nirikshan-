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

## Web UI

```bash
./run.sh server.py                 # then open http://localhost:8000
./run.sh server.py --host 0.0.0.0  # reachable from your phone on the LAN
```

Switch camera and detector live, toggle box/dot overlay, and tune thresholds
while watching the count. One worker thread owns the camera and every browser
tab reads the same annotated frames, so viewers cost nothing extra.

This is also the right interface for the eventual Jetson deployment, which will
run headless.

### P2PNet setup

The point-based detector needs the upstream repo (its 86 MB checkpoint is
bundled in it, so there is nothing else to download):

```bash
git clone --depth 1 https://github.com/TencentYoutuResearch/CrowdCounting-P2PNet.git third_party/P2PNet
```

**Read this before judging its accuracy:** the released weights are trained on
ShanghaiTech Part A — dense outdoor crowds of hundreds. On a near-empty indoor
scene P2PNet will overcount badly. That is domain mismatch, not a defect, and
it means a sparse-scene A/B against YOLO is not a fair comparison. Judge it on
genuinely crowded footage.

`detectors.py` shims two names (`_new_empty_tensor`, `_output_size`) that the
2021 repo imports from torchvision. Its version check reads `"0.26.0"` as `0.2`,
decides you are on torchvision 0.5, and takes a legacy path that no longer
exists. The shim avoids patching the vendored clone, which a re-clone would undo.

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

## 🚀 Jetson Nano Installation Guide

### 1. Clone the Code to your Jetson Nano
Once you have flashed the SD card and booted your Jetson Nano, open a terminal on the Nano and run:

```bash
# Move to your home directory
cd ~/
# Clone the repository
git clone https://github.com/Airoknight/Marg-Nirikshan-.git
cd Marg-Nirikshan-
```

### 2. Maximize Jetson Performance (Max-N Mode)
The original Jetson Nano needs to be put into 10W Max Performance mode and its fans/clocks spun up:

```bash
sudo nvpmodel -m 0
sudo jetson_clocks
```

### 3. Install System Dependencies
JetPack comes with OpenCV pre-installed, but you need some build tools:

```bash
sudo apt-get update
sudo apt-get install -y python3-pip libopenblas-base libopenmpi-dev libjpeg-dev zlib1g-dev python3-dev
```

### 4. Install PyTorch & Torchvision (CRITICAL STEP)
**DO NOT** just run `pip3 install torch`. It will fail on the Jetson's ARM architecture. You **must** use NVIDIA's custom compiled wheels for JetPack 4.6.1 (Python 3.6):

**Download and Install PyTorch 1.10:**
```bash
wget https://nvidia.box.com/shared/static/fjtbno0vpo676a25cgvuqc1wty0fkkg6.whl -O torch-1.10.0-cp36-cp36m-linux_aarch64.whl
pip3 install Cython numpy
pip3 install torch-1.10.0-cp36-cp36m-linux_aarch64.whl
```

**Compile Torchvision from Source:** 
Because you are using PyTorch 1.10, you must compile Torchvision v0.11.1 to match it:
```bash
git clone --branch v0.11.1 https://github.com/pytorch/vision torchvision
cd torchvision
export BUILD_VERSION=0.11.1
sudo python3 setup.py install
cd ..
```

### 5. Install Remaining App Requirements
Install FastAPI, Uvicorn, and other dependencies:

```bash
pip3 install fastapi uvicorn Pillow requests python-multipart scipy==1.5.4
```
*(Note: We specify `scipy==1.5.4` because newer versions dropped support for Python 3.6).*

### 6. Run the Application
Everything is now ready. Start the server exactly as you do on your laptop!

```bash
python3 server.py --host 0.0.0.0 --port 8000
```
> **Note:** The first time you run this, it may take 2-5 minutes to boot up because TensorRT will be optimizing and compiling the PyTorch models for the Jetson's Maxwell GPU.

### How to Access it from your Phone or Laptop:
To view the Dashboard or Passenger App from your phone/laptop, you don't need to connect a monitor to the Nano.
1. Find the Nano's IP address by running `hostname -I` in its terminal (e.g., `192.168.1.50`).
2. Open your phone or laptop browser and go to: `http://<YOUR_NANO_IP>:8000`

---

## ⚠️ Important Note on Git Tracking (`.gitignore`)

You may notice that certain folders (like `third_party/`, `.venv/`, `uploads/`, and large `.mp4` videos) are ignored by Git. **Do not remove `.gitignore` to force push everything.** 

Doing so will break your repository for three reasons:
1. **GitHub File Size Limits:** GitHub permanently blocks files over 100MB (like raw CCTV videos).
2. **Architecture Mismatch:** Pushing a massive 7.5GB `.venv` from a laptop to GitHub is not only too large, but the Linux x86 binaries inside won't even run on the Jetson Nano's ARM64 architecture.
3. **Nested Repositories:** P2PNet (`third_party/P2PNet`) is a cloned git repo. Pushing a repo inside a repo creates a submodule pointer instead of pushing the actual files, breaking the deployment. 

Always follow the installation steps to download models directly on the target hardware!