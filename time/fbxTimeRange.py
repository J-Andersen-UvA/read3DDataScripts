import argparse
import json
from pathlib import Path

import fbx


def loadScene(fbxPath: Path) -> fbx.FbxScene:
    manager = fbx.FbxManager.Create()
    ios = fbx.FbxIOSettings.Create(manager, fbx.IOSROOT)
    manager.SetIOSettings(ios)

    importer = fbx.FbxImporter.Create(manager, "")
    if not importer.Initialize(str(fbxPath), -1, manager.GetIOSettings()):
        raise RuntimeError(f"FBX import init failed: {importer.GetStatus().GetErrorString()}")

    scene = fbx.FbxScene.Create(manager, "scene")
    if not importer.Import(scene):
        raise RuntimeError(f"FBX import failed: {importer.GetStatus().GetErrorString()}")

    importer.Destroy()
    return scene


def getBestTimeSpan(scene: fbx.FbxScene) -> fbx.FbxTimeSpan:
    gs = scene.GetGlobalSettings()

    # Prefer animation stack span if available
    animStack = scene.GetCurrentAnimationStack()
    if animStack is None and scene.GetSrcObjectCount(fbx.FbxCriteria.ObjectType(fbx.FbxAnimStack.ClassId)) > 0:
        animStack = scene.GetSrcObject(fbx.FbxCriteria.ObjectType(fbx.FbxAnimStack.ClassId), 0)

    if animStack is not None:
        span = animStack.GetLocalTimeSpan()
        start = fbx.FbxTime()
        stop = fbx.FbxTime()
        start = span.GetStart()
        stop = span.GetStop()
        if start.Get() != 0 or stop.Get() != 0:
            return span

    # Fallback: timeline default
    return gs.GetTimelineDefaultTimeSpan()


def getAnimRange(fbxPath: Path) -> dict:
    scene = loadScene(fbxPath)

    gs = scene.GetGlobalSettings()
    timeMode = gs.GetTimeMode()

    fps = float(fbx.FbxTime.GetFrameRate(timeMode))

    span = getBestTimeSpan(scene)
    start = fbx.FbxTime()
    stop = fbx.FbxTime()
    start = span.GetStart()
    stop = span.GetStop()

    # Frame counts in the scene's time mode
    startFrame = int(start.GetFrameCount(timeMode))
    endFrame = int(stop.GetFrameCount(timeMode))

    # Some pipelines treat stop as inclusive; others as exclusive.
    # Here we return the raw FBX span frames, plus a derived duration in frames.
    durationFrames = max(0, endFrame - startFrame)

    return {
        "fbxPath": str(fbxPath),
        "fps": fps,
        "startFrame": startFrame,
        "endFrame": endFrame,
        "durationFrames": durationFrames,
        "timeMode": str(timeMode),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fbx", required=True, help="Path to .fbx")
    ap.add_argument("--outJson", default="", help="Optional path to write JSON result")
    args = ap.parse_args()

    result = getAnimRange(Path(args.fbx))

    if args.outJson:
        outPath = Path(args.outJson)
        outPath.parent.mkdir(parents=True, exist_ok=True)
        outPath.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    else:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()