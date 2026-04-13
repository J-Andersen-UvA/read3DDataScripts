import argparse
import fbx
import FbxCommon
import matplotlib.pyplot as plt


def find_node_recursive(node, name):
    if node.GetName() == name:
        return node
    for i in range(node.GetChildCount()):
        result = find_node_recursive(node.GetChild(i), name)
        if result:
            return result
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
    return fps if fps > 0 else 30.0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fbx", required=True)
    parser.add_argument("--foot", required=True)
    parser.add_argument("--hips", required=True)
    parser.add_argument("--axis", default="Y", choices=["X", "Y", "Z", "x", "y", "z"])
    args = parser.parse_args()

    manager, scene = FbxCommon.InitializeSdkObjects()
    if not FbxCommon.LoadScene(manager, scene, args.fbx):
        raise RuntimeError("Failed to load FBX")

    root = scene.GetRootNode()

    foot_node = find_node_recursive(root, args.foot)
    hips_node = find_node_recursive(root, args.hips)

    if not foot_node:
        raise RuntimeError(f"Foot node '{args.foot}' not found")
    if not hips_node:
        raise RuntimeError(f"Hips node '{args.hips}' not found")

    start_time, end_time, stack_name = get_anim_time_span(scene)
    fps = get_fps(scene)
    time_mode = scene.GetGlobalSettings().GetTimeMode()

    axis_index = {"X": 0, "Y": 1, "Z": 2}[args.axis.upper()]

    start_s = start_time.GetSecondDouble()
    end_s = end_time.GetSecondDouble()
    total_frames = int(round((end_s - start_s) * fps))

    seconds = []
    foot_vals = []
    hips_vals = []
    relative_vals = []

    for f in range(total_frames + 1):
        t = fbx.FbxTime()
        t.SetFrame(f, time_mode)

        foot_t = foot_node.EvaluateGlobalTransform(t).GetT()
        hips_t = hips_node.EvaluateGlobalTransform(t).GetT()

        foot_y = float(foot_t[axis_index])
        hips_y = float(hips_t[axis_index])
        rel_y = foot_y - hips_y

        seconds.append(f / fps)
        foot_vals.append(foot_y)
        hips_vals.append(hips_y)
        relative_vals.append(rel_y)

    plt.figure()
    plt.plot(seconds, foot_vals, label="Foot Global Y")
    plt.plot(seconds, hips_vals, label="Hips Global Y")
    plt.plot(seconds, relative_vals, label="Foot - Hips")

    plt.xlabel("Time (seconds)")
    plt.ylabel(f"Axis {args.axis.upper()}")
    plt.title(f"{args.fbx.split('/')[-1]} | Stack: {stack_name} | FPS: {fps}")
    plt.legend()
    plt.show()

    manager.Destroy()


if __name__ == "__main__":
    main()