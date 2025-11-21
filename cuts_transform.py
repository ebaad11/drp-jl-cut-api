"""
Cuts Transform Module
Logic for applying J-cuts and L-cuts to timeline boundaries.
"""

from typing import Tuple
from cuts_model import Boundary, ClipPair
from resolve_parse import set_clip_property, parse_int_property


def apply_j_cut(boundary: Boundary, offset: int, dry_run: bool = False) -> Tuple[bool, str]:
    """
    Apply a J-cut at a boundary.
    
    J-cut: The audio from the next clip starts earlier (before the video cut).
    
    Modifies:
    - Audio clip (after): Start -= offset, Duration += offset, In -= offset
    
    Args:
        boundary: Boundary where to apply the J-cut
        offset: Number of frames to offset (positive integer)
        dry_run: If True, don't actually modify, just validate
        
    Returns:
        Tuple of (success, message)
    """
    if offset <= 0:
        return False, "Offset must be positive"
    
    audio_clip = boundary.clip_pair_after.audio_clip
    
    # Get current values
    current_start = parse_int_property(audio_clip, "Start")
    current_duration = parse_int_property(audio_clip, "Duration")
    current_in = parse_int_property(audio_clip, "In")
    
    # Calculate new values
    new_start = current_start - offset
    new_duration = current_duration + offset
    new_in = current_in - offset
    
    # Validate
    if new_start < 0:
        return False, f"J-cut would push Start below 0 (new Start={new_start})"
    
    if new_in < 0:
        return False, f"J-cut would push In below 0 (new In={new_in}). Clip may not have enough source media before the cut point."
    
    if current_duration < offset:
        return False, f"Clip too short for offset {offset} (duration={current_duration})"
    
    # Apply changes if not dry run
    if not dry_run:
        set_clip_property(audio_clip, "Start", str(new_start))
        set_clip_property(audio_clip, "Duration", str(new_duration))
        set_clip_property(audio_clip, "In", str(new_in))
    
    clip_name = boundary.clip_pair_after.name
    message = f"J-cut applied to '{clip_name}': Start {current_start}→{new_start}, Duration {current_duration}→{new_duration}, In {current_in}→{new_in}"
    
    return True, message


def apply_l_cut(boundary: Boundary, offset: int, dry_run: bool = False) -> Tuple[bool, str]:
    """
    Apply an L-cut at a boundary.
    
    L-cut: The audio from the current clip continues longer (after the video cut).
    
    Modifies:
    - Audio clip (before): Duration += offset
    
    Args:
        boundary: Boundary where to apply the L-cut
        offset: Number of frames to offset (positive integer)
        dry_run: If True, don't actually modify, just validate
        
    Returns:
        Tuple of (success, message)
    """
    if offset <= 0:
        return False, "Offset must be positive"
    
    audio_clip = boundary.clip_pair_before.audio_clip
    
    # Get current values
    current_duration = parse_int_property(audio_clip, "Duration")
    current_in = parse_int_property(audio_clip, "In")
    
    # Calculate new values
    new_duration = current_duration + offset
    
    # Validate: check if source media has enough frames
    # We need to ensure that In + Duration doesn't exceed source media length
    # However, we don't have source media info in the XML, so we do basic checks
    
    if current_duration < 1:
        return False, f"Clip too short (duration={current_duration})"
    
    # Apply changes if not dry run
    if not dry_run:
        set_clip_property(audio_clip, "Duration", str(new_duration))
    
    clip_name = boundary.clip_pair_before.name
    message = f"L-cut applied to '{clip_name}': Duration {current_duration}→{new_duration}"
    
    return True, message


def validate_j_cut(boundary: Boundary, offset: int) -> Tuple[bool, str]:
    """
    Validate if a J-cut can be applied without actually applying it.
    
    Args:
        boundary: Boundary to check
        offset: Offset in frames
        
    Returns:
        Tuple of (is_valid, message)
    """
    return apply_j_cut(boundary, offset, dry_run=True)


def validate_l_cut(boundary: Boundary, offset: int) -> Tuple[bool, str]:
    """
    Validate if an L-cut can be applied without actually applying it.
    
    Args:
        boundary: Boundary to check
        offset: Offset in frames
        
    Returns:
        Tuple of (is_valid, message)
    """
    return apply_l_cut(boundary, offset, dry_run=True)


def apply_cuts_to_timeline(boundaries: list, offset: int, cut_type: str, dry_run: bool = False) -> dict:
    """
    Apply J-cuts or L-cuts to all boundaries in a timeline.
    
    Args:
        boundaries: List of Boundary objects
        offset: Offset in frames
        cut_type: Either "J" or "L"
        dry_run: If True, validate but don't modify
        
    Returns:
        Dictionary with results: {
            'success_count': int,
            'fail_count': int,
            'messages': list of str,
            'successful_boundaries': list of Boundary
        }
    """
    results = {
        'success_count': 0,
        'fail_count': 0,
        'messages': [],
        'successful_boundaries': []
    }
    
    cut_function = apply_j_cut if cut_type.upper() == 'J' else apply_l_cut
    
    for i, boundary in enumerate(boundaries):
        boundary_num = i + 1
        success, message = cut_function(boundary, offset, dry_run)
        
        if success:
            results['success_count'] += 1
            results['successful_boundaries'].append(boundary)
            results['messages'].append(f"  ✓ Boundary {boundary_num}: {message}")
        else:
            results['fail_count'] += 1
            results['messages'].append(f"  ✗ Boundary {boundary_num}: {message}")
    
    return results


# Module self-test
if __name__ == "__main__":
    import sys
    from pathlib import Path
    from drp_io import unpack_drp, cleanup_temp
    from resolve_parse import find_sequence_files, get_timeline_info, save_timeline_xml
    from cuts_model import find_clip_pairs, find_eligible_boundaries
    
    if len(sys.argv) < 2:
        print("Usage: python cuts_transform.py <path_to_drp_file>")
        print("This will test cut transformation logic (dry-run mode)")
        sys.exit(1)
    
    drp_file = sys.argv[1]
    
    print(f"\n=== Testing Cuts Transform Module ===")
    print(f"Input file: {drp_file}\n")
    
    try:
        # Extract and parse DRP
        print("1. Extracting and parsing DRP...")
        temp_dir = unpack_drp(drp_file)
        seq_files = find_sequence_files(temp_dir)
        
        print(f"   Found {len(seq_files)} timeline(s)")
        
        for seq_file in seq_files:
            print(f"\n   Processing: {Path(seq_file).name}")
            
            # Get timeline info and find boundaries
            info = get_timeline_info(seq_file)
            clip_pairs = find_clip_pairs(info['video_clips'], info['audio_clips'])
            boundaries = find_eligible_boundaries(clip_pairs)
            
            print(f"   - Found {len(boundaries)} eligible boundaries")
            
            if not boundaries:
                print("   - No boundaries to test")
                continue
            
            # Test J-cuts with different offsets (dry-run)
            print("\n2. Testing J-cuts (dry-run):")
            for offset in [4, 8, 12]:
                print(f"\n   Offset: {offset} frames")
                results = apply_cuts_to_timeline(boundaries, offset, "J", dry_run=True)
                for msg in results['messages']:
                    print(f"   {msg}")
                print(f"   Summary: {results['success_count']} successful, {results['fail_count']} failed")
            
            # Test L-cuts with different offsets (dry-run)
            print("\n3. Testing L-cuts (dry-run):")
            for offset in [4, 8, 12]:
                print(f"\n   Offset: {offset} frames")
                results = apply_cuts_to_timeline(boundaries, offset, "L", dry_run=True)
                for msg in results['messages']:
                    print(f"   {msg}")
                print(f"   Summary: {results['success_count']} successful, {results['fail_count']} failed")
            
            # Test actual modification with L-cut (smallest offset)
            print("\n4. Testing actual L-cut modification (offset=4):")
            results = apply_cuts_to_timeline(boundaries, 4, "L", dry_run=False)
            for msg in results['messages']:
                print(f"   {msg}")
            
            if results['success_count'] > 0:
                print("\n5. Saving modified timeline...")
                save_timeline_xml(info['tree'], seq_file)
        
        # Cleanup
        print("\n6. Cleaning up...")
        cleanup_temp(temp_dir)
        
        print("\n=== All tests passed! ===\n")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)




