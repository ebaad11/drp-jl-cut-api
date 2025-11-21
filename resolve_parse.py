"""
Resolve Parse Module
Utilities for locating and parsing DaVinci Resolve XML files.
"""

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Optional


def find_sequence_files(temp_dir: str) -> List[str]:
    """
    Find all Sm2SequenceContainer XML files in the extracted DRP directory.
    
    Args:
        temp_dir: Path to the extracted DRP directory
        
    Returns:
        List of paths to sequence container XML files
    """
    temp_dir = Path(temp_dir)
    seq_dir = temp_dir / "SeqContainer"
    
    if not seq_dir.exists():
        return []
    
    # Find all XML files in SeqContainer directory
    xml_files = list(seq_dir.glob("*.xml"))
    
    # Filter for files that contain Sm2SequenceContainer root element
    sequence_files = []
    for xml_file in xml_files:
        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()
            if root.tag == "Sm2SequenceContainer":
                sequence_files.append(str(xml_file))
        except ET.ParseError:
            continue
    
    return sequence_files


def load_timeline_xml(xml_path: str) -> ET.ElementTree:
    """
    Load and parse a timeline XML file.
    
    Args:
        xml_path: Path to the XML file
        
    Returns:
        ElementTree object
        
    Raises:
        FileNotFoundError: If file doesn't exist
        ET.ParseError: If XML is malformed
    """
    xml_path = Path(xml_path)
    
    if not xml_path.exists():
        raise FileNotFoundError(f"XML file not found: {xml_path}")
    
    tree = ET.parse(xml_path)
    return tree


def save_timeline_xml(tree: ET.ElementTree, xml_path: str) -> None:
    """
    Save a modified timeline XML file.
    Attempts to preserve formatting as much as possible.
    
    Args:
        tree: ElementTree object to save
        xml_path: Path where to save the file
    """
    xml_path = Path(xml_path)
    
    # Write with XML declaration and UTF-8 encoding
    tree.write(
        xml_path,
        encoding='UTF-8',
        xml_declaration=True
    )
    
    print(f"✓ Saved {xml_path.name}")


def get_video_track(root: ET.Element) -> Optional[ET.Element]:
    """
    Get the first video track from a sequence container.
    
    Args:
        root: Root element of Sm2SequenceContainer
        
    Returns:
        First Sm2TiTrack element from VideoTrackVec, or None
    """
    video_track_vec = root.find("VideoTrackVec")
    if video_track_vec is None:
        return None
    
    # Get first Element
    element = video_track_vec.find("Element")
    if element is None:
        return None
    
    # Get the Sm2TiTrack
    track = element.find("Sm2TiTrack")
    return track


def get_audio_track(root: ET.Element) -> Optional[ET.Element]:
    """
    Get the first audio track from a sequence container.
    
    Args:
        root: Root element of Sm2SequenceContainer
        
    Returns:
        First Sm2TiTrack element from AudioTrackVec, or None
    """
    audio_track_vec = root.find("AudioTrackVec")
    if audio_track_vec is None:
        return None
    
    # Get first Element
    element = audio_track_vec.find("Element")
    if element is None:
        return None
    
    # Get the Sm2TiTrack
    track = element.find("Sm2TiTrack")
    return track


def get_track_items(track: ET.Element) -> List[ET.Element]:
    """
    Get all clip items from a track.
    
    Args:
        track: Sm2TiTrack element
        
    Returns:
        List of clip elements (Sm2TiVideoClip or Sm2TiAudioClip)
    """
    items_element = track.find("Items")
    if items_element is None:
        return []
    
    clips = []
    for element in items_element.findall("Element"):
        # Find either video or audio clip
        clip = element.find("Sm2TiVideoClip")
        if clip is None:
            clip = element.find("Sm2TiAudioClip")
        
        if clip is not None:
            clips.append(clip)
    
    return clips


def get_clip_property(clip: ET.Element, property_name: str) -> Optional[str]:
    """
    Get a property value from a clip element.
    
    Args:
        clip: Clip element (Sm2TiVideoClip or Sm2TiAudioClip)
        property_name: Name of the property (e.g., "Start", "Duration", "Name")
        
    Returns:
        Property value as string, or None if not found
    """
    element = clip.find(property_name)
    if element is None:
        return None
    
    # Return text, or empty string if element is self-closing
    return element.text if element.text is not None else ""


def set_clip_property(clip: ET.Element, property_name: str, value: str) -> None:
    """
    Set a property value on a clip element.
    
    Args:
        clip: Clip element (Sm2TiVideoClip or Sm2TiAudioClip)
        property_name: Name of the property (e.g., "Start", "Duration", "In")
        value: New value as string
    """
    element = clip.find(property_name)
    if element is not None:
        element.text = value


def parse_int_property(clip: ET.Element, property_name: str, default: int = 0) -> int:
    """
    Parse an integer property from a clip, with default for empty/missing values.
    
    Args:
        clip: Clip element
        property_name: Name of the property
        default: Default value if property is missing or empty
        
    Returns:
        Integer value
    """
    value = get_clip_property(clip, property_name)
    if value is None or value == "":
        return default
    
    try:
        return int(value)
    except ValueError:
        return default


def get_timeline_info(xml_path: str) -> dict:
    """
    Extract basic information about a timeline.
    
    Args:
        xml_path: Path to the sequence XML file
        
    Returns:
        Dictionary with timeline information
    """
    tree = load_timeline_xml(xml_path)
    root = tree.getroot()
    
    video_track = get_video_track(root)
    audio_track = get_audio_track(root)
    
    video_clips = get_track_items(video_track) if video_track is not None else []
    audio_clips = get_track_items(audio_track) if audio_track is not None else []
    
    return {
        'xml_path': xml_path,
        'video_clip_count': len(video_clips),
        'audio_clip_count': len(audio_clips),
        'video_clips': video_clips,
        'audio_clips': audio_clips,
        'video_track': video_track,
        'audio_track': audio_track,
        'root': root,
        'tree': tree
    }


# Module self-test
if __name__ == "__main__":
    import sys
    from drp_io import unpack_drp, cleanup_temp
    
    if len(sys.argv) < 2:
        print("Usage: python resolve_parse.py <path_to_drp_file>")
        print("This will test XML parsing of timeline files")
        sys.exit(1)
    
    drp_file = sys.argv[1]
    
    print(f"\n=== Testing Resolve Parse Module ===")
    print(f"Input file: {drp_file}\n")
    
    try:
        # Extract DRP
        print("1. Extracting DRP...")
        temp_dir = unpack_drp(drp_file)
        
        # Find sequence files
        print("\n2. Finding sequence files...")
        seq_files = find_sequence_files(temp_dir)
        print(f"   Found {len(seq_files)} sequence file(s):")
        for seq_file in seq_files:
            print(f"   - {Path(seq_file).name}")
        
        # Parse each sequence
        print("\n3. Parsing timeline information...")
        for seq_file in seq_files:
            print(f"\n   Timeline: {Path(seq_file).name}")
            info = get_timeline_info(seq_file)
            
            print(f"   - Video clips: {info['video_clip_count']}")
            print(f"   - Audio clips: {info['audio_clip_count']}")
            
            # Show first video clip details
            if info['video_clips']:
                clip = info['video_clips'][0]
                name = get_clip_property(clip, "Name")
                start = parse_int_property(clip, "Start")
                duration = parse_int_property(clip, "Duration")
                in_point = parse_int_property(clip, "In")
                
                print(f"   - First video clip: {name}")
                print(f"     Start={start}, Duration={duration}, In={in_point}")
            
            # Show first audio clip details
            if info['audio_clips']:
                clip = info['audio_clips'][0]
                name = get_clip_property(clip, "Name")
                start = parse_int_property(clip, "Start")
                duration = parse_int_property(clip, "Duration")
                in_point = parse_int_property(clip, "In")
                
                print(f"   - First audio clip: {name}")
                print(f"     Start={start}, Duration={duration}, In={in_point}")
        
        # Test save functionality (no modifications)
        print("\n4. Testing save functionality...")
        for seq_file in seq_files:
            tree = load_timeline_xml(seq_file)
            save_timeline_xml(tree, seq_file)
        
        # Cleanup
        print("\n5. Cleaning up...")
        cleanup_temp(temp_dir)
        
        print("\n=== All tests passed! ===\n")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)




