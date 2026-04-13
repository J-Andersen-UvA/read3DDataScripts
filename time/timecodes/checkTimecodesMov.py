import json
import subprocess
import sys
import math

def runFfprobe(path):
    cmd = [
        "ffprobe",
        "-v", "error",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        path
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "ffprobe failed")

    return json.loads(result.stdout)

def getTag(tags, key):
    if not tags:
        return None

    for tagKey, value in tags.items():
        if tagKey.lower() == key.lower():
            return value

    return None

def parseFrameRate(rateString):
    if not rateString or rateString == "0/0":
        return None

    num, den = rateString.split("/")
    return float(num) / float(den)

def timecodeToFrames(timecode, fps):
    tc = timecode.strip()
    isDropFrame = ";" in tc

    clean = tc.replace(";", ":")
    parts = clean.split(":")
    if len(parts) != 4:
        raise ValueError(f"Unsupported timecode format: {timecode}")

    hh, mm, ss, ff = [int(x) for x in parts]

    if not isDropFrame:
        nominalFps = round(fps)
        totalSeconds = hh * 3600 + mm * 60 + ss
        return totalSeconds * nominalFps + ff

    if not (math.isclose(fps, 29.97, abs_tol=0.01) or math.isclose(fps, 59.94, abs_tol=0.01)):
        raise ValueError(f"Drop-frame timecode only implemented for 29.97/59.94 fps, got {fps}")

    if math.isclose(fps, 29.97, abs_tol=0.01):
        nominalFps = 30
        dropFrames = 2
    else:
        nominalFps = 60
        dropFrames = 4

    totalMinutes = hh * 60 + mm
    dropped = dropFrames * (totalMinutes - totalMinutes // 10)

    totalFrames = ((hh * 3600 + mm * 60 + ss) * nominalFps + ff) - dropped
    return totalFrames

def framesToTimecode(frames, fps):
    totalSeconds = frames / fps

    hours = int(totalSeconds // 3600)
    minutes = int((totalSeconds % 3600) // 60)
    seconds = int(totalSeconds % 60)
    milliseconds = int((totalSeconds - int(totalSeconds)) * 1000)

    return f"{hours:02}:{minutes:02}:{seconds:02}:{milliseconds:03}"

def checkMovTimecode(path):
    data = runFfprobe(path)

    formatInfo = data.get("format", {})
    streams = data.get("streams", [])

    formatTags = formatInfo.get("tags", {})
    durationString = formatInfo.get("duration")
    durationSeconds = float(durationString) if durationString is not None else None

    videoStream = next((s for s in streams if s.get("codec_type") == "video"), None)
    timecodeStream = next((s for s in streams if s.get("codec_tag_string") == "tmcd"), None)

    videoTags = videoStream.get("tags", {}) if videoStream else {}
    timecodeTags = timecodeStream.get("tags", {}) if timecodeStream else {}

    timecode = (
        getTag(timecodeTags, "timecode")
        or getTag(videoTags, "timecode")
        or getTag(formatTags, "timecode")
    )

    frameRate = None
    if videoStream:
        frameRate = parseFrameRate(videoStream.get("avg_frame_rate")) or parseFrameRate(videoStream.get("r_frame_rate"))

    print(f"File: {path}")

    if durationSeconds is not None:
        print(f"Duration Seconds: {durationSeconds:.3f}")
    else:
        print("Duration Seconds: not found")

    if durationSeconds is not None:
        print(f"Duration hh:mm:ss:ms: {framesToTimecode(durationSeconds * (frameRate or 1), frameRate or 1)}")
    else:
        print("Duration hh:mm:ss:ms: not found")

    if frameRate is not None:
        print(f"Frame Rate: {frameRate:.3f} fps")
    else:
        print("Frame Rate: not found")

    if timecode:
        print(f"Start Timecode: {timecode}")
    else:
        print("Start Timecode: not found")

    if timecodeStream:
        print("Timecode Track: yes")
    else:
        print("Timecode Track: no explicit tmcd track found")

    if timecode and frameRate is not None:
        try:
            startFrame = timecodeToFrames(timecode, frameRate)
            print(f"Start Frame: {startFrame}")

            if durationSeconds is not None:
                durationFrames = round(durationSeconds * frameRate)
                endFrameExclusive = startFrame + durationFrames
                endFrameInclusive = endFrameExclusive - 1

                print(f"Duration Frames: {durationFrames}")
                print(f"End Frame Inclusive: {endFrameInclusive}")
                print(f"End Frame Exclusive: {endFrameExclusive}")
        except ValueError as e:
            print(f"Start Frame: could not calculate ({e})")
    else:
        print("Start Frame: could not calculate")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python checkMovTimecode.py <path_to_mov>")
    else:
        checkMovTimecode(sys.argv[1])