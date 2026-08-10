#!/usr/bin/env bash
# Run a prototype script against the venv with ROS 2's PYTHONPATH stripped.
#
# Sourcing ROS 2 injects /opt/ros/humble/... into PYTHONPATH, and PYTHONPATH is
# placed AHEAD of the venv's site-packages in sys.path -- a venv does not filter
# it. Any name present in both resolves to the ROS copy. `env -u PYTHONPATH`
# removes the variable for this process only; your shell keeps ROS as-is.
#
#   ./run.sh people_counter.py
#   ./run.sh benchmark_models.py --source clip.mp4 --truth 3

cd "$(dirname "$0")" || exit 1
exec env -u PYTHONPATH ./.venv/bin/python "$@"

