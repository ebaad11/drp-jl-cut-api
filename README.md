# DRP J/L Cut Tool

A command-line tool to apply J-cuts and L-cuts to DaVinci Resolve project files (.drp).

## What are J-cuts and L-cuts?

- **J-cut**: The audio from the next clip starts before the video cut (audio leads)
- **L-cut**: The audio from the current clip continues after the video cut (audio trails)

## Requirements

- Python 3.8 or higher
- No external dependencies (uses Python standard library)

## Installation

No installation required. Just clone or download the project.

## Usage

Basic usage:
```bash
python main.py path/to/your_project.drp
```

The tool will:
1. Extract the .drp file
2. Present a menu to choose J-cut or L-cut mode
3. Ask for the offset in frames (e.g., 8-12 frames typical)
4. Apply the cuts to all eligible boundaries
5. Create a new .drp file: `your_project (J cuts added).drp`

### Example

```bash
python main.py J_cut_test.drp
```

Output: `J_cut_test (J cuts added).drp`

## Testing Individual Modules

Run the test suite:
```bash
python test_modules.py
```

This will test each module independently:
- DRP I/O (extract/repack)
- XML parsing
- Cut detection
- Cut transformation

## Project Structure

```
.
├── main.py              # CLI interface
├── drp_io.py           # DRP file extraction/repacking
├── resolve_parse.py    # XML parsing utilities
├── cuts_model.py       # Cut detection logic
├── cuts_transform.py   # J/L cut transformation
├── test_modules.py     # Independent module tests
├── requirements.txt    # Dependencies
└── README.md          # This file
```

## How it Works

1. **Extract**: The .drp file (a ZIP archive) is extracted to a temporary directory
2. **Parse**: Timeline XML files are parsed to find video and audio clips
3. **Detect**: Eligible cut boundaries are identified (where A/V are aligned)
4. **Transform**: J-cut or L-cut logic is applied by modifying audio clip timing
5. **Repack**: Modified files are zipped back into a new .drp file

## Limitations

- V1 applies the same offset to all eligible cuts (batch processing)
- Only processes simple aligned A/V cuts
- Requires manual verification in DaVinci Resolve after processing

## Safety

- Original .drp file is never modified
- All changes are written to a new file with "(J cuts added)" or "(L cuts added)" suffix
- Dry-run mode available to preview changes before applying




