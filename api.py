"""
FastAPI wrapper for DRP J/L Cut Tool
Provides REST API endpoints for processing DaVinci Resolve project files.
"""

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import tempfile
import zipfile
import os
import shutil
from pathlib import Path
from io import BytesIO
import time
from typing import Optional

# Import your existing modules
from drp_io import unpack_drp, repack_drp, cleanup_temp, get_output_name
from resolve_parse import find_sequence_files, get_timeline_info, save_timeline_xml
from cuts_model import find_clip_pairs, find_eligible_boundaries
from cuts_transform import apply_cuts_to_timeline

# Configuration
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
MAX_EXTRACTED_SIZE = 200 * 1024 * 1024  # 200MB
ALLOWED_EXTENSIONS = ['.drp']
PROCESSING_TIMEOUT = 30  # seconds

# Initialize FastAPI
app = FastAPI(
    title="DRP J/L Cut Tool API",
    description="Apply J-cuts and L-cuts to DaVinci Resolve project files",
    version="1.0.0"
)

# Rate limiting
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS (allow all origins for now - restrict in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change to specific domains in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def validate_file_extension(filename: str) -> bool:
    """Validate file has .drp extension"""
    return any(filename.lower().endswith(ext) for ext in ALLOWED_EXTENSIONS)


def validate_zip_structure(file_content: bytes) -> tuple:
    """
    Validate ZIP structure to prevent security issues.
    Returns (is_valid, error_message)
    """
    try:
        with zipfile.ZipFile(BytesIO(file_content)) as zf:
            # Check for zip bombs (extracted size)
            total_size = sum(info.file_size for info in zf.infolist())
            if total_size > MAX_EXTRACTED_SIZE:
                return False, f"Extracted size ({total_size} bytes) exceeds maximum ({MAX_EXTRACTED_SIZE} bytes)"
            
            # Check for path traversal attacks
            for info in zf.infolist():
                if '..' in info.filename or info.filename.startswith('/'):
                    return False, f"Invalid file path in archive: {info.filename}"
            
            # Check for required DRP structure
            filenames = [info.filename for info in zf.infolist()]
            if 'project.xml' not in filenames:
                return False, "Invalid DRP structure: missing project.xml"
            
            return True, ""
            
    except zipfile.BadZipFile:
        return False, "File is not a valid ZIP archive"
    except Exception as e:
        return False, f"Error validating file: {str(e)}"


@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "name": "DRP J/L Cut Tool API",
        "version": "1.0.0",
        "status": "operational",
        "endpoints": {
            "process": "/api/process",
            "health": "/health",
            "docs": "/docs"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "service": "drp-jl-cut-api"
    }


@app.post("/api/process")
@limiter.limit("5/hour")
async def process_drp(
    request: Request,
    file: UploadFile = File(..., description="DaVinci Resolve project file (.drp)"),
    cut_type: str = Form(..., description="Cut type: 'J' or 'L'"),
    offset: int = Form(..., description="Offset in frames (e.g., 8)")
):
    """
    Process a DaVinci Resolve project file and apply J-cuts or L-cuts.
    
    - **file**: .drp file to process
    - **cut_type**: Either 'J' for J-cuts or 'L' for L-cuts
    - **offset**: Number of frames for the cut offset (typically 4-12)
    
    Returns the processed .drp file ready for download.
    """
    
    temp_input = None
    temp_dir = None
    output_path = None
    
    try:
        # Validate cut type
        cut_type = cut_type.upper()
        if cut_type not in ['J', 'L']:
            raise HTTPException(status_code=400, detail="cut_type must be 'J' or 'L'")
        
        # Validate offset
        if offset <= 0:
            raise HTTPException(status_code=400, detail="offset must be a positive integer")
        if offset > 100:
            raise HTTPException(status_code=400, detail="offset too large (max 100 frames)")
        
        # Validate file extension
        if not validate_file_extension(file.filename):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Only {', '.join(ALLOWED_EXTENSIONS)} files are allowed"
            )
        
        # Read file content
        file_content = await file.read()
        
        # Validate file size
        if len(file_content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File size ({len(file_content)} bytes) exceeds maximum ({MAX_FILE_SIZE} bytes)"
            )
        
        # Validate ZIP structure
        is_valid, error_msg = validate_zip_structure(file_content)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_msg)
        
        # Save to temporary file
        temp_input = tempfile.NamedTemporaryFile(delete=False, suffix='.drp')
        temp_input.write(file_content)
        temp_input.close()
        
        # Process the file
        print(f"Processing {file.filename} with {cut_type}-cuts, offset={offset}")
        
        # Extract DRP
        temp_dir = unpack_drp(temp_input.name)
        
        # Find and process timelines
        seq_files = find_sequence_files(temp_dir)
        if not seq_files:
            raise HTTPException(
                status_code=400,
                detail="No timelines found in project file"
            )
        
        total_boundaries = 0
        total_applied = 0
        
        for seq_file in seq_files:
            info = get_timeline_info(seq_file)
            clip_pairs = find_clip_pairs(info['video_clips'], info['audio_clips'])
            boundaries = find_eligible_boundaries(clip_pairs)
            
            total_boundaries += len(boundaries)
            
            if boundaries:
                results = apply_cuts_to_timeline(boundaries, offset, cut_type, dry_run=False)
                total_applied += results['success_count']
                
                if results['success_count'] > 0:
                    save_timeline_xml(info['tree'], seq_file)
        
        # Check if any cuts were applied
        if total_boundaries == 0:
            raise HTTPException(
                status_code=400,
                detail="No eligible boundaries found in project. Clips must have aligned audio/video."
            )
        
        if total_applied == 0:
            raise HTTPException(
                status_code=400,
                detail=f"Could not apply {cut_type}-cuts. Try a smaller offset or different cut type."
            )
        
        # Repack to new DRP
        output_name = get_output_name(file.filename, cut_type)
        output_path = repack_drp(temp_dir, output_name)
        
        print(f"Successfully applied {total_applied} {cut_type}-cuts to {file.filename}")
        
        # Return the processed file
        return FileResponse(
            path=output_path,
            media_type='application/zip',
            filename=output_name,
            headers={
                "X-Cuts-Applied": str(total_applied),
                "X-Total-Boundaries": str(total_boundaries),
                "X-Cut-Type": cut_type,
                "X-Offset": str(offset)
            }
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
        
    except Exception as e:
        # Log the error and return 500
        print(f"Error processing file: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Error processing file: {str(e)}"
        )
        
    finally:
        # Cleanup temporary files
        try:
            if temp_input and os.path.exists(temp_input.name):
                os.unlink(temp_input.name)
            if temp_dir and os.path.exists(temp_dir):
                cleanup_temp(temp_dir)
            # Note: output_path cleanup is handled by FastAPI after sending response
        except Exception as e:
            print(f"Error cleaning up: {str(e)}")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors"""
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {str(exc)}"}
    )


if __name__ == "__main__":
    import uvicorn
    import os
    
    # Get port from environment (Railway provides this)
    port = int(os.getenv("PORT", 8000))
    
    print("Starting DRP J/L Cut Tool API...")
    print(f"Port: {port}")
    print("Visit /docs for interactive API documentation")
    
    uvicorn.run(app, host="0.0.0.0", port=port)

