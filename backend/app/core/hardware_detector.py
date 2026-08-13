"""Detect local machine specs: RAM, CPU, GPU, disk, Ollama status, installed models."""

import json
import os
import shutil
import subprocess


def _run(cmd: list[str], timeout: int = 5) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except Exception:
        return ""


def detect_ram_gb() -> float:
    try:
        import psutil

        return round(psutil.virtual_memory().total / (1024**3), 1)
    except ImportError:
        pass
    # macOS fallback
    out = _run(["sysctl", "-n", "hw.memsize"])
    if out:
        return round(int(out) / (1024**3), 1)
    return 0.0


def detect_ram_available_gb() -> float:
    try:
        import psutil

        return round(psutil.virtual_memory().available / (1024**3), 1)
    except ImportError:
        pass
    out = _run(["vm_stat"])
    if "free" in out:
        # rough parse
        try:
            free_pages = [line for line in out.split("\n") if "free" in line][0]
            count = int("".join(c for c in free_pages.split(":")[1] if c.isdigit()))
            return round(count * 16384 / (1024**3), 1)
        except Exception:
            return 0.0
    return 0.0


def detect_cpu() -> dict:
    info = {"model": "", "cores_physical": 0, "cores_logical": 0}
    out = _run(["sysctl", "-n", "machdep.cpu.brand_string"])
    if out:
        info["model"] = out
    out2 = _run(["sysctl", "-n", "hw.physicalcpu"])
    if out2:
        info["cores_physical"] = int(out2)
    out3 = _run(["sysctl", "-n", "hw.logicalcpu"])
    if out3:
        info["cores_logical"] = int(out3)
    return info


def detect_platform() -> str:
    import platform as pf

    return f"{pf.system()} {pf.machine()}"


def detect_is_apple_silicon() -> bool:
    return detect_platform().startswith("Darwin arm64")


def detect_disk_free_gb(path: str | None = None) -> float:
    try:
        usage = shutil.disk_usage(path or os.getcwd())
        return round(usage.free / (1024**3), 1)
    except Exception:
        return 0.0


def detect_ollama_installed() -> bool:
    return shutil.which("ollama") is not None


def detect_ollama_running() -> bool:
    try:
        import requests

        r = requests.get("http://127.0.0.1:11434/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def detect_ollama_models() -> list[dict]:
    if not detect_ollama_running():
        return []
    try:
        import requests

        r = requests.get("http://127.0.0.1:11434/api/tags", timeout=5)
        data = r.json()
        models = []
        for m in data.get("models", []):
            name = m.get("name", "")
            size = m.get("size", 0)
            models.append(
                {
                    "name": name.replace(":latest", ""),
                    "size_gb": round(size / (1024**3), 1),
                    "digest": m.get("digest", "")[:12],
                }
            )
        return models
    except Exception:
        return []


def detect_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


def detect_python_version() -> str:
    import sys

    return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


def detect_gpu() -> dict:
    """Detect GPU model info (Apple Silicon or discrete GPU)."""
    info = {"model": "", "detail": ""}
    # Apple Silicon
    if detect_is_apple_silicon():
        out = _run(["sysctl", "-n", "machdep.cpu.brand_string"])
        if out:
            info["model"] = f"Apple {out.split(' ')[-1]}" if "Apple" not in out else out
        # Try to get GPU core count
        gpu_core = _run(["sysctl", "-n", "hw.perflevel1.logicalcpu"])
        if gpu_core and gpu_core.isdigit():
            info["detail"] = f"{gpu_core} GPU cores"
        return info
    # Non-Apple: try system_profiler
    out = _run(["system_profiler", "SPDisplaysDataType", "-json"], timeout=8)
    if out:
        try:
            data = json.loads(out)
            displays = data.get("SPDisplaysDataType", [])
            if displays:
                info["model"] = displays[0].get("sppci_model", "")
                info["detail"] = displays[0].get("sppci_vendor", "")
        except Exception:
            pass
    return info


def detect_all() -> dict:
    ram_total = detect_ram_gb()
    ram_avail = detect_ram_available_gb()
    cpu = detect_cpu()
    is_silicon = detect_is_apple_silicon()
    disk_free = detect_disk_free_gb()
    ollama_installed = detect_ollama_installed()
    ollama_running = detect_ollama_running()
    ollama_models = detect_ollama_models() if ollama_running else []
    ffmpeg_ok = detect_ffmpeg()
    gpu = detect_gpu()

    return {
        "platform": detect_platform(),
        "is_apple_silicon": is_silicon,
        "silicon": gpu["model"] if is_silicon else None,
        "gpu_model": gpu["model"] if not is_silicon else None,
        "gpu_detail": gpu["detail"],
        "cpu_model": cpu.get("model", ""),
        "cpu_physical_cores": cpu.get("cores_physical", 0),
        "cpu_logical_cores": cpu.get("cores_logical", 0),
        "ram_total_gb": ram_total,
        "ram_available_gb": ram_avail,
        "ram_tier": _ram_tier(ram_total),
        "cpu": cpu,
        "disk_free_gb": disk_free,
        "ollama": {
            "installed": ollama_installed,
            "running": ollama_running,
            "models": ollama_models,
        },
        "ffmpeg_installed": ffmpeg_ok,
        "python_version": detect_python_version(),
    }


def _ram_tier(ram_gb: float) -> str:
    if ram_gb < 6:
        return "edge"
    elif ram_gb < 12:
        return "light"
    elif ram_gb < 24:
        return "medium"
    else:
        return "heavy"
