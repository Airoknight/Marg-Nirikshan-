# 🚀 Deploying Marg Nirikshan on NVIDIA Jetson Orin Nano

This guide outlines the step-by-step process for deploying the **Marg Nirikshan AI Crowd Analytics Platform** onto the **NVIDIA Jetson Orin Nano Developer Kit (ARM64 / JetPack)**.

---

## 📋 Hardware & Software Prerequisites

1. **NVIDIA Jetson Orin Nano DevKit** (4GB or 8GB RAM).
2. **JetPack 5.1.x / JetPack 6.0** flashed via SD Card / NVMe SSD (Ubuntu 20.04 / 22.04 LTS).
3. **Power Supply**: 9V-20V DC Barrel Jack (recommended 19V 45W for 15W Max Power Mode).
4. **CCTV / Camera Input**: USB Webcam, RTSP IP Camera stream, or MIPI CSI Camera (`CAM0` / `CAM1` connector).

---

## ⚡ Step 1: Maximize Jetson Performance Mode

Run the following commands in the Jetson terminal to unlock full 15W GPU performance:

```bash
# Set Power Mode to 15W MAX-N
sudo nvpmodel -m 0

# Maximize GPU, CPU, and Memory clock speeds
sudo jetson_clocks
```

---

## 📦 Step 2: System Dependencies & OpenCV Setup

Install system prerequisites, GStreamer (hardware decoding), and Python libraries:

```bash
sudo apt-get update
sudo apt-get install -y \
    python3-pip \
    python3-dev \
    libopenblas-dev \
    libopenmpi-dev \
    openmpi-bin \
    git \
    cmake \
    ffmpeg \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly
```

---

## 🔥 Step 3: Install PyTorch & torchvision for Jetson ARM64

> ⚠️ **IMPORTANT**: Do NOT use `pip install torch` from PyPI! You must use NVIDIA's official pre-built ARM64 JetPack wheels.

### For JetPack 5.1 (Ubuntu 20.04 / Python 3.8):
```bash
# Download PyTorch for ARM64 JetPack 5.1
wget https://developer.download.nvidia.com/vulkan/redist/torch-2.0.0+nv23.05-cp38-cp38-linux_aarch64.whl -O torch-2.0.0-cp38-linux_aarch64.whl
pip3 install torch-2.0.0-cp38-linux_aarch64.whl

# Download torchvision matching PyTorch 2.0
sudo apt-get install -y libjpeg-dev zlib1g-dev
git clone --branch v0.15.2 https://github.com/pytorch/vision torchvision
cd torchvision
export BUILD_VERSION=0.15.2
python3 setup.py install --user
cd ..
```

### For JetPack 6.0 (Ubuntu 22.04 / Python 3.10):
```bash
# Install PyTorch JetPack 6.0 wheel
pip3 install --extra-index-url https://developer.download.nvidia.com/compute/redist/jp/v60 torch torchvision
```

---

## 📥 Step 4: Clone Repository & Install Python Dependencies

```bash
# Navigate to workspace
cd ~/
git clone <your-repo-url> marg-nirikshan
cd marg-nirikshan

# Install application requirements (excluding desktop torch)
pip3 install fastapi uvicorn opencv-python Pillow requests numpy scipy
```

---

## 🎯 Step 5: GPU Model Execution (P2PNet & TensorRT)

On Jetson Orin Nano, P2PNet and YOLO run seamlessly on CUDA:

1. **Test CUDA Availability**:
   ```python
   python3 -c "import torch; print('CUDA Available:', torch.cuda.is_available()); print('Device:', torch.cuda.get_device_name(0))"
   ```
   *Output should display: `Device: Orin`*

2. **Run Server with GPU Acceleration**:
   ```bash
   python3 server.py --host 0.0.0.0 --port 8000
   ```

---

## 🎥 Step 6: Connecting Physical Cameras / Streams

### A. USB Webcams (`/dev/video0`)
Pass camera index in the server UI or config:
```json
{
  "source": "0"
}
```

### B. RTSP IP CCTV Camera Feeds
Enter your RTSP stream URL directly in the UI dropdown or camera source:
```
rtsp://admin:password@192.168.1.100:554/h264Preview_01_main
```

### C. Onboard MIPI CSI Cameras (`CAM0` / `CAM1` ribbon cables)
Use the GStreamer pipeline string as source:
```
nvarguscamerasrc sensor-id=0 ! video/x-raw(memory:NVMM), width=1280, height=720, framerate=30/1 ! nvvidconv ! video/x-raw, format=BGRx ! videoconvert ! video/x-raw, format=BGR ! appsink
```

---

## 🌐 Step 7: Network Access from Phone / Laptop

Once server is running on Jetson:
- Find Jetson IP: `hostname -I` (e.g., `192.168.1.50`).
- Access from any Phone/Laptop on the same Wi-Fi network:
  - **Government Dashboard**: `http://192.168.1.50:8000`
  - **Passenger App**: `http://192.168.1.50:8000` (auto-detects mobile screen width)

---

## ⚡ Performance Benchmark on Jetson Orin Nano

| AI Model | Input Res | Precision | Frame Rate (FPS) |
| :--- | :--- | :--- | :--- |
| **P2PNet (Head Detection)** | 512×512 | FP16 (CUDA) | **28 – 35 FPS** |
| **YOLOv8 Small** | 640×640 | TensorRT FP16 | **45 – 60 FPS** |
| **Density Heatmap** | 512×512 | CUDA | **30 FPS** |
