"""Camera discovery and opening, shared by the prototype scripts.

V4L2 exposes two nodes per UVC camera -- video0/video1 for one physical device.
Only the first delivers frames; the second carries metadata. So "how many
/dev/video* exist" is never the same as "how many cameras you have", and the
only reliable test is to open one and try to read a frame.
"""

import glob
import os
import re

import cv2

# ---------------------------------------------------------------------------
# DEFAULT CAMERA -- change this one line to switch which camera every script
# uses. Run list_cameras.py to see the options.
#
#   external USB cam (640x480, mounted wherever you need it):
#     "/dev/v4l/by-id/usb-Generic_HD_camera_20181212000000-video-index0"
#   built-in laptop webcam (1280x720):
#     "/dev/v4l/by-id/usb-Sonix_Technology_Co.__Ltd._Integrated_Webcam_HD-video-index0"
#
# by-id paths are used instead of "0"/"2" because the kernel's video<N>
# numbering shifts on replug and reboot; by-id names the physical device.
# ---------------------------------------------------------------------------
DEFAULT_SOURCE = "/dev/v4l/by-id/usb-Generic_HD_camera_20181212000000-video-index0"


def _sysfs_name(dev_path):
    m = re.search(r"video(\d+)$", os.path.realpath(dev_path))
    if not m:
        return "?"
    try:
        with open(f"/sys/class/video4linux/video{m.group(1)}/name") as f:
            return f.read().strip()
    except OSError:
        return "?"


def list_cameras(probe=True):
    """Return [{index, path, name, stable_path, works, width, height}] for each
    /dev/video* node. With probe=True each is opened to see if it yields a frame."""
    out = []
    # Map real device -> stable /dev/v4l/by-id symlink, which survives replug
    # and reboot, unlike the kernel's video<N> numbering.
    by_id = {}
    for link in glob.glob("/dev/v4l/by-id/*"):
        by_id.setdefault(os.path.realpath(link), link)

    for path in sorted(glob.glob("/dev/video*"), key=lambda p: int(re.sub(r"\D", "", p) or 0)):
        idx = int(re.sub(r"\D", "", path) or 0)
        entry = {"index": idx, "path": path, "name": _sysfs_name(path),
                 "stable_path": by_id.get(os.path.realpath(path)),
                 "works": False, "width": 0, "height": 0}
        if probe:
            cap = cv2.VideoCapture(idx, cv2.CAP_V4L2)
            if cap.isOpened():
                ok, frame = cap.read()
                if ok and frame is not None:
                    entry.update(works=True, height=frame.shape[0], width=frame.shape[1])
            cap.release()
        out.append(entry)
    return out


def open_capture(source, width=1280, height=720):
    """Open a camera index, a /dev/video* path, a /dev/v4l/by-id/* symlink, or a
    video file. Camera sources get MJPG requested -- without it many USB cams are
    capped to ~5 fps at 720p, because raw YUYV needs more bandwidth than USB 2.0
    has to give."""
    is_device = False
    if isinstance(source, str) and source.isdigit():
        target, is_device = int(source), True
    elif isinstance(source, int):
        target, is_device = source, True
    elif isinstance(source, str) and source.startswith("/dev/"):
        # cv2 takes a device path, but only the V4L2 backend handles it properly.
        target, is_device = os.path.realpath(source), True
    else:
        target = source

    cap = cv2.VideoCapture(target, cv2.CAP_V4L2) if is_device else cv2.VideoCapture(target)
    if not cap.isOpened():
        raise SystemExit(f"could not open source {source!r} -- run list_cameras.py to see what exists")

    if is_device:
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # prefer the newest frame over a backlog
    return cap
