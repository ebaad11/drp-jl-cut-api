"""
Cuts Model Module
Data structures and logic for detecting eligible cut boundaries in a timeline.
"""

from dataclasses import dataclass
from typing import List, Optional
import xml.etree.ElementTree as ET
from resolve_parse import get_clip_property, parse_int_property


@dataclass
class ClipPair:
    """
    Represents a matched video/audio clip pair.
    """
    video_clip: ET.Element
    audio_clip: ET.Element
    name: str
    start: int
    duration: int
    in_point: int
    media_ref: str
    
    def __repr__(self):
        return f"ClipPair(name={self.name}, start={self.start}, duration={self.duration}, in={self.in_point})"


@dataclass
class Boundary:
    """
    Represents a cut boundary between two clip pairs.
    """
    clip_pair_before: ClipPair
    clip_pair_after: ClipPair
    cut_frame: int  # The frame number where the cut occurs
    
    def __repr__(self):
        return f"Boundary(cut_frame={self.cut_frame}, before={self.clip_pair_before.name}, after={self.clip_pair_after.name})"


def find_clip_pairs(video_clips: List[ET.Element], audio_clips: List[ET.Element]) -> List[ClipPair]:
    """
    Match video and audio clips into pairs based on Name, MediaRef, and Start.
    
    Args:
        video_clips: List of Sm2TiVideoClip elements
        audio_clips: List of Sm2TiAudioClip elements
        
    Returns:
        List of ClipPair objects, sorted by start time
    """
    pairs = []
    
    # Create a lookup for audio clips by (Name, MediaRef, Start)
    audio_lookup = {}
    for audio_clip in audio_clips:
        name = get_clip_property(audio_clip, "Name") or ""
        media_ref = get_clip_property(audio_clip, "MediaRef") or ""
        start = parse_int_property(audio_clip, "Start")
        
        key = (name, media_ref, start)
        audio_lookup[key] = audio_clip
    
    # Match video clips with audio clips
    for video_clip in video_clips:
        name = get_clip_property(video_clip, "Name") or ""
        media_ref = get_clip_property(video_clip, "MediaRef") or ""
        start = parse_int_property(video_clip, "Start")
        duration = parse_int_property(video_clip, "Duration")
        in_point = parse_int_property(video_clip, "In")
        
        key = (name, media_ref, start)
        
        if key in audio_lookup:
            audio_clip = audio_lookup[key]
            
            pair = ClipPair(
                video_clip=video_clip,
                audio_clip=audio_clip,
                name=name,
                start=start,
                duration=duration,
                in_point=in_point,
                media_ref=media_ref
            )
            pairs.append(pair)
    
    # Sort by start time
    pairs.sort(key=lambda p: p.start)
    
    return pairs


def is_aligned(clip_pair: ClipPair) -> bool:
    """
    Check if a clip pair has aligned video and audio.
    
    Args:
        clip_pair: ClipPair to check
        
    Returns:
        True if video and audio have same Start, Duration, and In
    """
    video = clip_pair.video_clip
    audio = clip_pair.audio_clip
    
    v_start = parse_int_property(video, "Start")
    a_start = parse_int_property(audio, "Start")
    
    v_duration = parse_int_property(video, "Duration")
    a_duration = parse_int_property(audio, "Duration")
    
    v_in = parse_int_property(video, "In")
    a_in = parse_int_property(audio, "In")
    
    return (v_start == a_start and 
            v_duration == a_duration and 
            v_in == a_in)


def find_eligible_boundaries(clip_pairs: List[ClipPair], max_gap: int = 10) -> List[Boundary]:
    """
    Find all eligible cut boundaries where J/L cuts can be applied.
    
    A boundary is eligible if:
    - Both clip pairs (before and after) have aligned A/V
    - The clips are consecutive or have a small gap (within max_gap frames)
    
    Args:
        clip_pairs: List of ClipPair objects
        max_gap: Maximum gap in frames between clips (default 10)
        
    Returns:
        List of Boundary objects
    """
    boundaries = []
    
    for i in range(len(clip_pairs) - 1):
        current_pair = clip_pairs[i]
        next_pair = clip_pairs[i + 1]
        
        # Check if both pairs are aligned
        if not is_aligned(current_pair):
            continue
        if not is_aligned(next_pair):
            continue
        
        # Calculate cut frame (where current clip ends)
        cut_frame = current_pair.start + current_pair.duration
        
        # Calculate gap between clips
        gap = next_pair.start - cut_frame
        
        # Check if clips are consecutive or have acceptable gap
        if 0 <= gap <= max_gap:
            boundary = Boundary(
                clip_pair_before=current_pair,
                clip_pair_after=next_pair,
                cut_frame=cut_frame
            )
            boundaries.append(boundary)
    
    return boundaries


def get_boundary_info(boundary: Boundary) -> dict:
    """
    Get detailed information about a boundary for display.
    
    Args:
        boundary: Boundary object
        
    Returns:
        Dictionary with boundary information
    """
    before = boundary.clip_pair_before
    after = boundary.clip_pair_after
    
    return {
        'cut_frame': boundary.cut_frame,
        'before_name': before.name,
        'before_start': before.start,
        'before_duration': before.duration,
        'before_end': before.start + before.duration,
        'after_name': after.name,
        'after_start': after.start,
        'after_duration': after.duration,
        'after_end': after.start + after.duration
    }


def validate_boundary_for_offset(boundary: Boundary, offset: int) -> tuple[bool, str]:
    """
    Check if a boundary can safely accommodate the given offset.
    
    Args:
        boundary: Boundary to check
        offset: Offset in frames
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check if clips are long enough
    min_duration = offset * 2
    
    if boundary.clip_pair_before.duration < min_duration:
        return False, f"Clip before ({boundary.clip_pair_before.name}) too short for offset {offset}"
    
    if boundary.clip_pair_after.duration < min_duration:
        return False, f"Clip after ({boundary.clip_pair_after.name}) too short for offset {offset}"
    
    # Check if offset would push start time negative (for J-cut)
    after_new_start = boundary.clip_pair_after.start - offset
    if after_new_start < 0:
        return False, f"Offset would push next clip start below 0"
    
    # Check if offset would push in point negative (for J-cut)
    after_in = parse_int_property(boundary.clip_pair_after.audio_clip, "In")
    after_new_in = after_in - offset
    if after_new_in < 0:
        return False, f"Offset would push next clip in point below 0"
    
    return True, ""


# Module self-test
if __name__ == "__main__":
    import sys
    from pathlib import Path
    from drp_io import unpack_drp, cleanup_temp
    from resolve_parse import find_sequence_files, get_timeline_info, get_track_items
    
    if len(sys.argv) < 2:
        print("Usage: python cuts_model.py <path_to_drp_file>")
        print("This will test cut detection logic")
        sys.exit(1)
    
    drp_file = sys.argv[1]
    
    print(f"\n=== Testing Cuts Model Module ===")
    print(f"Input file: {drp_file}\n")
    
    try:
        # Extract and parse DRP
        print("1. Extracting and parsing DRP...")
        temp_dir = unpack_drp(drp_file)
        seq_files = find_sequence_files(temp_dir)
        
        for seq_file in seq_files:
            print(f"\n   Processing: {Path(seq_file).name}")
            
            # Get timeline info
            info = get_timeline_info(seq_file)
            video_clips = info['video_clips']
            audio_clips = info['audio_clips']
            
            print(f"   - Found {len(video_clips)} video clips, {len(audio_clips)} audio clips")
            
            # Find clip pairs
            print("\n2. Finding clip pairs...")
            clip_pairs = find_clip_pairs(video_clips, audio_clips)
            print(f"   Found {len(clip_pairs)} matched clip pairs:")
            
            for i, pair in enumerate(clip_pairs):
                aligned = "✓ aligned" if is_aligned(pair) else "✗ not aligned"
                print(f"   {i+1}. {pair.name} (start={pair.start}, duration={pair.duration}) {aligned}")
            
            # Find boundaries
            print("\n3. Finding eligible boundaries...")
            boundaries = find_eligible_boundaries(clip_pairs)
            print(f"   Found {len(boundaries)} eligible cut boundaries:")
            
            for i, boundary in enumerate(boundaries):
                info = get_boundary_info(boundary)
                print(f"\n   Boundary {i+1}:")
                print(f"   - Cut at frame: {info['cut_frame']}")
                print(f"   - Before: {info['before_name']} (frames {info['before_start']}-{info['before_end']})")
                print(f"   - After: {info['after_name']} (frames {info['after_start']}-{info['after_end']})")
                
                # Test validation with different offsets
                print(f"   - Validation:")
                for offset in [4, 8, 12, 20]:
                    valid, msg = validate_boundary_for_offset(boundary, offset)
                    status = "✓" if valid else "✗"
                    result = "OK" if valid else msg
                    print(f"     {status} Offset {offset}: {result}")
        
        # Cleanup
        print("\n4. Cleaning up...")
        cleanup_temp(temp_dir)
        
        print("\n=== All tests passed! ===\n")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

