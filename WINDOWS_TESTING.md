# Windows Terminal Testing Guide

## Prerequisites
1. Windows 10 (version 1903+) or Windows 11
2. Windows Terminal installed (recommended)
3. Python 3.7+

## Installation
```bash
pip install gvtop
```

## Running the Application
```bash
gvtop
```

## Verification Checklist
1. **Display Output**:
   - Verify no flickering during updates
   - Check all colors display correctly
   - Confirm Unicode characters (bars, icons) render properly

2. **Input Handling**:
   - Test exit with ESC key
   - Test exit with 'q' key
   - Test exit with CTRL+C

3. **Cleanup**:
   - Verify terminal returns to normal state after exit
   - Check no residual ANSI codes remain
   - Confirm "Bye sexy 😘!" message appears

## Troubleshooting
- If colors don't display:
  ```bash
  pip install --upgrade colorama
  ```
- If Unicode characters don't render:
  - Use Windows Terminal instead of cmd.exe
  - Set terminal font to "Consolas" or "Cascadia Code"