import fbx
import FbxCommon
import sys
import math


# ------------------------------------------------------------
# Utility
# ------------------------------------------------------------

def get_fps_from_time_mode(scene):
    time_mode = scene.GetGlobalSettings().GetTimeMode()
    return fbx.FbxTime.GetFrameRate(time_mode)


def find_node_recursive(node, name):
    if node.GetName() == name:
        return node
    for i in range(node.GetChildCount()):
        result = find_node_recursive(node.GetChild(i), name)
        if result:
            return result
    return None


def get_animation_time_span(scene):
    stack = scene.GetSrcObject(fbx.FbxCriteria.ObjectType(fbx.FbxAnimStack.ClassId), 0)
    if not stack:
        raise RuntimeError("No FbxAnimStack found in scene.")
    scene.SetCurrentAnimationStack(stack)

    time_span = stack.GetLocalTimeSpan()
    return time_span.GetStart(), time_span.GetStop()


def get_total_frames(start_time, end_time, fps):
    duration_s = end_time.GetSecondDouble() - start_time.GetSecondDouble()
    if duration_s <= 0:
        raise RuntimeError("Invalid animation duration.")
    return int(round(duration_s * fps))


def find_last_local_min(samples):
    # samples: List[(frame:int, value:float)]
    # local min: prev > curr <= next
    valleys = []
    for i in range(1, len(samples) - 1):
        prev_v = samples[i - 1][1]
        curr_v = samples[i][1]
        next_v = samples[i + 1][1]
        if prev_v > curr_v and curr_v <= next_v:
            valleys.append(samples[i])
    return valleys[-1] if valleys else None


# ------------------------------------------------------------
# Core logic
# ------------------------------------------------------------

def analyze_clip(
    fbx_path,
    foot_bone_name,
    hips_bone_name,
    axis='Y',
):
    manager, scene = FbxCommon.InitializeSdkObjects()
    result = FbxCommon.LoadScene(manager, scene, fbx_path)

    if not result:
        raise RuntimeError(f"Failed to load {fbx_path}")

    fps = float(get_fps_from_time_mode(scene))
    if fps <= 0:
        fps = 30.0

    start_time, end_time = get_animation_time_span(scene)
    total_frames = get_total_frames(start_time, end_time, fps)

    root = scene.GetRootNode()
    foot_node = find_node_recursive(root, foot_bone_name)
    hips_node = find_node_recursive(root, hips_bone_name)

    if not foot_node:
        raise RuntimeError(f"Foot bone '{foot_bone_name}' not found")
    if not hips_node:
        raise RuntimeError(f"Hips bone '{hips_bone_name}' not found")

    axis_index = {'X': 0, 'Y': 1, 'Z': 2}[axis.upper()]
    time_mode = scene.GetGlobalSettings().GetTimeMode()

    # Sample full clip: relativeY = footGlobalY - hipsGlobalY
    samples = []
    for f in range(0, total_frames + 1):
        t = fbx.FbxTime()
        t.SetFrame(f, time_mode)

        foot_t = foot_node.EvaluateGlobalTransform(t).GetT()
        hips_t = hips_node.EvaluateGlobalTransform(t).GetT()

        relative = (foot_t - hips_t)[axis_index]
        samples.append((f, float(relative)))

    # Prefer the LAST local minimum. If none exists, use global minimum.
    last_valley = find_last_local_min(samples)
    if last_valley is not None:
        press_frame, press_value = last_valley
        press_kind = "lastLocalMin"
    else:
        press_frame, press_value = min(samples, key=lambda x: x[1])
        press_kind = "globalMin"

    press_seconds = press_frame / fps

    manager.Destroy()

    return {
        "fbx": fbx_path,
        "foot": foot_bone_name,
        "hips": hips_bone_name,
        "axis": axis.upper(),
        "fps": fps,
        "press_frame": press_frame,
        "press_seconds": press_seconds,
        "press_value": press_value,
        "press_kind": press_kind,
    }


# ------------------------------------------------------------
# Comparison
# ------------------------------------------------------------

def compare_clips(a_path, a_foot, a_hips, b_path, b_foot, b_hips, axis='Y'):
    A = analyze_clip(a_path, a_foot, a_hips, axis=axis)
    B = analyze_clip(b_path, b_foot, b_hips, axis=axis)

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


# ------------------------------------------------------------
# Entry
# ------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) not in (7, 8):
        print("Usage:")
        print("python find_press_fbx.py fbxA footA hipsA fbxB footB hipsB [axis]")
        print('Example: python find_press_fbx.py a.fbx RightFoot Hips b.fbx RightFoot Hips Y')
        sys.exit(1)

    axis = sys.argv[7] if len(sys.argv) == 8 else 'Y'
    compare_clips(
        a_path=sys.argv[1],
        a_foot=sys.argv[2],
        a_hips=sys.argv[3],
        b_path=sys.argv[4],
        b_foot=sys.argv[5],
        b_hips=sys.argv[6],
        axis=axis
    )