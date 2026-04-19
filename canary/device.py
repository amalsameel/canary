"""hardware profiling for backend recommendations."""
from __future__ import annotations

from dataclasses import dataclass
import ctypes
import os
import platform
import shutil


@dataclass
class DeviceProfile:
    system: str
    machine: str
    cpu_count: int
    memory_gb: float | None
    has_discrete_gpu_hint: bool
    apple_silicon: bool

    @property
    def accelerator(self) -> str:
        if self.apple_silicon:
            return "Apple Silicon"
        if self.has_discrete_gpu_hint:
            return "discrete GPU"
        return "CPU"

    @property
    def local_recommended(self) -> bool:
        if self.apple_silicon or self.has_discrete_gpu_hint:
            return True
        if self.memory_gb is None:
            return self.cpu_count >= 10
        return self.cpu_count >= 10 and self.memory_gb >= 16

    @property
    def local_warning(self) -> bool:
        return not self.local_recommended

    @property
    def recommended_mode(self) -> str:
        return "local" if self.local_recommended else "online"

    @property
    def summary(self) -> str:
        parts = [self.system.lower(), self.machine.lower(), f"{self.cpu_count} CPU"]
        if self.memory_gb is not None:
            parts.append(f"{int(round(self.memory_gb))} GB RAM")
        parts.append(self.accelerator)
        return "  ·  ".join(parts)


def _memory_gb() -> float | None:
    try:
        if os.name == "posix":
            pages = os.sysconf("SC_PHYS_PAGES")
            page_size = os.sysconf("SC_PAGE_SIZE")
            return (pages * page_size) / (1024 ** 3)
    except (AttributeError, OSError, ValueError):
        pass

    if os.name == "nt":
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):  # type: ignore[attr-defined]
            return stat.ullTotalPhys / (1024 ** 3)
    return None


def detect_device_profile() -> DeviceProfile:
    system = platform.system()
    machine = platform.machine()
    cpu_count = os.cpu_count() or 1
    memory_gb = _memory_gb()
    apple_silicon = system == "Darwin" and machine.lower() in {"arm64", "aarch64"}
    has_discrete_gpu_hint = shutil.which("nvidia-smi") is not None

    return DeviceProfile(
        system=system,
        machine=machine,
        cpu_count=cpu_count,
        memory_gb=memory_gb,
        has_discrete_gpu_hint=has_discrete_gpu_hint,
        apple_silicon=apple_silicon,
    )
