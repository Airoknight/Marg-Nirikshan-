# Marg Nirikshan &mdash; Ideas & Research TODO Checklist

A comprehensive tracking document for research papers, dynamic model switching architectures, datasets, and academic publication milestones.

---

## 💡 Core Research & Product Ideas

### 1. Scene-Aware Dynamic Model Switching Engine (Mixture-of-Experts)
* **Goal**: Build an automated router that dynamically selects between YOLO, P2PNet, KDE Density, and CSRNet in under 1 millisecond.
* **Why**: Solves the edge computing dilemma (preserves battery/power on NVIDIA Jetson while maintaining 95%+ accuracy across both sparse and extreme crowds).
* **Architecture**:
  * **Feature Extractor**: Laplacian Variance ($\text{Var}(\nabla^2 I)$) + Motion Subtraction + Micro ShuffleNetV2 (0.5M params).
  * **Router State Machine**: 15-frame sliding window hysteresis to prevent thrashing.
  * **Target Paper**: *IEEE Transactions on Intelligent Transportation Systems* / *IEEE Access*.

### 2. Spatiotemporal Congestion & Stampede Early Warnings ($\frac{\partial D}{\partial t}$)
* **Goal**: Track spatial density gradients over time to predict platform overcrowding 5 minutes before train arrival.
* **Metric**: $\Delta \text{Density} / \Delta t$. Trigger automatic station announcements & security alerts if rate of crowd accumulation exceeds safe thresholds.

### 3. Edge-Side Privacy-Compliant Heatmap Dashboards
* **Goal**: Broadcast anonymized 2D spatial energy maps ($\text{people}/m^2$) to commuter mobile apps without capturing or streaming raw CCTV faces/bodies.

### 4. "Marg-Crowd" Dataset & Domain Adaptation
* **Goal**: Benchmark and fine-tune CSRNet / P2PNet specifically for high-ceiling overhead CCTV angles and Indian suburban/metro railway crowd behaviors.

---

## 📊 Datasets to Use for Paper Experiments

- [x] **Dombivli & Delhi Metro Video Clips**: Local testing & UI verification (`videos/`, `uploads/`).
- [ ] **PETS 2009 Dataset**: 
  - **S1 (Person Count & Density)**: Benchmark CSRNet, P2PNet, KDE Density across `S1.L1` (Low), `S1.L2` (Medium), and `S1.L3` (High).
  - **S2 (People Tracking)**: Benchmark YOLO + ByteTrack flow rate.
  - Download: [http://www.cvg.reading.ac.uk/PETS2009/data.html](http://www.cvg.reading.ac.uk/PETS2009/data.html)
- [ ] **WorldExpo'10 Dataset**: 108 CCTV camera feeds for multi-view density validation.
- [ ] **ShanghaiTech Part A & B**: Pre-trained baseline comparison.

---

## 📋 Action Items & TODO List

### Phase 1: Prototype & Model Benchmarking (Current Phase)
- [x] Run `server.py` Web UI with live model switcher & responsive viewport.
- [x] Integrate **YOLOv11 + ByteTrack** (bounding boxes + tracking IDs).
- [x] Integrate **P2PNet** (head point localization).
- [x] Implement **Perspective-Adaptive KDE Density** (geometry-aware Gaussian spread $\sigma(y)$).
- [x] Integrate **CSRNet (Deep Dilated Density Regressor)** with pre-trained `csrnet.pth` weights.
- [x] Add real-time **Density Status Badges** (`LOW`, `MODERATE`, `HIGH CROWD`) on HUD & UI.

### Phase 2: Dynamic Router Engine Development
- [ ] Build `GatingRouter` class in `detectors.py`.
- [ ] Implement Laplacian variance texture calculation (`cv2.Laplacian`).
- [ ] Train micro-classifier (ShuffleNetV2 0.5M) to classify frames into `[Sparse, Medium, Dense]`.
- [ ] Implement FSM Hysteresis state machine (15-frame buffer).

### Phase 3: Benchmarking & Paper Experiments
- [ ] Download PETS 2009 `S1.L1`, `S1.L2`, `S1.L3` sequences.
- [ ] Run benchmark evaluation comparing:
  - Static YOLO vs Static CSRNet vs Dynamic Router Engine.
- [ ] Record evaluation metrics:
  - **MAEC (Mean Absolute Error in Count)**
  - **RMSE (Root Mean Square Error)**
  - **FPS & Latency (ms)**
  - **Wattage / Energy (Joules per frame)** on Jetson hardware.

### Phase 4: Paper Writing & Academic Submission
- [ ] Write Introduction & Related Works (YOLO, P2PNet, CSRNet, PETS 2009).
- [ ] Format Methodology section with Router equations & Cost function $J = \alpha \cdot \text{MAEC} + \beta \cdot \text{Latency} + \gamma \cdot \text{Power}$.
- [ ] Generate comparative plots & spatial density heatmaps for Figures.
- [ ] Submit paper to IEEE / CVPR Workshop / Springer journal.
