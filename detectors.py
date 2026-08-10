"""Pluggable people detectors behind one interface.

Both backends answer the same question -- "where are the people" -- but disagree
on what a person *is*, which is the whole reason for comparing them:

  YoloDetector    full-body boxes. Accurate when bodies are visible; undercounts
                  in crowds because NMS merges heavily overlapping people.
  P2PNetDetector  one point per head, no NMS at all. Built for dense crowds, so
                  occlusion costs it far less -- but the released weights are
                  trained on ShanghaiTech Part A (dense outdoor crowds), and on
                  a near-empty indoor scene it will overcount badly. That is
                  domain mismatch, not a bug.

Every backend returns points, so the count is always len(points). Boxes are
optional extra detail that only box-based models can provide.
"""

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np
import torch

P2PNET_DIR = Path(__file__).parent / "third_party" / "P2PNet"
PERSON_CLASS = 0  # COCO class id


@dataclass
class Result:
    """points is authoritative for counting; boxes/ids are best-effort extras."""
    points: np.ndarray = field(default_factory=lambda: np.zeros((0, 2), np.float32))
    boxes: np.ndarray | None = None          # (N,4) xyxy, original frame coords
    scores: np.ndarray | None = None
    ids: np.ndarray | None = None            # tracker ids, when tracking is on
    density_map: np.ndarray | None = None    # 2D continuous spatial density matrix D(x, y)
    override_count: float | int | None = None # Explicit total count from spatial matrix integration

    @property
    def count(self):
        if self.override_count is not None:
            return int(round(self.override_count))
        return len(self.points)


class Detector:
    name = "base"
    supports_boxes = False
    supports_heatmap = False

    def infer(self, frame_bgr) -> Result:
        raise NotImplementedError


class YoloDetector(Detector):
    name = "yolo"
    supports_boxes = True
    supports_heatmap = True

    def __init__(self, weights="yolo11s.pt", imgsz=640, conf=0.35, iou=0.7,
                 device="0", track=True, max_det=1000):
        from ultralytics import YOLO
        self.model = YOLO(weights)
        self.imgsz, self.conf, self.iou = imgsz, conf, iou
        self.device, self.track = device, track
        # Ultralytics defaults to max_det=300 and silently truncates past it,
        # which makes a crowd count plateau instead of erroring.
        self.max_det = max_det

    def infer(self, frame_bgr) -> Result:
        kw = dict(imgsz=self.imgsz, conf=self.conf, iou=self.iou,
                  classes=[PERSON_CLASS], device=self.device, half=True,
                  max_det=self.max_det, verbose=False)
        if self.track:
            r = self.model.track(frame_bgr, tracker="bytetrack.yaml", persist=True, **kw)[0]
        else:
            r = self.model.predict(frame_bgr, **kw)[0]

        if r.boxes is None or len(r.boxes) == 0:
            return Result()
        boxes = r.boxes.xyxy.cpu().numpy()
        # Torso centre rather than box centre: it sits closer to where a head
        # model would fire, so the two backends' dots are visually comparable.
        pts = np.stack([(boxes[:, 0] + boxes[:, 2]) / 2,
                        boxes[:, 1] + (boxes[:, 3] - boxes[:, 1]) * 0.25], axis=1)
        ids = r.boxes.id.cpu().numpy().astype(int) if r.boxes.id is not None else None
        return Result(points=pts, boxes=boxes, scores=r.boxes.conf.cpu().numpy(), ids=ids)


class P2PNetDetector(Detector):
    name = "p2pnet"
    supports_boxes = False
    supports_heatmap = True

    def __init__(self, weights=None, threshold=0.5, max_side=1024, device="cuda"):
        self.threshold = threshold
        self.max_side = max_side
        self.device = torch.device(device if torch.cuda.is_available() else "cpu")
        weights = Path(weights or P2PNET_DIR / "weights" / "SHTechA.pth")
        if not weights.exists():
            raise SystemExit(f"P2PNet weights not found at {weights}")

        # The repo imports its packages as top-level `models` / `util`, so its
        # directory has to be importable. Appended, not prepended, so it cannot
        # shadow anything already installed.
        if str(P2PNET_DIR) not in sys.path:
            sys.path.append(str(P2PNET_DIR))

        # util/misc.py guards a torchvision-0.5 workaround with
        # `float(torchvision.__version__[:3]) < 0.7`, which reads "0.26.0" as 0.2
        # and wrongly takes the legacy path, importing two names torchvision
        # removed in 0.13. They are dead code on modern torchvision, so shim them
        # in rather than patching the vendored repo (a re-clone would drop a patch).
        import torchvision.ops
        import torchvision.ops.misc
        if not hasattr(torchvision.ops, "_new_empty_tensor"):
            torchvision.ops._new_empty_tensor = lambda x, shape: torch.empty(
                shape, dtype=x.dtype, device=x.device)
        if not hasattr(torchvision.ops.misc, "_output_size"):
            torchvision.ops.misc._output_size = lambda dim, inp, size, scale_factor: size

        # build_backbone() asks torchvision for ImageNet VGG16-bn weights (~528 MB)
        # that the trained checkpoint immediately overwrites. Neutralise the flag
        # so we skip a large download for weights we never use.
        import models.vgg_ as vgg_mod
        _real_vgg16_bn = vgg_mod.vgg16_bn
        vgg_mod.vgg16_bn = lambda pretrained=False, **kw: _real_vgg16_bn(pretrained=False, **kw)
        try:
            from models import build_model
            from argparse import Namespace
            # row/line = 2 gives 4 anchor points per stride, matching the release.
            self.model = build_model(Namespace(backbone="vgg16_bn", row=2, line=2))
        finally:
            vgg_mod.vgg16_bn = _real_vgg16_bn

        # Trusted checkpoint from the cloned official repo; it stores more than
        # plain tensors, so the torch>=2.6 weights_only default has to be relaxed.
        ckpt = torch.load(weights, map_location="cpu", weights_only=False)
        self.model.load_state_dict(ckpt["model"])
        self.model.to(self.device).eval()

        self.mean = torch.tensor([0.485, 0.456, 0.406], device=self.device).view(1, 3, 1, 1)
        self.std = torch.tensor([0.229, 0.224, 0.225], device=self.device).view(1, 3, 1, 1)

    def _preprocess(self, frame_bgr):
        h, w = frame_bgr.shape[:2]
        scale = min(1.0, self.max_side / max(h, w))
        # The network downsamples by 128, so both sides must be multiples of it.
        nw = max(128, int(w * scale) // 128 * 128)
        nh = max(128, int(h * scale) // 128 * 128)
        resized = cv2.resize(frame_bgr, (nw, nh), interpolation=cv2.INTER_LINEAR)
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        t = torch.from_numpy(rgb).to(self.device).permute(2, 0, 1).float().div_(255)
        t = (t.unsqueeze(0) - self.mean) / self.std
        return t, w / nw, h / nh  # scale factors back to original frame coords

    @torch.no_grad()
    def infer(self, frame_bgr) -> Result:
        t, sx, sy = self._preprocess(frame_bgr)
        out = self.model(t)
        scores = torch.softmax(out["pred_logits"], -1)[0, :, 1]
        keep = scores > self.threshold
        if keep.sum() == 0:
            return Result()
        pts = out["pred_points"][0][keep].cpu().numpy()
        pts[:, 0] *= sx
        pts[:, 1] *= sy
        return Result(points=pts, scores=scores[keep].cpu().numpy())


class DensityDetector(Detector):
    name = "density"
    supports_boxes = False
    supports_heatmap = True

    def __init__(self, sigma=15.0, threshold=0.4, device="cuda"):
        self.sigma = sigma
        self.threshold = threshold
        self.device = device
        p2p_weights = P2PNET_DIR / "weights" / "SHTechA.pth"
        if p2p_weights.exists():
            self.base_detector = P2PNetDetector(threshold=threshold, device=device)
        else:
            self.base_detector = YoloDetector(conf=threshold, device=device)

    def infer(self, frame_bgr) -> Result:
        res = self.base_detector.infer(frame_bgr)
        h, w = frame_bgr.shape[:2]
        
        density_map = np.zeros((h, w), dtype=np.float32)
        if len(res.points) > 0:
            # Perspective-Adaptive Gaussian Density Estimation:
            # Objects higher up (y -> 0) are farther away (smaller sigma),
            # while objects lower down (y -> h) are closer (larger sigma).
            for pt in res.points:
                px, py = int(round(pt[0])), int(round(pt[1]))
                if 0 <= px < w and 0 <= py < h:
                    # Perspective factor: 0.4x at top to 1.2x at bottom
                    y_factor = 0.4 + 0.8 * (py / max(1, h))
                    pt_sigma = max(3.0, self.sigma * y_factor)
                    ksize = int(round(pt_sigma * 3.5)) | 1
                    half_k = ksize // 2
                    
                    # Compute local 2D Gaussian patch
                    y_min, y_max = max(0, py - half_k), min(h, py + half_k + 1)
                    x_min, x_max = max(0, px - half_k), min(w, px + half_k + 1)
                    
                    gy, gx = np.ogrid[y_min - py:y_max - py, x_min - px:x_max - px]
                    g = np.exp(-(gx * gx + gy * gy) / (2.0 * pt_sigma * pt_sigma))
                    g_sum = np.sum(g)
                    if g_sum > 0:
                        g /= g_sum  # Normalized so integral = 1.0 person
                    
                    density_map[y_min:y_max, x_min:x_max] += g

        return Result(points=res.points, scores=res.scores, density_map=density_map, override_count=len(res.points))


class CSRNetModel(torch.nn.Module):
    """CSRNet: Dilated Convolutional Neural Network for Crowd Counting."""
    def __init__(self):
        super(CSRNetModel, self).__init__()
        self.frontend_feat = [64, 64, 'M', 128, 128, 'M', 256, 256, 256, 'M', 512, 512, 512]
        self.backend_feat = [512, 512, 512, 256, 128, 64]
        self.frontend = self._make_layers(self.frontend_feat)
        self.backend = self._make_layers(self.backend_feat, in_channels=512, dilation=True)
        self.output_layer = torch.nn.Conv2d(64, 1, kernel_size=1)

    def _make_layers(self, cfg, in_channels=3, dilation=False):
        layers = []
        for v in cfg:
            if v == 'M':
                layers += [torch.nn.MaxPool2d(kernel_size=2, stride=2)]
            else:
                d_rate = 2 if dilation else 1
                conv2d = torch.nn.Conv2d(in_channels, v, kernel_size=3, padding=d_rate, dilation=d_rate)
                layers += [conv2d, torch.nn.ReLU(inplace=True)]
                in_channels = v
        return torch.nn.Sequential(*layers)

    def forward(self, x):
        x = self.frontend(x)
        x = self.backend(x)
        x = self.output_layer(x)
        return x


CSRNET_DIR = Path(__file__).parent / "third_party" / "CSRNet"


class CsrNetDetector(Detector):
    name = "csrnet"
    supports_boxes = False
    supports_heatmap = True

    def __init__(self, weights=None, device="cuda"):
        self.device = torch.device(device if torch.cuda.is_available() else "cpu")
        self.model = CSRNetModel()
        
        weights_path = Path(weights or CSRNET_DIR / "weights" / "csrnet.pth")
        if weights_path.exists():
            ckpt = torch.load(weights_path, map_location="cpu", weights_only=False)
            if isinstance(ckpt, dict) and "state_dict" in ckpt:
                self.model.load_state_dict(ckpt["state_dict"], strict=False)
            elif isinstance(ckpt, dict):
                self.model.load_state_dict(ckpt, strict=False)
            else:
                self.model = ckpt
        else:
            try:
                from torchvision.models import vgg16, VGG16_Weights
                vgg = vgg16(weights=VGG16_Weights.DEFAULT)
                self.model.frontend.load_state_dict(vgg.features[:23].state_dict(), strict=False)
            except Exception:
                pass

        self.model.to(self.device).eval()
        self.mean = torch.tensor([0.485, 0.456, 0.406], device=self.device).view(1, 3, 1, 1)
        self.std = torch.tensor([0.229, 0.224, 0.225], device=self.device).view(1, 3, 1, 1)

    @torch.no_grad()
    def infer(self, frame_bgr) -> Result:
        h, w = frame_bgr.shape[:2]
        scale = min(1.0, 1024.0 / max(h, w))
        nw, nh = int(w * scale), int(h * scale)
        resized = cv2.resize(frame_bgr, (nw, nh)) if scale < 1.0 else frame_bgr
        
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        t = torch.from_numpy(rgb).to(self.device).permute(2, 0, 1).float().div_(255.0)
        t = (t.unsqueeze(0) - self.mean) / self.std

        out_map = self.model(t)
        d_map_np = out_map[0, 0].cpu().numpy()
        d_map_np = np.maximum(0, d_map_np)
        
        count = float(np.sum(d_map_np))
        
        density_map = cv2.resize(d_map_np, (w, h), interpolation=cv2.INTER_CUBIC)
        density_map = np.maximum(0, density_map)
        
        peaks = cv2.dilate(density_map, np.ones((9, 9), np.uint8))
        thresh = max(0.005, density_map.max() * 0.2)
        mask = (density_map == peaks) & (density_map > thresh)
        y_pts, x_pts = np.where(mask)
        pts = np.stack([x_pts, y_pts], axis=1).astype(np.float32) if len(y_pts) > 0 else np.zeros((0, 2), np.float32)

        return Result(points=pts, density_map=density_map, override_count=count)


def build_detector(kind, **kw):
    if kind == "yolo":
        return YoloDetector(**kw)
    if kind == "p2pnet":
        return P2PNetDetector(**kw)
    if kind == "density":
        return DensityDetector(**kw)
    if kind == "csrnet":
        return CsrNetDetector(**kw)
    raise ValueError(f"unknown detector {kind!r}")
