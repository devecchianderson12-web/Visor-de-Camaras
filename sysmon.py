"""Monitor de rendimiento del sistema SIN dependencias (ctypes en Windows; /proc en Linux solo para pruebas).
 - CPU y RAM: llamadas de microsegundos (GetSystemTimes / GlobalMemoryStatusEx).
 - GPU: contadores de Windows «GPU Engine» (todas las marcas, Windows 10 1709+) o NVML (NVIDIA, incluso en 8.1).
   Si no hay forma de medirla, la GPU se informa como None («n/d»)."""
import os
import re
import sys
import threading

IS_WIN = sys.platform == "win32"
_ENG_RE = re.compile(r"luid_0x[0-9A-Fa-f]+_0x[0-9A-Fa-f]+_phys_\d+_eng_\d+")


def _pct(last, cur):
    """last/cur = (inactivo, total) acumulados -> % de uso entre ambas lecturas."""
    if not last:
        return None
    di, dt = cur[0] - last[0], cur[1] - last[1]
    if dt <= 0:
        return None
    return max(0.0, min(100.0, 100.0 * (1.0 - di / dt)))


if IS_WIN:
    import ctypes
    from ctypes import wintypes

    class _MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [("dwLength", wintypes.DWORD), ("dwMemoryLoad", wintypes.DWORD),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

    class _PdhUnion(ctypes.Union):
        _fields_ = [("longValue", ctypes.c_long), ("doubleValue", ctypes.c_double),
                    ("largeValue", ctypes.c_longlong), ("AnsiStringValue", ctypes.c_char_p),
                    ("WideStringValue", ctypes.c_wchar_p)]

    class _PdhValue(ctypes.Structure):
        _fields_ = [("CStatus", wintypes.DWORD), ("u", _PdhUnion)]

    class _PdhItem(ctypes.Structure):
        _fields_ = [("szName", ctypes.c_wchar_p), ("FmtValue", _PdhValue)]

    class _NvmlUtil(ctypes.Structure):
        _fields_ = [("gpu", ctypes.c_uint), ("memory", ctypes.c_uint)]

    class _WinCpuRam:
        def __init__(self):
            k32 = ctypes.windll.kernel32
            self._times = k32.GetSystemTimes
            self._times.argtypes = [ctypes.POINTER(wintypes.FILETIME)] * 3
            self._times.restype = wintypes.BOOL
            self._mem = k32.GlobalMemoryStatusEx
            self._mem.argtypes = [ctypes.POINTER(_MEMORYSTATUSEX)]
            self._mem.restype = wintypes.BOOL
            self._last = None

        @staticmethod
        def _ft(ft):
            return (ft.dwHighDateTime << 32) | ft.dwLowDateTime

        def cpu(self):
            idle, kern, user = wintypes.FILETIME(), wintypes.FILETIME(), wintypes.FILETIME()
            if not self._times(ctypes.byref(idle), ctypes.byref(kern), ctypes.byref(user)):
                return None
            cur = (self._ft(idle), self._ft(kern) + self._ft(user))   # «kernel» ya incluye el tiempo inactivo
            last, self._last = self._last, cur
            return _pct(last, cur)

        def ram(self):
            m = _MEMORYSTATUSEX()
            m.dwLength = ctypes.sizeof(m)
            return float(m.dwMemoryLoad) if self._mem(ctypes.byref(m)) else None

    class _GpuPdh:
        """Contadores «GPU Engine» (Windows 10 1709+): uso = motor más cargado, como el Administrador de tareas."""
        FMT_DOUBLE = 0x200
        MORE_DATA = 0x800007D2

        def __init__(self):
            pdh = ctypes.WinDLL("pdh")
            vp, dw = ctypes.c_void_p, wintypes.DWORD
            pdh.PdhOpenQueryW.argtypes = [wintypes.LPCWSTR, ctypes.c_size_t, ctypes.POINTER(vp)]
            pdh.PdhAddEnglishCounterW.argtypes = [vp, wintypes.LPCWSTR, ctypes.c_size_t, ctypes.POINTER(vp)]
            pdh.PdhCollectQueryData.argtypes = [vp]
            pdh.PdhCloseQuery.argtypes = [vp]
            pdh.PdhGetFormattedCounterArrayW.argtypes = [vp, dw, ctypes.POINTER(dw), ctypes.POINTER(dw), vp]
            for f in (pdh.PdhOpenQueryW, pdh.PdhAddEnglishCounterW, pdh.PdhCollectQueryData,
                      pdh.PdhCloseQuery, pdh.PdhGetFormattedCounterArrayW):
                f.restype = ctypes.c_long
            self._pdh = pdh
            self._q, self._c = vp(), vp()
            if pdh.PdhOpenQueryW(None, 0, ctypes.byref(self._q)) != 0:
                raise OSError("PdhOpenQuery")
            if pdh.PdhAddEnglishCounterW(self._q, r"\GPU Engine(*)\Utilization Percentage", 0,
                                         ctypes.byref(self._c)) != 0:
                pdh.PdhCloseQuery(self._q)
                raise OSError("este Windows no tiene contadores de GPU")
            pdh.PdhCollectQueryData(self._q)

        def sample(self):
            pdh = self._pdh
            if pdh.PdhCollectQueryData(self._q) != 0:
                return None
            size, count = wintypes.DWORD(0), wintypes.DWORD(0)
            st = pdh.PdhGetFormattedCounterArrayW(self._c, self.FMT_DOUBLE, ctypes.byref(size),
                                                  ctypes.byref(count), None)
            if (st & 0xFFFFFFFF) != self.MORE_DATA or not size.value:
                return None
            buf = ctypes.create_string_buffer(size.value)
            if pdh.PdhGetFormattedCounterArrayW(self._c, self.FMT_DOUBLE, ctypes.byref(size),
                                                ctypes.byref(count), buf) != 0:
                return None
            items = ctypes.cast(buf, ctypes.POINTER(_PdhItem))
            per_engine = {}
            for i in range(count.value):
                it = items[i]
                m = _ENG_RE.search(it.szName or "")
                if m and it.FmtValue.CStatus in (0, 1):
                    per_engine[m.group(0)] = per_engine.get(m.group(0), 0.0) + it.FmtValue.u.doubleValue
            return min(100.0, max(per_engine.values())) if per_engine else 0.0

        def close(self):
            try:
                self._pdh.PdhCloseQuery(self._q)
            except Exception:
                pass

    class _GpuNvml:
        """NVIDIA (también en Windows 8.1) a través de nvml.dll, que instala el controlador."""

        def __init__(self):
            lib = None
            pf = os.environ.get("ProgramFiles", r"C:\Program Files")
            for name in ("nvml.dll", os.path.join(pf, "NVIDIA Corporation", "NVSMI", "nvml.dll")):
                try:
                    lib = ctypes.CDLL(name)
                    break
                except OSError:
                    continue
            if lib is None or lib.nvmlInit_v2() != 0:
                raise OSError("sin NVML")
            n = ctypes.c_uint(0)
            lib.nvmlDeviceGetCount_v2(ctypes.byref(n))
            self._h = []
            for i in range(n.value):
                h = ctypes.c_void_p()
                if lib.nvmlDeviceGetHandleByIndex_v2(i, ctypes.byref(h)) == 0:
                    self._h.append(h)
            if not self._h:
                raise OSError("NVML sin dispositivos")
            self._lib = lib

        def sample(self):
            best = None
            for h in self._h:
                u = _NvmlUtil()
                if self._lib.nvmlDeviceGetUtilizationRates(h, ctypes.byref(u)) == 0:
                    best = max(best or 0, u.gpu)
            return None if best is None else float(best)

        def close(self):
            try:
                self._lib.nvmlShutdown()
            except Exception:
                pass

    class _WinBackend:
        def __init__(self):
            self._cr = _WinCpuRam()
            self._gpu = None
            self.gpu_source = "no disponible"
            for cls, label in ((_GpuPdh, "contadores de Windows"), (_GpuNvml, "NVIDIA NVML")):
                try:
                    self._gpu, self.gpu_source = cls(), label
                    break
                except Exception:
                    continue

        def cpu(self):
            return self._cr.cpu()

        def ram(self):
            return self._cr.ram()

        def gpu(self):
            return self._gpu.sample() if self._gpu else None

        def close(self):
            if self._gpu:
                self._gpu.close()


class _LinuxBackend:
    """Solo para pruebas fuera de Windows."""
    gpu_source = "no disponible"

    def __init__(self):
        self._last = None

    def cpu(self):
        with open("/proc/stat") as f:
            vals = [int(x) for x in f.readline().split()[1:]]
        cur = (vals[3] + (vals[4] if len(vals) > 4 else 0), sum(vals[:8]))
        last, self._last = self._last, cur
        return _pct(last, cur)

    def ram(self):
        info = {}
        with open("/proc/meminfo") as f:
            for line in f:
                k, v = line.split(":", 1)
                info[k] = int(v.split()[0])
        return 100.0 * (1.0 - info["MemAvailable"] / info["MemTotal"])

    def gpu(self):
        return None

    def close(self):
        pass


def _make_backend():
    return _WinBackend() if IS_WIN else _LinuxBackend()


class SysMonitor:
    """Hilo que mide 1 vez por segundo mientras está activo. snapshot() -> (cpu %, ram %, gpu % | None)."""

    def __init__(self):
        self.cpu, self.ram, self.gpu = 0.0, 0.0, None
        self.gpu_source = ""
        self._thread, self._stop = None, threading.Event()

    def start(self):
        if self._thread and self._thread.is_alive() and not self._stop.is_set():
            return
        self._stop = threading.Event()               # un evento nuevo por ejecución: sin carreras
        self._thread = threading.Thread(target=self._run, args=(self._stop,), daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def snapshot(self):
        return self.cpu, self.ram, self.gpu

    def _run(self, stop):
        backend = None
        try:
            backend = _make_backend()
            self.gpu_source = backend.gpu_source
            while not stop.is_set():
                try:
                    c, r, g = backend.cpu(), backend.ram(), backend.gpu()
                except Exception:
                    c = r = g = None
                if c is not None:
                    self.cpu = c
                if r is not None:
                    self.ram = r
                self.gpu = g
                stop.wait(1.0)
        finally:
            if backend:
                backend.close()
