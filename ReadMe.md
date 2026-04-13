# read3DDataScripts
This repo is a collection of my scripts to read stuff from 3D data like animations and meshes (fbx and sometimes glb).
What follows is a small description of each script.

## plotBone.py
Plots motion from an FBX and visualizes relative movement over time. Takes two bone names and an axis, samples transforms per frame, and plots global foot, hips, and relative curves using matplotlib.

## footPress/diffPlotPress.py
Compares two FBX clips and plots detected foot press timing. Samples foot-hips relative motion, detects press using strongest negative velocity, and overlays curves with vertical markers for comparison. Designed for side-by-side debugging of contact timing.

## footPress/diffPress.py
Runs press detection on one or multiple FBX clips and outputs structured JSON plus optional plots. Computes foot-hips relative motion, finds minimum velocity frame, and records frame/time/value for pipeline usage. Intended for automated press detection.

## footPress/find_peak_fbx.py
Detects foot press frame using last local minimum (fallback to global minimum). Samples relative foot-hips motion across animation and returns press frame/time/value. Designed for robust detection across noisy animation.

## time/fbxTimeRange.py
Reads animation range from an FBX and outputs start frame, end frame, duration, and FPS. Prefers animation stack span and falls back to timeline default if needed. Useful for verifying clip duration and frame ranges.

## time/timecodes/checkTimecodes.py
Prints animation stack start/end timecodes for FBX files. Converts frames to HH:MM:SS.mmm format and reports duration and FPS. Used to inspect timeline-based FBX timecodes.

## time/timecodes/checkTimecodesMov.py
Reads MOV timecode metadata using ffprobe. Supports drop-frame timecodes, converts to frames, and prints duration, fps, and start timecode. Used for validating camera or capture timecodes.

## time/timecodes/checkTimecodesUnreal.py
Reads Unreal-style timecode metadata from FBX (animated custom properties) and GLB (extras). Resolves animated values at stack start and prints start TC, rate, subframe, slate, and take. Used to verify Unreal exported timecodes survived conversion.

