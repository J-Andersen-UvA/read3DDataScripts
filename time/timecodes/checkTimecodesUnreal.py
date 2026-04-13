import argparse
import sys

import fbx
import FbxCommon

import json
import struct


candidatePropertyNames = [
    "TCHour",
    "TCMinute",
    "TCSecond",
    "TCFrame",
    "TCSubframe",
    "TCRate",
    "TCSlate",
    "Slate",
    "Take",
]

candidateNameSet = {name.lower() for name in candidatePropertyNames}


# -----------------------------
# common helpers
# -----------------------------

def getNodePath(node):
    parts = []
    current = node
    while current:
        name = nodeName(current)
        if name:
            parts.append(name)
        current = current.GetParent()
    return "\\".join(reversed(parts))


def nodeName(node):
    name = node.GetName()
    try:
        return str(name)
    except Exception:
        return f"{name}"


def safeString(value):
    try:
        return str(value)
    except Exception:
        try:
            return f"{value}"
        except Exception:
            return "<unreadable>"


def formatTimecode(hour, minute, second, frame):
    try:
        return f"{int(hour):02d}:{int(minute):02d}:{int(second):02d}:{int(frame):02d}"
    except Exception:
        return "<invalid>"


def valueOrMissing(value):
    if value is None:
        return "<missing>"
    return value


# -----------------------------
# FBX helpers
# -----------------------------

def iterProperties(node):
    prop = node.GetFirstProperty()
    while prop.IsValid():
        yield prop
        prop = node.GetNextProperty(prop)


def getPropertyTypeName(prop):
    try:
        return safeString(prop.GetPropertyDataType().GetName())
    except Exception:
        return "Unknown"


def getPropertyValue(prop):
    typeName = getPropertyTypeName(prop)

    try:
        if typeName in {"Bool", "bool"}:
            return fbx.FbxPropertyBool1(prop).Get()
        if typeName in {"Integer", "int"}:
            return fbx.FbxPropertyInteger1(prop).Get()
        if typeName in {"Float"}:
            return fbx.FbxPropertyFloat1(prop).Get()
        if typeName in {"Double", "Number", "double"}:
            return fbx.FbxPropertyDouble1(prop).Get()
        if typeName in {"KString", "String", "string"}:
            return safeString(fbx.FbxPropertyString(prop).Get())
    except Exception:
        pass

    wrappers = [
        fbx.FbxPropertyInteger1,
        fbx.FbxPropertyDouble1,
        fbx.FbxPropertyFloat1,
        fbx.FbxPropertyString,
        fbx.FbxPropertyBool1,
    ]

    for wrapper in wrappers:
        try:
            wrapped = wrapper(prop)
            if wrapped.IsValid():
                value = wrapped.Get()
                if wrapper is fbx.FbxPropertyString:
                    return safeString(value)
                return value
        except Exception:
            pass

    try:
        value = prop.Get()
        return safeString(value) if typeName in {"KString", "String", "string"} else value
    except Exception:
        return f"<unreadable:{typeName}>"


def getAnimCurve(prop, animLayer):
    try:
        curve = prop.GetCurve(animLayer)
        if curve:
            return curve
    except Exception:
        pass

    try:
        curve = prop.GetCurve(animLayer, "")
        if curve:
            return curve
    except Exception:
        pass

    return None


def getAnimatedPropertyValue(prop, animLayer, fbxTime):
    typeName = getPropertyTypeName(prop)

    curve = getAnimCurve(prop, animLayer)
    if curve is None:
        return None

    try:
        value = curve.Evaluate(fbxTime)
        if typeName in {"Integer", "int"}:
            return int(round(value))
        return value
    except Exception:
        pass

    try:
        keyCount = curve.KeyGetCount()
        if keyCount > 0:
            value = curve.KeyGetValue(0)
            if typeName in {"Integer", "int"}:
                return int(round(value))
            return value
    except Exception:
        pass

    return None


def getAnimatedOrStaticValue(prop, animLayer, fbxTime):
    animated = getAnimatedPropertyValue(prop, animLayer, fbxTime)
    if animated is not None:
        return animated, True
    return getPropertyValue(prop), False


def findRootBone(rootNode):
    for i in range(rootNode.GetChildCount()):
        result = findRootBoneRecursive(rootNode.GetChild(i))
        if result is not None:
            return result
    return None


def findRootBoneRecursive(node):
    attr = node.GetNodeAttribute()
    if attr:
        try:
            attrType = attr.GetAttributeType()
            enumType = getattr(fbx.FbxNodeAttribute, "EType", None)
            if enumType is not None and attrType == enumType.eSkeleton:
                return node
        except Exception:
            pass

    for i in range(node.GetChildCount()):
        result = findRootBoneRecursive(node.GetChild(i))
        if result is not None:
            return result

    return None


def iterSkeletonNodes(node):
    attr = node.GetNodeAttribute()
    if attr:
        try:
            attrType = attr.GetAttributeType()
            enumType = getattr(fbx.FbxNodeAttribute, "EType", None)
            if enumType is not None and attrType == enumType.eSkeleton:
                yield node
        except Exception:
            pass

    for i in range(node.GetChildCount()):
        yield from iterSkeletonNodes(node.GetChild(i))


def findProperty(node, wantedName):
    wantedLower = wantedName.lower()
    for prop in iterProperties(node):
        name = safeString(prop.GetName())
        if name and name.lower() == wantedLower:
            return prop
    return None


def getFirstAnimStack(scene):
    count = scene.GetSrcObjectCount(fbx.FbxCriteria.ObjectType(fbx.FbxAnimStack.ClassId))
    if count <= 0:
        return None
    return scene.GetSrcObject(fbx.FbxCriteria.ObjectType(fbx.FbxAnimStack.ClassId), 0)


def getFirstAnimLayer(animStack):
    if animStack is None:
        return None
    count = animStack.GetSrcObjectCount(fbx.FbxCriteria.ObjectType(fbx.FbxAnimLayer.ClassId))
    if count <= 0:
        return None
    return animStack.GetSrcObject(fbx.FbxCriteria.ObjectType(fbx.FbxAnimLayer.ClassId), 0)


def getStackStartTime(animStack):
    if animStack is None:
        return fbx.FbxTime()
    return animStack.GetLocalTimeSpan().GetStart()


def printAnimStacks(scene):
    animStackCount = scene.GetSrcObjectCount(
        fbx.FbxCriteria.ObjectType(fbx.FbxAnimStack.ClassId)
    )
    print(f"Animation stacks: {animStackCount}")

    for i in range(animStackCount):
        animStack = scene.GetSrcObject(
            fbx.FbxCriteria.ObjectType(fbx.FbxAnimStack.ClassId), i
        )
        timeSpan = animStack.GetLocalTimeSpan()
        start = timeSpan.GetStart()
        end = timeSpan.GetStop()
        frameRate = fbx.FbxTime.GetFrameRate(
            scene.GetGlobalSettings().GetTimeMode()
        )

        print(f"  Stack: {safeString(animStack.GetName())}")
        print(f"    Start: {start.GetTimeString()}")
        print(f"    End:   {end.GetTimeString()}")
        print(f"    FPS:   {frameRate}")
    print("")


def buildStartTimecodeInfo(node, animLayer, fbxTime):
    values = {}
    animatedFlags = {}

    for name in candidatePropertyNames:
        prop = findProperty(node, name)
        if prop is None:
            values[name] = None
            animatedFlags[name] = False
            continue

        value, isAnimated = getAnimatedOrStaticValue(prop, animLayer, fbxTime)
        values[name] = value
        animatedFlags[name] = isAnimated

    slateValue = values["TCSlate"] if values["TCSlate"] is not None else values["Slate"]

    startTimecode = None
    if all(values[name] is not None for name in ["TCHour", "TCMinute", "TCSecond", "TCFrame"]):
        startTimecode = formatTimecode(
            values["TCHour"],
            values["TCMinute"],
            values["TCSecond"],
            values["TCFrame"],
        )

    return {
        "startTimecode": startTimecode,
        "hour": values["TCHour"],
        "minute": values["TCMinute"],
        "second": values["TCSecond"],
        "frame": values["TCFrame"],
        "subframe": values["TCSubframe"],
        "rate": values["TCRate"],
        "slate": slateValue,
        "take": values["Take"],
        "animatedFlags": animatedFlags,
    }


def printStartTimecode(node, animLayer, fbxTime, label):
    info = buildStartTimecodeInfo(node, animLayer, fbxTime)

    print(f"{label}: {nodeName(node)}")
    print(f"Path: {getNodePath(node)}")
    print(f"Start TC:  {valueOrMissing(info['startTimecode'])}")
    print(f"TC Rate:   {valueOrMissing(info['rate'])}")
    print(f"TC Subf:   {valueOrMissing(info['subframe'])}")
    print(f"Slate:     {valueOrMissing(info['slate'])}")
    print(f"Take:      {valueOrMissing(info['take'])}")

    animatedNames = [
        name for name, isAnimated in info["animatedFlags"].items() if isAnimated
    ]
    if animatedNames:
        print(f"Animated:  {', '.join(animatedNames)}")
    else:
        print("Animated:  <none>")
    print("")


def printAllUserDefinedRootProps(rootBone, animLayer, fbxTime):
    print("All user-defined properties on root bone:\n")

    for prop in iterProperties(rootBone):
        name = safeString(prop.GetName())
        if not name:
            continue

        if not prop.GetFlag(fbx.FbxPropertyFlags.EFlags.eUserDefined):
            continue

        typeName = getPropertyTypeName(prop)
        value, isAnimated = getAnimatedOrStaticValue(prop, animLayer, fbxTime)

        print(f"Property: {name}")
        print(f"  Type: {typeName}")
        print(f"  Value: {value}")
        print(f"  Source: {'animated' if isAnimated else 'static'}")
        print("")


def findBestTimecodeNode(rootNode, animLayer, fbxTime):
    bestNode = None
    bestScore = -1

    for node in iterSkeletonNodes(rootNode):
        info = buildStartTimecodeInfo(node, animLayer, fbxTime)

        score = 0
        if info["startTimecode"] is not None:
            score += 10
        if info["hour"] not in (None, 0):
            score += 3
        if info["minute"] not in (None, 0):
            score += 3
        if info["second"] not in (None, 0):
            score += 3
        if info["frame"] not in (None, 0):
            score += 3

        if score > bestScore:
            bestScore = score
            bestNode = node

    return bestNode


# -----------------------------
# GLB
# -----------------------------

def readGlbJson(path):
    with open(path, "rb") as f:
        data = f.read()

    magic, version, length = struct.unpack_from("<III", data, 0)
    if magic != 0x46546C67:
        raise RuntimeError("Not a GLB file")

    offset = 12
    jsonChunk = None

    while offset < length:
        chunkLen, chunkType = struct.unpack_from("<II", data, offset)
        offset += 8

        chunkData = data[offset: offset + chunkLen]
        offset += chunkLen

        if chunkType == 0x4E4F534A:
            jsonChunk = chunkData

    if jsonChunk is None:
        raise RuntimeError("GLB missing JSON chunk")

    return json.loads(jsonChunk.decode("utf-8"))


def extractTimecodeFromExtras(extras):
    if not isinstance(extras, dict):
        return None

    result = {}
    for name in candidatePropertyNames:
        if name in extras:
            result[name] = extras[name]

    return result if result else None


def scanGlb(path):
    doc = readGlbJson(path)

    print(f"GLB: {path}\n")

    nodes = doc.get("nodes", [])

    for i, node in enumerate(nodes):
        extras = node.get("extras")
        tc = extractTimecodeFromExtras(extras)
        if not tc:
            continue

        name = node.get("name", f"node_{i}")

        hour = tc.get("TCHour")
        minute = tc.get("TCMinute")
        second = tc.get("TCSecond")
        frame = tc.get("TCFrame")

        startTc = None
        if None not in (hour, minute, second, frame):
            startTc = formatTimecode(hour, minute, second, frame)

        print(f"Node: {name}")
        print(f"Start TC:  {startTc}")
        print(f"TC Rate:   {tc.get('TCRate')}")
        print(f"TC Subf:   {tc.get('TCSubframe')}")
        print(f"Slate:     {tc.get('TCSlate') or tc.get('Slate')}")
        print(f"Take:      {tc.get('Take')}")
        print("")


# -----------------------------
# main
# -----------------------------

def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--fbx", help="Path to FBX file")
    parser.add_argument("--glb", help="Path to GLB file")

    parser.add_argument(
        "--dumpAllUserProps",
        action="store_true",
    )

    parser.add_argument(
        "--scanAllBones",
        action="store_true",
    )

    args = parser.parse_args()

    # ---- GLB mode ----
    if args.glb:
        scanGlb(args.glb)
        return

    if not args.fbx:
        print("Provide --fbx or --glb")
        return

    # ---- FBX mode ----
    manager, scene = FbxCommon.InitializeSdkObjects()

    try:
        ok = FbxCommon.LoadScene(manager, scene, args.fbx)
        if not ok:
            print(f"Failed to load FBX: {args.fbx}")
            sys.exit(1)

        print(f"FBX: {args.fbx}")
        printAnimStacks(scene)

        rootNode = scene.GetRootNode()
        rootBone = findRootBone(rootNode)

        animStack = getFirstAnimStack(scene)
        animLayer = getFirstAnimLayer(animStack)
        startTime = getStackStartTime(animStack)

        print("Start timecode summary:\n")
        printStartTimecode(rootBone, animLayer, startTime, "Root bone")

        if args.scanAllBones:
            bestNode = findBestTimecodeNode(rootNode, animLayer, startTime)
            if bestNode and bestNode != rootBone:
                print("Best match across all skeleton bones:\n")
                printStartTimecode(bestNode, animLayer, startTime, "Best bone")

        if args.dumpAllUserProps:
            print("")
            printAllUserDefinedRootProps(rootBone, animLayer, startTime)

    finally:
        manager.Destroy()


if __name__ == "__main__":
    main()