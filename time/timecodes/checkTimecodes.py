import fbx
import FbxCommon
import sys

def frames_to_timecode(frames, fps):
    total_seconds = frames / fps

    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = int(total_seconds % 60)
    milliseconds = int((total_seconds - int(total_seconds)) * 1000)

    return f"{hours:02}:{minutes:02}:{seconds:02}:{milliseconds:03}"

def check_fbx_timecodes(path):
    manager, scene = FbxCommon.InitializeSdkObjects()
    
    result = FbxCommon.LoadScene(manager, scene, path)
    if not result:
        print("Failed to load FBX file.")
        return
    
    anim_stack_count = scene.GetSrcObjectCount(
        fbx.FbxCriteria.ObjectType(fbx.FbxAnimStack.ClassId)
    )
    
    if anim_stack_count == 0:
        print("No animation stacks found. No timecodes present.")
        return
    
    print(f"Found {anim_stack_count} animation stack(s):\n")
    
    for i in range(anim_stack_count):
        anim_stack = scene.GetSrcObject(
            fbx.FbxCriteria.ObjectType(fbx.FbxAnimStack.ClassId), i
        )
        time_span = anim_stack.GetLocalTimeSpan()
        
        start = time_span.GetStart()
        end = time_span.GetStop()
        
        fps = fbx.FbxTime.GetFrameRate(
            scene.GetGlobalSettings().GetTimeMode()
        )

        start_frames = start.GetFrameCount()
        end_frames = end.GetFrameCount()
        frame_count = end_frames - start_frames

        start_tc = frames_to_timecode(start_frames, fps)
        end_tc = frames_to_timecode(end_frames, fps)
        duration_tc = frames_to_timecode(frame_count, fps)
        
        print(f"Animation Stack: {anim_stack.GetName()}")
        print(f"  Start Time: {start.GetTimeString()}  ({start_tc})")
        print(f"  End Time:   {end.GetTimeString()}  ({end_tc})")
        print(f"  Frame Count: {frame_count}  ({duration_tc})")
        print(f"  Frame Rate: {fps} fps\n")
    
    manager.Destroy()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python check_fbx_timecodes.py <path_to_fbx>")
    else:
        check_fbx_timecodes(sys.argv[1])