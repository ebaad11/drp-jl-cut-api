"""
DRP I/O Module
Handles extraction and repacking of DaVinci Resolve Project (.drp) files.
A .drp file is a ZIP archive containing XML files describing the project.
"""

import zipfile
import tempfile
import shutil
import os
from pathlib import Path
from typing import Optional


def unpack_drp(drp_path: str) -> str:
    """
    Unpack a .drp file to a temporary directory.
    
    Args:
        drp_path: Path to the .drp file
        
    Returns:
        Path to the temporary directory containing extracted files
        
    Raises:
        FileNotFoundError: If the .drp file doesn't exist
        zipfile.BadZipFile: If the file is not a valid ZIP archive
    """
    drp_path = Path(drp_path)
    
    if not drp_path.exists():
        raise FileNotFoundError(f"DRP file not found: {drp_path}")
    
    # Create a temporary directory
    temp_dir = tempfile.mkdtemp(prefix="drp_extract_")
    
    try:
        # Extract the .drp (which is a ZIP file)
        with zipfile.ZipFile(drp_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        print(f"✓ Extracted {drp_path.name} to temporary directory")
        
        # Verify the structure
        if not verify_drp_structure(temp_dir):
            raise ValueError("Invalid DRP structure: missing required files")
        
        return temp_dir
        
    except Exception as e:
        # Clean up on error
        cleanup_temp(temp_dir)
        raise e


def repack_drp(temp_dir: str, output_name: str, output_dir: Optional[str] = None) -> str:
    """
    Repack a temporary directory back into a .drp file.
    
    Args:
        temp_dir: Path to the temporary directory with modified files
        output_name: Name for the output .drp file (without extension)
        output_dir: Optional directory for output file (defaults to current working directory)
        
    Returns:
        Path to the created .drp file
        
    Raises:
        FileNotFoundError: If temp_dir doesn't exist
    """
    temp_dir = Path(temp_dir)
    
    if not temp_dir.exists():
        raise FileNotFoundError(f"Temporary directory not found: {temp_dir}")
    
    # Ensure output name has .drp extension
    if not output_name.endswith('.drp'):
        output_name += '.drp'
    
    # Determine output directory
    if output_dir is None:
        output_dir = Path.cwd()
    else:
        output_dir = Path(output_dir)
    
    # Create output path
    output_path = output_dir / output_name
    
    # Create a temporary ZIP file first
    temp_zip = temp_dir.parent / f"{output_name}.tmp"
    
    try:
        # Create ZIP file with all contents
        with zipfile.ZipFile(temp_zip, 'w', zipfile.ZIP_DEFLATED) as zip_ref:
            # Walk through all files in temp_dir
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    file_path = Path(root) / file
                    # Calculate the archive name (relative path from temp_dir)
                    arcname = file_path.relative_to(temp_dir)
                    zip_ref.write(file_path, arcname)
        
        # Rename to .drp
        shutil.move(str(temp_zip), str(output_path))
        
        print(f"✓ Created {output_path.name}")
        return str(output_path)
        
    except Exception as e:
        # Clean up temporary zip on error
        if temp_zip.exists():
            temp_zip.unlink()
        raise e


def verify_drp_structure(temp_dir: str) -> bool:
    """
    Verify that the extracted directory has the required DRP structure.
    
    Args:
        temp_dir: Path to the extracted directory
        
    Returns:
        True if structure is valid, False otherwise
    """
    temp_dir = Path(temp_dir)
    
    # Required files/directories
    required_files = ['project.xml']
    required_dirs = ['SeqContainer']
    
    # Check for required files
    for file in required_files:
        if not (temp_dir / file).exists():
            print(f"✗ Missing required file: {file}")
            return False
    
    # Check for required directories
    for dir_name in required_dirs:
        if not (temp_dir / dir_name).is_dir():
            print(f"✗ Missing required directory: {dir_name}")
            return False
    
    return True


def cleanup_temp(temp_dir: str) -> None:
    """
    Remove a temporary directory and all its contents.
    
    Args:
        temp_dir: Path to the temporary directory to remove
    """
    temp_dir = Path(temp_dir)
    
    if temp_dir.exists() and temp_dir.is_dir():
        shutil.rmtree(temp_dir)
        print(f"✓ Cleaned up temporary directory")


def get_output_name(original_path: str, cut_type: str) -> str:
    """
    Generate output filename based on original name and cut type.
    
    Args:
        original_path: Path to original .drp file
        cut_type: Either "J" or "L"
        
    Returns:
        New filename with suffix
    """
    original_path = Path(original_path)
    base_name = original_path.stem  # filename without extension
    
    if cut_type.upper() == 'J':
        suffix = " (J cuts added)"
    elif cut_type.upper() == 'L':
        suffix = " (L cuts added)"
    else:
        suffix = " (modified)"
    
    return f"{base_name}{suffix}.drp"


# Module self-test
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python drp_io.py <path_to_drp_file>")
        print("This will test extraction and repacking of a .drp file")
        sys.exit(1)
    
    drp_file = sys.argv[1]
    
    print(f"\n=== Testing DRP I/O Module ===")
    print(f"Input file: {drp_file}\n")
    
    try:
        # Test unpacking
        print("1. Testing unpack_drp()...")
        temp_dir = unpack_drp(drp_file)
        print(f"   Extracted to: {temp_dir}")
        
        # List contents
        print("\n2. Contents:")
        for root, dirs, files in os.walk(temp_dir):
            level = root.replace(temp_dir, '').count(os.sep)
            indent = ' ' * 2 * level
            print(f"{indent}{os.path.basename(root)}/")
            subindent = ' ' * 2 * (level + 1)
            for file in files:
                print(f"{subindent}{file}")
        
        # Test repacking
        print("\n3. Testing repack_drp()...")
        output_name = get_output_name(drp_file, "TEST")
        output_path = repack_drp(temp_dir, output_name)
        print(f"   Created: {output_path}")
        
        # Verify the output file
        print("\n4. Verifying output file...")
        if Path(output_path).exists():
            file_size = Path(output_path).stat().st_size
            print(f"   ✓ Output file exists ({file_size} bytes)")
            
            # Try to open it as a zip
            with zipfile.ZipFile(output_path, 'r') as zf:
                file_count = len(zf.namelist())
                print(f"   ✓ Valid ZIP archive ({file_count} files)")
        
        # Cleanup
        print("\n5. Testing cleanup_temp()...")
        cleanup_temp(temp_dir)
        
        print("\n=== All tests passed! ===\n")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

