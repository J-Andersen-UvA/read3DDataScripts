import argparse
import fbx
import FbxCommon
import matplotlib.pyplot as plt


def find_node_recursive(node, name):
    if node.GetName() == name:
        return node
    for i in range(node.GetChildCount()):
        res = find_node_recursive(node.GetChild(i), name)
        if res:
            return res
    return None


def get_first_anim_stack(scene):
    criteria = fbx.FbxCriteria.ObjectType(fbx.FbxAnimStack.ClassId)
    return scene.GetSrcObject(criteria, 0)


def get_anim_time_span(scene):
    stack = get_first_anim_stack(scene)
    if not stack:
        raise RuntimeError("No animation stack found.")
    scene.SetCurrentAnimationStack(stack)
    ts = stack.GetLocalTimeSpan()
    return ts.GetStart(), ts.GetStop(), stack.GetName()


def get_fps(scene):
    tm = scene.GetGlobalSettings().GetTimeMode()
    fps = fbx.FbxTime.GetFrameRate(tm)
    return float(fps) if fps > 0 else 30.0


def get_total_frames(start_time, end_time, fps):
    duration_s = end_time.GetSecondDouble() - start_time.GetSecondDouble()
    if duration_s <= 0:
        raise RuntimeError("Invalid animation duration.")
    return int(round(duration_s * fps))


def sample_curves(scene, foot_node, hips_node, axis_index):
    start_time, end_time, stack_name = get_anim_time_span(scene)
    fps = get_fps(scene)
    time_mode = scene.GetGlobalSettings().GetTimeMode()
    total_frames = get_total_frames(start_time, end_time, fps)

    seconds = []
    foot_vals = []
    hips_vals = []
    rel_vals = []
    frames = []

    for f in range(0, total_frames + 1):
        t = fbx.FbxTime()
        t.SetFrame(f, time_mode)

        foot_t = foot_node.EvaluateGlobalTransform(t).GetT()
        hips_t = hips_node.EvaluateGlobalTransform(t).GetT()

        foot_v = float(foot_t[axis_index])
        hips_v = float(hips_t[axis_index])
        rel_v = foot_v - hips_v

        frames.append(f)
        seconds.append(f / fps)
        foot_vals.append(foot_v)
        hips_vals.append(hips_v)
        rel_vals.append(rel_v)

    return {
        "stack": stack_name,
        "fps": fps,
        "frames": frames,
        "seconds": seconds,
        "foot": foot_vals,
        "hips": hips_vals,
        "rel": rel_vals,
    }


def find_last_local_min(frames, values):
    valleys = []
    for i in range(1, len(values) - 1):
        if values[i - 1] > values[i] and values[i] <= values[i + 1]:
            valleys.append(i)
    return valleys[-1] if valleys else None


def detect_press(curves):
    rel = curves["rel"]
    frames = curves["frames"]

    # compute velocity (frame-to-frame difference)
    velocities = []
    for i in range(1, len(rel)):
        dv = rel[i] - rel[i - 1]
        velocities.append((i, dv))

    # strongest negative velocity = press impact
    press_i, min_vel = min(velocities, key=lambda x: x[1])

    return press_i, "minVelocity"

def load_scene(fbx_path):
    manager, scene = FbxCommon.InitializeSdkObjects()
    if not FbxCommon.LoadScene(manager, scene, fbx_path):
        raise RuntimeError(f"Failed to load FBX: {fbx_path}")
    return manager, scene


def analyze_and_plot(ax, fbx_path, foot_name, hips_name, axis):
    manager, scene = load_scene(fbx_path)
    root = scene.GetRootNode()

    foot_node = find_node_recursive(root, foot_name)
    hips_node = find_node_recursive(root, hips_name)
    if not foot_node:
        raise RuntimeError(f"[{fbx_path}] Foot node '{foot_name}' not found")
    if not hips_node:
        raise RuntimeError(f"[{fbx_path}] Hips node '{hips_name}' not found")

    axis_index = {"X": 0, "Y": 1, "Z": 2}[axis.upper()]
    curves = sample_curves(scene, foot_node, hips_node, axis_index)

    press_i, press_kind = detect_press(curves)
    press_frame = curves["frames"][press_i]
    press_time = curves["seconds"][press_i]
    press_value = curves["rel"][press_i]

    # Plot curves
    ax.plot(curves["seconds"], curves["foot"], label="Foot Global")
    ax.plot(curves["seconds"], curves["hips"], label="Hips Global")
    ax.plot(curves["seconds"], curves["rel"], label="Foot - Hips")

    # Horizontal line at detected press value (on relative curve scale)
    ax.axhline(press_value, linestyle="--", linewidth=1.0)
    # Vertical marker at detected time
    ax.axvline(press_time, linestyle="--", linewidth=1.0)

    clip_name = fbx_path.split("/")[-1].split("\\")[-1]
    ax.set_title(f"{clip_name} | stack: {curves['stack']} | fps: {curves['fps']:.3f} | press: f{press_frame} t{press_time:.3f}s ({press_kind})")
    ax.set_xlabel("Time (seconds)")
    ax.set_ylabel(f"Axis {axis.upper()}")

    ax.legend()

    manager.Destroy()

    return {
        "fbx": fbx_path,
        "fps": curves["fps"],
        "press_frame": press_frame,
        "press_seconds": press_time,
        "press_value": press_value,
        "press_kind": press_kind,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fbxA", required=True)
    ap.add_argument("--footA", required=True)
    ap.add_argument("--hipsA", required=True)

    ap.add_argument("--fbxB", required=True)
    ap.add_argument("--footB", required=True)
    ap.add_argument("--hipsB", required=True)

    ap.add_argument("--axis", default="Y", choices=["X", "Y", "Z", "x", "y", "z"])
    args = ap.parse_args()

    fig, axes = plt.subplots(2, 1, figsize=(10, 8), sharex=False)

    A = analyze_and_plot(axes[0], args.fbxA, args.footA, args.hipsA, args.axis)
    B = analyze_and_plot(axes[1], args.fbxB, args.footB, args.hipsB, args.axis)

    dt_seconds = B["press_seconds"] - A["press_seconds"]
    dt_frames_A = dt_seconds * A["fps"]
    dt_frames_B = dt_seconds * B["fps"]

    print("\n=== Clip A ===")
    print(A)
    print("\n=== Clip B ===")
    print(B)
    print("\n=== Difference (B - A) ===")
    print(f"dt_seconds: {dt_seconds}")
    print(f"dt_frames_at_A_fps ({A['fps']}): {dt_frames_A}")
    print(f"dt_frames_at_B_fps ({B['fps']}): {dt_frames_B}")

    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()