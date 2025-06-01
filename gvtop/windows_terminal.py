import ctypes
from ctypes import wintypes
import sys
import platform
from typing import List

class WindowsConsole:
    """Native Windows console implementation with double buffering"""
    
    def __init__(self):
        self.kernel32 = ctypes.windll.kernel32
        self.handle = self.kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        self.prev_buffer = []
        self._setup_console()
        
    def _setup_console(self):
        """Enable virtual terminal processing and other console features"""
        ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
        ENABLE_PROCESSED_OUTPUT = 0x0001
        mode = wintypes.DWORD()
        self.kernel32.GetConsoleMode(self.handle, ctypes.byref(mode))
        mode.value |= ENABLE_VIRTUAL_TERMINAL_PROCESSING | ENABLE_PROCESSED_OUTPUT
        self.kernel32.SetConsoleMode(self.handle, mode)
        
    def write(self, lines: List[str]):
        """Write lines to console with minimal updates"""
        COORD = wintypes._COORD
        SMALL_RECT = wintypes.SMALL_RECT
        
        # Calculate minimal update regions
        diff_lines = self._calculate_diffs(lines)
        if not diff_lines:
            return
            
        # Prepare console buffer
        buffer_size = COORD(len(lines[0]), len(lines))
        buffer_coord = COORD(0, 0)
        write_region = SMALL_RECT(0, 0, len(lines[0])-1, len(lines)-1)
        
        # Create CHAR_INFO buffer
        CHAR_INFO = wintypes.CHAR * (len(lines[0]) * len(lines))
        char_buffer = CHAR_INFO()
        
        # Fill buffer with content
        for y, line in enumerate(lines):
            for x, char in enumerate(line):
                char_buffer[y * len(lines[0]) + x] = ord(char)
                
        # Write to console
        self.kernel32.WriteConsoleOutputW(
            self.handle,
            ctypes.cast(char_buffer, wintypes.PCHAR_INFO),
            buffer_size,
            buffer_coord,
            ctypes.byref(write_region)
        )
        
        self.prev_buffer = lines.copy()
        
    def _calculate_diffs(self, new_lines: List[str]) -> List[int]:
        """Calculate which lines need updating"""
        if not self.prev_buffer:
            return list(range(len(new_lines)))
            
        diffs = []
        for i, (old_line, new_line) in enumerate(zip(self.prev_buffer, new_lines)):
            if old_line != new_line:
                diffs.append(i)
        return diffs

class WindowsGpuMonitor:
    """Windows GPU monitoring using WMI"""
    
    def __init__(self):
        import wmi
        self.wmi = wmi.WMI()
        self.gpu_info = None
        self._init_gpu_info()
        
    def _init_gpu_info(self):
        """Initialize GPU information"""
        adapters = self.wmi.Win32_VideoController()
        if adapters:
            self.gpu_info = {
                'name': adapters[0].Name,
                'memory': int(adapters[0].AdapterRAM) // (1024**2),
                'driver_version': adapters[0].DriverVersion
            }
            
    def get_utilization(self):
        """Get current GPU utilization"""
        # Windows doesn't provide direct utilization via WMI
        # Would need DirectX/DXGI or NVML for this
        return 0
        
    def get_memory_usage(self):
        """Get current GPU memory usage"""
        # Windows doesn't provide this via WMI
        return 0

def get_terminal():
    """Get appropriate terminal implementation for platform"""
    if platform.system() == 'Windows':
        return WindowsConsole()
    else:
        from blessed import Terminal
        return Terminal()