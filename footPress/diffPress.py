import argparse
import json
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


def detect_press(curves):
    rel = curves["rel"]

    # compute velocity (frame-to-frame difference)
    best_i = 1
    best_dv = rel[1] - rel[0]
    for i in range(2, len(rel)):
        dv = rel[i] - rel[i - 1]
        if dv < best_dv:
            best_dv = dv
            best_i = i

    return best_i, "minVelocity"


def load_scene(fbx_path):
    manager, scene = FbxCommon.InitializeSdkObjects()
    if not FbxCommon.LoadScene(manager, scene, fbx_path):
        raise RuntimeError(f"Failed to load FBX: {fbx_path}")
    return manager, scene


def analyze_clip(fbx_path, foot_name, hips_name, axis):
    manager, scene = load_scene(fbx_path)
    root = scene.GetRootNode()

    foot_node = find_node_recursive(root, foot_name)
    hips_node = find_node_recursive(root, hips_name)
    if not foot_node:
        manager.Destroy()
        raise RuntimeError(f"[{fbx_path}] Foot node '{foot_name}' not found")
    if not hips_node:
        manager.Destroy()
        raise RuntimeError(f"[{fbx_path}] Hips node '{hips_name}' not found")

    axis_index = {"X": 0, "Y": 1, "Z": 2}[axis.upper()]
    curves = sample_curves(scene, foot_node, hips_node, axis_index)

    press_i, press_kind = detect_press(curves)
    press_frame = int(curves["frames"][press_i])
    press_time = float(curves["seconds"][press_i])
    press_value = float(curves["rel"][press_i])

    clip_result = {
        "fbx": fbx_path,
        "stack": curves["stack"],
        "fps": float(curves["fps"]),
        "axis": axis.upper(),
        "foot": foot_name,
        "hips": hips_name,
        "press_frame": press_frame,
        "press_seconds": press_time,
        "press_value": press_value,
        "press_kind": press_kind,
    }

    manager.Destroy()
    return clip_result, curves


def plot_clip(ax, clip_result, curves):
    press_frame = clip_result["press_frame"]
    press_time = clip_result["press_seconds"]
    press_value = clip_result["press_value"]

    ax.plot(curves["seconds"], curves["foot"], label="Foot Global")
    ax.plot(curves["seconds"], curves["hips"], label="Hips Global")
    ax.plot(curves["seconds"], curves["rel"], label="Foot - Hips")

    ax.axhline(press_value, linestyle="--", linewidth=1.0)
    ax.axvline(press_time, linestyle="--", linewidth=1.0)

    clip_name = clip_result["fbx"].split("/")[-1].split("\\")[-1]
    ax.set_title(
        f"{clip_name} | stack: {clip_result['stack']} | fps: {clip_result['fps']:.3f} | "
        f"press: f{press_frame} t{press_time:.3f}s ({clip_result['press_kind']})"
    )
    ax.set_xlabel("Time (seconds)")
    ax.set_ylabel(f"Axis {clip_result['axis']}")
    ax.legend()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fbxA", required=True)
    ap.add_argument("--footA", required=True)
    ap.add_argument("--hipsA", required=True)

    ap.add_argument("--fbxB", required=True)
    ap.add_argument("--footB", required=True)
    ap.add_argument("--hipsB", required=True)

    ap.add_argument("--axis", default="Y", choices=["X", "Y", "Z", "x", "y", "z"])

    ap.add_argument("--noPlot", action="store_true", help="Disable plotting (for batch runs)")
    ap.add_argument("--outJson", default=None, help="Write results dictionary to this JSON file path")

    args = ap.parse_args()

    A_result, A_curves = analyze_clip(args.fbxA, args.footA, args.hipsA, args.axis)
    B_result, B_curves = analyze_clip(args.fbxB, args.footB, args.hipsB, args.axis)

    dt_seconds = float(B_result["press_seconds"] - A_result["press_seconds"])
    dt_frames_A = float(dt_seconds * A_result["fps"])
    dt_frames_B = float(dt_seconds * B_result["fps"])

    out = {
        "clipA": A_result,
        "clipB": B_result,
        "difference": {
            "dt_seconds": dt_seconds,
            "dt_frames_at_A_fps": dt_frames_A,
            "dt_frames_at_B_fps": dt_frames_B,
        },
    }

    # print("\n=== Clip A ===")
    # print(A_result)
    # print("\n=== Clip B ===")
    # print(B_result)
    # print("\n=== Difference (B - A) ===")
    # print(f"dt_seconds: {dt_seconds}")
    # print(f"dt_frames_at_A_fps ({A_result['fps']}): {dt_frames_A}")
    # print(f"dt_frames_at_B_fps ({B_result['fps']}): {dt_frames_B}")

    if args.outJson:
        with open(args.outJson, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2)

    if not args.noPlot:
        fig, axes = plt.subplots(2, 1, figsize=(10, 8), sharex=False)
        plot_clip(axes[0], A_result, A_curves)
        plot_clip(axes[1], B_result, B_curves)
        plt.tight_layout()
        plt.show()


if __name__ == "__main__":
    main()