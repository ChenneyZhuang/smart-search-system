
"""psutil回退模块 - 当psutil不可用时提供基本功能"""

import sys
import os
import time

class Process:
    def __init__(self, pid=None):
        self.pid = pid or os.getpid()
    
    def memory_info(self):
        class MemoryInfo:
            rss = 1024 * 1024 * 100  # 模拟100MB
            vms = 1024 * 1024 * 200  # 模拟200MB
        
        return MemoryInfo()
    
    def memory_percent(self):
        return 10.0  # 模拟10%

def cpu_percent(interval=None):
    return 25.0  # 模拟25%

def virtual_memory():
    class VirtualMemory:
        total = 1024 * 1024 * 1024 * 16  # 16GB
        available = 1024 * 1024 * 1024 * 8  # 8GB
        percent = 50.0  # 50%
    
    return VirtualMemory()

def disk_usage(path):
    class DiskUsage:
        total = 1024 * 1024 * 1024 * 500  # 500GB
        used = 1024 * 1024 * 1024 * 200  # 200GB
        free = 1024 * 1024 * 1024 * 300  # 300GB
        percent = 40.0  # 40%
    
    return DiskUsage()

def cpu_count():
    return 4  # 模拟4核

__version__ = "0.0.0-fallback"
