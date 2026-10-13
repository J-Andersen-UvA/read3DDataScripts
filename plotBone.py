import argparse
import math
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
    parser.add_argument("--bone", nargs="+")
    parser.add_argument("--foot")
    parser.add_argument("--hips")
    parser.add_argument(
        "--mode",
        default="position",
        choices=["position", "averageAcceleration", "averageAngularAcceleration"],
    )
    parser.add_argument(
        "--space",
        default="global",
        choices=["global", "local", "reference"],
    )
    parser.add_argument("--referenceBone")
    parser.add_argument("--axis", default="Y", choices=["X", "Y", "Z", "x", "y", "z"])
    args = parser.parse_args()

    if args.bone and (args.foot or args.hips):
        parser.error("Use either --bone or both --foot and --hips")
    if not args.bone and not (args.foot and args.hips):
        parser.error("Provide --bone, or provide both --foot and --hips")
    if args.mode in ("averageAcceleration", "averageAngularAcceleration") and not args.bone:
        parser.error(f"{args.mode} mode requires --bone")
    if args.space == "local" and not args.bone:
        parser.error("Local space requires --bone")
    if args.mode == "averageAngularAcceleration" and args.space != "local":
        parser.error("averageAngularAcceleration mode requires --space local")
    if args.referenceBone and args.space != "reference":
        parser.error("--referenceBone can only be used with --space reference")

    manager, scene = FbxCommon.InitializeSdkObjects()
    if not FbxCommon.LoadScene(manager, scene, args.fbx):
        raise RuntimeError("Failed to load FBX")

    root = scene.GetRootNode()

    if args.bone:
        boneNodes = []
        for boneName in args.bone:
            boneNode = find_node_recursive(root, boneName)
            if not boneNode:
                raise RuntimeError(f"Bone node '{boneName}' not found")
            boneNodes.append((boneName, boneNode))

        if args.space == "reference":
            referenceBoneName = args.referenceBone or args.bone[0]
            referenceBoneNode = find_node_recursive(root, referenceBoneName)
            if not referenceBoneNode:
                raise RuntimeError(f"Reference bone node '{referenceBoneName}' not found")

            boneNodes = [
                (boneName, boneNode)
                for boneName, boneNode in boneNodes
                if boneName != referenceBoneName
            ]
            if not boneNodes:
                raise RuntimeError("Local space requires at least one bone besides the reference bone")
    else:
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
    boneTranslations = {boneName: [] for boneName, _ in boneNodes} if args.bone else {}
    boneRotations = {boneName: [] for boneName, _ in boneNodes} if args.bone else {}
    foot_vals = []
    hips_vals = []
    relative_vals = []

    for f in range(total_frames + 1):
        t = fbx.FbxTime()
        t.SetFrame(f, time_mode)

        seconds.append(f / fps)

        if args.bone:
            if args.space == "reference":
                referenceInverse = referenceBoneNode.EvaluateGlobalTransform(t).Inverse()

            for boneName, boneNode in boneNodes:
                if args.space == "local":
                    boneTransform = boneNode.EvaluateLocalTransform(t)
                else:
                    boneTransform = boneNode.EvaluateGlobalTransform(t)
                    if args.space == "reference":
                        boneTransform = referenceInverse * boneTransform

                translation = boneTransform.GetT()
                boneTranslations[boneName].append(
                    (
                        float(translation[0]),
                        float(translation[1]),
                        float(translation[2]),
                    )
                )

                if args.mode == "averageAngularAcceleration":
                    rotation = boneTransform.GetR()
                    rotationValues = [float(rotation[component]) for component in range(3)]
                    previousRotations = boneRotations[boneName]
                    if previousRotations:
                        previous = previousRotations[-1]
                        for component in range(3):
                            while rotationValues[component] - previous[component] > 180.0:
                                rotationValues[component] -= 360.0
                            while rotationValues[component] - previous[component] < -180.0:
                                rotationValues[component] += 360.0
                    previousRotations.append(tuple(rotationValues))
        else:
            foot_t = foot_node.EvaluateGlobalTransform(t).GetT()
            hips_t = hips_node.EvaluateGlobalTransform(t).GetT()

            foot_value = float(foot_t[axis_index])
            hips_value = float(hips_t[axis_index])

            foot_vals.append(foot_value)
            hips_vals.append(hips_value)
            relative_vals.append(foot_value - hips_value)

    plt.figure()
    axis = args.axis.upper()

    if args.bone:
        if args.mode in ("averageAcceleration", "averageAngularAcceleration"):
            if args.mode == "averageAngularAcceleration":
                movementValues = boneRotations
                plotLabel = "Average parent-local angular acceleration magnitude"
                yLabel = "Angular acceleration magnitude (degrees/s²)"
            else:
                movementValues = boneTranslations
                plotLabel = f"Average 3D acceleration magnitude ({args.space} space)"
                yLabel = "Acceleration magnitude (units/s²)"

            averageAcceleration = []
            for frameIndex in range(1, len(seconds) - 1):
                accelerationMagnitudes = []
                for values in movementValues.values():
                    previous = values[frameIndex - 1]
                    current = values[frameIndex]
                    following = values[frameIndex + 1]
                    acceleration = [
                        (following[component] - 2 * current[component] + previous[component])
                        * fps**2
                        for component in range(3)
                    ]
                    accelerationMagnitudes.append(
                        math.sqrt(sum(value**2 for value in acceleration))
                    )
                averageAcceleration.append(
                    sum(accelerationMagnitudes) / len(accelerationMagnitudes)
                )

            plt.plot(
                seconds[1:-1],
                averageAcceleration,
                label=plotLabel,
            )
            plt.ylabel(yLabel)
        else:
            for boneName, translations in boneTranslations.items():
                values = [translation[axis_index] for translation in translations]
                plt.plot(seconds, values, label=f"{boneName} {args.space.title()} {axis}")
            plt.ylabel(f"Axis {axis}")
    else:
        plt.plot(seconds, foot_vals, label=f"Foot Global {axis}")
        plt.plot(seconds, hips_vals, label=f"Hips Global {axis}")
        plt.plot(seconds, relative_vals, label=f"Foot - Hips {axis}")
        plt.ylabel(f"Axis {axis}")

    plt.xlabel("Time (seconds)")
    plt.title(f"{args.fbx.split('/')[-1]} | Stack: {stack_name} | FPS: {fps}")
    plt.legend()
    plt.show()

    manager.Destroy()


if __name__ == "__main__":
    main()
