import argparse
import importlib
import sys
import time
import select
import os
import platform
from pynvml import *
import psutil
import datetime
from . import utils

is_windows = platform.system() == 'Windows'

if is_windows:
    import colorama
    colorama.init()
    import ctypes
    from ctypes import wintypes
    
    # Enable Windows VT processing
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    STD_OUTPUT_HANDLE = -11
    ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
    
    hOut = kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
    mode = wintypes.DWORD()
    kernel32.GetConsoleMode(hOut, ctypes.byref(mode))
    kernel32.SetConsoleMode(hOut, mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING)
else:
    import termios
    import tty

def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--interval", help="Seconds between updates", type=int, default=1)
    args=parser.parse_args()

    try:
        nvmlInit()
    except:
        print("Could not initialize NVML. Sorry 🥺...")
        exit(1)

    GEM = os.getenv("GEM", "emerald")
    THEME = importlib.import_module("gvtop.themes."+GEM).THEME

    fd = sys.stdin.fileno()

    if is_windows:
        old_settings = None
        # Windows Terminal already supports alternate buffer
        print("\x1b[?1049h\x1b[?25l", end="", flush=True)
    else:
        old_settings = termios.tcgetattr(fd)
        print("\x1b[?1049h\x1b[?25l", end="", flush=True)
        tty.setraw(fd)

    cuda = str(nvmlSystemGetCudaDriverVersion_v2())
    major = int(cuda[:2])
    minor = int(cuda[2:4])
    patch = int(cuda[4])

    count = nvmlDeviceGetCount()
    handles = []
    for index in range(count):
        handles.append( nvmlDeviceGetHandleByIndex(index) )
    device_name = nvmlDeviceGetName(handles[0])
    cuda_cores = nvmlDeviceGetNumGpuCores(handles[0])
    # .total, .free, .used
    total_mem = round(nvmlDeviceGetMemoryInfo(handles[0]).total/2**30)
    max_power = round(nvmlDeviceGetEnforcedPowerLimit(handles[0])/1000)

    while True:
        # Dark mode ANSI DSR (https://contour-terminal.org/vt-extensions/color-palette-update-notifications/)
        print("\x1b[?996n",end="",flush=True)
        response = os.read(fd, 9)
        if response==b"\x1b[?997;1n":
            mode="dark"
        elif response==b"\x1b[?997;2n":
            mode="light"

        SCHEME = THEME[mode]
        
        icon = lambda x: "\x1b[38;2;%sm%s\x1b[39m" % (SCHEME["primary"], x)
        key = lambda x: "\x1b[38;2;%s;49m▐\x1b[38;2;%s;48;2;%sm%s\x1b[38;2;%s;49m▌\x1b[39;49m" % (SCHEME["error"],SCHEME["onError"],SCHEME["error"],x,SCHEME["error"])
        first_line = '\x1b[38;2;%s;1m%s\x1b[39;22m' % (SCHEME["secondary"],device_name)
        tip = "Close with%s/%s/%s+%s" % (key("ESC"),key("q"),key("CTRL"),key("c"))
        extra_spaces = os.get_terminal_size().columns - utils.ansi_len(first_line) - utils.ansi_len(tip)
        first_line = first_line + " "*extra_spaces + tip + "\n"
        header = (first_line +
                  '%s Cores: %8.8s\n' % (icon(" "),cuda_cores)+
                  '%s  Mem.: %8.8s\n' % (icon(" "),"%d GiB" % total_mem) +
                  '%s  Pow.: %8.8s\n' % (icon(" "),"%d W" % max_power) +
                  '%s  CUDA: %8.8s' % (icon(" "),"≤ %d.%d" % (major,minor)))
        
        containers = []
        global_processes = []
        for index in range(count):
            used_mem = round(nvmlDeviceGetMemoryInfo(handles[index]).used/2**30)
            power = round(nvmlDeviceGetPowerUsage(handles[index])/1000)
            # .gpu, .memory
            util = nvmlDeviceGetUtilizationRates(handles[index]).gpu/100
            # .pid, .usedGpuMemory, .gpuInstanceId, .computeInstanceId
            local_processes = nvmlDeviceGetComputeRunningProcesses_v3(handles[index])
            global_processes.append(local_processes)
            
            container = utils.GPUContainer(SCHEME, index, used_mem, total_mem, power, max_power, util, len(local_processes))
            containers.append(str(container))
        body = utils.to_grid(containers,4)

        footer = "\x1b[1m%4.4s %8.8s %8.8s %12.12s %8.8s %s\x1b[22m\n" % ("GPU", "Mem.", "PID", "Start", "Elapsed", "CMD")
        for index in range(count):
            local_processes = global_processes[index]
            for process in local_processes:
                proc = psutil.Process(process.pid)
                start = datetime.datetime.fromtimestamp(proc.create_time()).strftime("%a/%H:%M:%S")
                elapsed = round(time.time() - proc.create_time())
                hours = elapsed//3600
                mins = (elapsed%3600)//60
                secs = elapsed%60
                elapsed = "%02d:%02d:%02d" % (hours, mins, secs)
                cmd = " ".join(proc.cmdline())
                footer += "%4.4s %8.8s %8.8s %12.12s %8.8s %s\n" % (index, "%d GiB" % round(process.usedGpuMemory/2**30), process.pid, start, elapsed, cmd)
        # Delete final new line
        footer = footer[:-1]
        
        # Begin Synchronized Update, clear screen, cursor home, End Synchronized Update
        string = "\x1b[?2026h\x1b[2J\x1b[H%s\n%s\n%s\x1b[?2026l" % (header,body,footer)
        # string contains \n, which in raw mode are not converted to \r\n
        print(string.replace("\n","\r\n"),end="",flush=True)

        start = time.time()
        while time.time()-start < args.interval:
            # rlist, wlist, xlist=select.select(rlist, wlist, xlist, timeout=None/blocking)
            if is_windows:
                if msvcrt.kbhit():
                    byte = msvcrt.getch()
                    if byte in [b"\x1b", b"q", b"\x03"]:
                        utils.cleanup(fd, old_settings)
            else:
                if select.select([sys.stdin], [], [], 0)[0]:
                    byte = os.read(fd, 1)
                    # CTRL+c=3/ETX
                    if byte in [b"\x1b", b"q", b"\x03"]:
                        utils.cleanup(fd, old_settings)

if __name__ == "__main__":
    main()
