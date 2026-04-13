To timecode we use a tentacle sync E that jam syncs the Vicon Lock.

## Live recordings
### Vicon
To set that up read [[Genlocking - Timecoding - Vicon]].
### iPhone
The iPhone can read from the same tentacle sync E:
1. Go to Settings in LLF
2. Timecode
3. Set it to the Tentacle Sync that is used by the Lock
If you cannot find it, make sure to detect it first in the Tentacle app in the iPhone.

### Unreal Engine
We don't read directly from the tentacle sync in Unreal Engine, instead we define the Vicon stream as the Timecode Provider.
To accomplish this we need to set up a few things:
1. Enable the timed data monitor plugin
2. Add the live link sources (usually ARKit, Vicon, and a camera if you want)
3. Set the evaluation modes to Timecode
4. Reuse or make a new Blueprint class: timecodeprovider
	1. Inside the blueprint set the subject key to use the Vicon Live Link source
5. Use the shortcut to provider settings button to go to the Project Settings
	1. Under Timecode set the Timecode provider to the blueprint
6. Hit the calibrate button, observe the upper right of the Timed Data Monitor
	1. Its okay if the timing diagram line is aligned, but the indicator says that we are outside range.
	2. We don't want the Global Frame Offset to be set to anything, otherwise we will need to take that into account later for the not connected Unreal devices
7. In the TakeRecorder settings:
	1. Recording Clock Source: Tick
	2. Record Timecode: True
	3. Timecode Bone Method: All
![[TimedDataMonitor.png]]
*Why do we put the evaluation mode on Timecode and the ClockSource on Tick?*
**Clock Source: Tick**  
Use **Tick** so Take Recorder captures the final evaluated avatar each engine frame. This avoids delays caused by waiting for individual source timestamps after Unreal merges and solves multiple streams.

**Incoming Streams Evaluation: Timecode**  
Use **Timecode** so all incoming sources (Vicon, ARKit, etc.) are aligned to the same moment before Unreal evaluates them. This keeps body, face, and other inputs synchronized using the shared external clock.


## Exporting data out of the relevant software
We want to keep the timecodes intact when exporting out of the relevant software.

### Shogun Post
After importing the .mcp into Shogun Post, we need to keep in mind that the .mcp timecodes only work if the timecode method aligns with the recorded timecode method. So either check that by opening the .x2d file in post, looking at Shogun Live, remembering what you recorded with. Most likely you used 30hz (hsl command example `setFrameRate "30hz" 30.000000;`).

### Unreal
The timecodes are recorded on the bones through the Take Recorder.

### LLF
The timecodes are embedded on the .mov and on the csv's.

## Aligning the recordings
In post, we want to align the recorded data in the relevant software. The following examples are there to show how to retrieve the timecodes:
**Mov LLF**
```python
rootBone = findRootBone(rootNode)
prop = findProperty(rootBone, "TCHour")
value = getPropertyValue(prop)
print(value)
```
Reads embedded MOV timecode tag from ffprobe metadata.  

**Unreal FBX**
```python
rootBone = findRootBone(rootNode)
prop = findProperty(rootBone, "TCHour")
value = getPropertyValue(prop)
print(value)
```
Timecode is stored as user properties on bones (TCHour etc).  

**Vicon Shogun Post FBX**
```python
time_span = anim_stack.GetLocalTimeSpan()
start = time_span.GetStart().GetFrameCount()
fps = fbx.FbxTime.GetFrameRate(scene.GetGlobalSettings().GetTimeMode())
start_tc = frames_to_timecode(start, fps)
```
Reads animation stack start/end time from FBX scene.

