import re
import sys
import termios
import tty
import math
from pynvml import *

pattern = re.compile(r"\x1b\[[0-9;]*m")

def remove_ansi(string):
    return pattern.sub("", string)

def ansi_len(string):
    return len(remove_ansi(string))

def ansi_cols(lines):
    cols = 0

    for line in lines:
        cols = max(cols, ansi_len(line))

    return cols

def get_bar(ratio, on="255;255;255", off="128;128;128"):

    on_bars = round(ratio*10)
    off_bars = 10 - on_bars
    bar = "\x1b[38;2;%sm%s\x1b[38;2;%sm%s\x1b[39m" % (on, "❚"*on_bars, off, "❚"*off_bars)

    return bar

def get_traffic(is_on, on="0;255;0", off="255;0;0"):
    if is_on:
        traffic = "\x1b[38;2;%sm●\x1b[39m" % on
    else:
        traffic = "\x1b[38;2;%sm●\x1b[39m" % off

    return traffic

def to_columns(strings):
    lists = [string.splitlines() for string in strings]
    
    # line=(c1,c2,...)
    cols = ""
    for line in zip(*lists):
        cols += "".join(line) + "\n"
    # Delete final new line
    cols = cols[:-1]

    return cols

def to_grid(strings, cols=2):
    grid = ""

    rows = math.ceil(len(strings)/cols)
    for row in range(0, rows):
        grid += to_columns(strings[cols*row:cols*row+cols]) + "\n"
    # Delete final new line
    grid = grid[:-1]

    return grid

class Container():
    def __init__(self, foreground="255;255;255", background="128;128;128", header="None", content=[]):
        super().__init__()
    
        self.foreground = foreground
        self.background = background
        self.header = header
        self.content = content
        
        # header+content
        self.lines = 1 + len(content)
        self.cols = ansi_cols([header]+content)

        self.left_padding = "\x1b[38;2;%s;49m▐\x1b[38;2;%s;48;2;%sm" % (background, foreground, background)
        self.right_padding = "\x1b[38;2;%s;49m▌\x1b[38;2;%s;48;2;%sm" % (background, foreground, background)
        self.top_padding = "\x1b[38;2;%s;49m▄\x1b[38;2;%s;48;2;%sm" % (background, foreground, background)
        self.bot_padding = "\x1b[38;2;%s;49m▀\x1b[38;2;%s;48;2;%sm" % (background, foreground, background)
        self.top_left_padding = "\x1b[38;2;%s;49m▗\x1b[38;2;%s;48;2;%sm" % (background, foreground, background)
        self.top_right_padding = "\x1b[38;2;%s;49m▖\x1b[38;2;%s;48;2;%sm" % (background, foreground, background)
        self.bot_left_padding = "\x1b[38;2;%s;49m▝\x1b[38;2;%s;48;2;%sm" % (background, foreground, background)
        self.bot_right_padding = "\x1b[38;2;%s;49m▘\x1b[38;2;%s;48;2;%sm" % (background, foreground, background)

    def append(self, new_content):
        self.content += new_content

        self.lines += len(new_content)
        self.cols = max(self.cols, ansi_cols(new_content))
        
    def __str__(self):
        string = "\x1b[38;2;%s;48;2;%sm" % (self.foreground,self.background)

        string += self.top_left_padding + self.top_padding*self.cols + self.top_right_padding + "\n" 

        for line in [self.header]+self.content:
            # Fill with extra spaces to the right so that the background is visible
            string += self.left_padding + line + " "*(self.cols-ansi_len(line)) + self.right_padding + "\n"

        string += self.bot_left_padding + self.bot_padding*self.cols + self.bot_right_padding 

        # Reset background
        string += "\x1b[39;49m"

        return string

class GPUContainer(Container):
    def __init__(self, scheme, index=0, freq=0, max_freq=1, used_mem=0, total_mem=1, power=0, max_power=1, util=0, local_processes=0):
        self.scheme = scheme 
        self.index = index
        self.freq = freq
        self.max_freq = max_freq
        self.used_mem = used_mem
        self.total_mem = total_mem
        self.power = power
        self.max_power = max_power
        self.util = util
        
        foreground = scheme["onSurface"]
        background = scheme["surfaceContainerLow"]
        header = "\x1b[38;2;%s;1mGPU %d\x1b[38;2;%s;22m" % (scheme["secondary"], index, foreground)
        icon = lambda x: "\x1b[38;2;%sm%s\x1b[38;2;%sm" % (scheme["primary"], x, scheme["onSurface"])
        content = ["%s Freq.: %14.14s %s" % (icon(" "), "%d/%d MHz" % (freq,max_freq), get_bar(freq/max_freq,scheme["tertiary"],scheme["tertiaryContainer"])),
                   "%s  Mem.: %14.14s %s" % (icon(" "), "%d/%d GiB" % (used_mem,total_mem), get_bar(used_mem/total_mem,scheme["tertiary"],scheme["tertiaryContainer"])),
                   "%s  Pow.: %14.14s %s" % (icon(" "), "%d/%d W" % (power,max_power), get_bar(power/max_power,scheme["tertiary"],scheme["tertiaryContainer"])),
                   "%s Util.: %14.14s %s" % (icon(" "), "%d%%" % round(util*100), get_bar(util,scheme["tertiary"],scheme["tertiaryContainer"])),
                   "%s Proc.: %14.14s %s" % (icon(" "), "%d" % local_processes, get_traffic(local_processes>0,scheme["tertiary"],scheme["tertiaryContainer"]))]

        super().__init__(foreground, background, header, content)

def cleanup(fd, old_settings):
    nvmlShutdown()

    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    # Exit alternate buffer (restores some settings)
    print("\x1b[?1049l",end="",flush=True)
    
    print("Bye sexy 😘!")

    exit(0)
