import argparse
import importlib
import time
import os
import platform
from pynvml import *
import psutil
import datetime
from . import utils
from .windows_terminal import get_terminal, WindowsGpuMonitor

class GVTopUI:
    def __init__(self):
        self.palette = [
            ('header', 'black', 'light gray'),
            ('body', 'light gray', 'black'),
            ('footer', 'dark red', 'black')
        ]
        self.header_text = urwid.Text("")
        self.body_text = urwid.Text("")
        self.footer_text = urwid.Text("")
        self.layout = urwid.Frame(
            header=urwid.AttrMap(self.header_text, 'header'),
            body=urwid.AttrMap(self.body_text, 'body'),
            footer=urwid.AttrMap(self.footer_text, 'footer')
        )
        self.loop = None

    def update_screen(self, header, body, footer):
        """Update screen using platform-appropriate method"""
        if platform.system() == 'Windows':
            term = get_terminal()
            with term.fullscreen(), term.hidden_cursor():
                print(term.clear(), end='')
                print(header + body + footer, end='', flush=True)
        else:
            self.header_text.set_text(header)
            self.body_text.set_text(body)
            self.footer_text.set_text(footer)
            if self.loop:
                self.loop.draw_screen()

    def run(self, interval, update_callback):
        def input_handler(key):
            if key in ('esc', 'q', 'ctrl c'):
                raise urwid.ExitMainLoop()

        self.loop = urwid.MainLoop(
            self.layout,
            self.palette,
            unhandled_input=input_handler,
            handle_mouse=False
        )
        
        def refresh(loop, data):
            update_callback()
            loop.set_alarm_in(interval, refresh)

        self.loop.set_alarm_in(interval, refresh)
        self.loop.run()
from pynvml import *
import psutil
import datetime
from . import utils

def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--interval", help="Seconds between updates", type=int, default=1)
    args=parser.parse_args()

    gpu_monitor = None
    nvml_initialized = False
    
    if platform.system() == 'Windows':
        try:
            gpu_monitor = WindowsGpuMonitor()
        except Exception as e:
            print(f"Warning: Could not initialize WMI GPU monitoring: {str(e)}")
    
    # Try NVML initialization for all platforms
    try:
        nvmlInit()
        nvml_initialized = True
    except pynvml.NVMLError_Unitialized:
        print("Warning: NVML not initialized - GPU monitoring limited")
    except Exception as e:
        print(f"Warning: NVML initialization failed: {str(e)}")
    
    if platform.system() != 'Windows' and not nvml_initialized and not gpu_monitor:
        print("Error: No GPU monitoring available")
        exit(1)

    GEM = os.getenv("GEM", "emerald")
    THEME = importlib.import_module("gvtop.themes."+GEM).THEME

    # Enter alternate buffer and hide cursor handled by blessed

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
        # Default to dark mode
        mode = "dark"
        SCHEME = THEME[mode]
        
        # Get GPU info from appropriate source
        if platform.system() == 'Windows' and gpu_monitor:
            try:
                gpu_name = gpu_monitor.gpu_info['name']
                gpu_mem = gpu_monitor.gpu_info['memory']
            except:
                gpu_name = "Unknown GPU"
                gpu_mem = 0
        elif nvml_initialized:
            gpu_name = device_name
            gpu_mem = total_mem
        else:
            gpu_name = "GPU Monitoring Unavailable"
            gpu_mem = 0
            
        icon = lambda x: "\x1b[38;2;%sm%s\x1b[39m" % (SCHEME["primary"], x)
        key = lambda x: "\x1b[38;2;%s;49m▐\x1b[38;2;%s;48;2;%sm%s\x1b[38;2;%s;49m▌\x1b[39;49m" % (SCHEME["error"],SCHEME["onError"],SCHEME["error"],x,SCHEME["error"])
        first_line = '\x1b[38;2;%s;1m%s\x1b[39;22m' % (SCHEME["secondary"],gpu_name)
        tip = "Close with%s/%s/%s+%s" % (key("ESC"),key("q"),key("CTRL"),key("c"))
        extra_spaces = os.get_terminal_size().columns - utils.ansi_len(first_line) - utils.ansi_len(tip)
        first_line = first_line + " "*extra_spaces + tip + "\n"
        header = (first_line +
                  '%s Cores: %8.8s\n' % (icon(" "),cuda_cores)+
                  '%s  Mem.: %8.8s\n' % (icon(" "),"%d GiB" % gpu_mem) +
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
                mem_usage = round(process.usedGpuMemory/2**30) if process.usedGpuMemory else 0
                footer += "%4.4s %8.8s %8.8s %12.12s %8.8s %s\n" % (index, "%d GiB" % mem_usage, process.pid, start, elapsed, cmd)
        # Delete final new line
        footer = footer[:-1]
        
        # Smart display update
        screen_lines = [header, body, footer]
        update_screen(screen_lines)

        start = time.time()
        while time.time()-start < args.interval:
            if get_input(args.interval - (time.time()-start)):
                utils.cleanup()
                break

if __name__ == "__main__":
    main()
