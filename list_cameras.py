"""Show every camera the system exposes and which ones actually deliver frames.

  ./run.sh list_cameras.py
"""

from camera import list_cameras

if __name__ == "__main__":
    cams = list_cameras(probe=True)
    print(f"{'src':>4}  {'device':<14}{'resolution':<13}{'ok':<5}name")
    print("-" * 72)
    for c in cams:
        res = f"{c['width']}x{c['height']}" if c["works"] else "-"
        print(f"{c['index']:>4}  {c['path']:<14}{res:<13}{'yes' if c['works'] else 'no':<5}{c['name']}")

    usable = [c for c in cams if c["works"]]
    print(f"\n{len(usable)} usable camera(s). Use the 'src' number with --source.\n")
    for c in usable:
        print(f"  --source {c['index']}   {c['name']}")
        if c["stable_path"]:
            # Kernel video<N> numbering shifts on replug/reboot; the by-id path
            # does not, so prefer it for anything you want to keep working.
            print(f"  --source {c['stable_path']}   (same camera, stable across replug)")
    print("\nNodes marked 'no' are metadata companions of the camera above them, not real cameras.")
