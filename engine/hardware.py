"""Dynamic hardware detection — CPU & GPU profiling for 95% utilization."""

import os
import shutil
import subprocess
import platform
import threading

_hw_cache = None
_hw_lock = threading.Lock()


def detect_hardware():
    """Detect CPU and GPU capabilities. Cached after first call."""
    global _hw_cache
    with _hw_lock:
        if _hw_cache is not None:
            return _hw_cache
        _hw_cache = _detect()
        return _hw_cache


def _detect():
    info = {
        "cpu_cores_physical": 0,
        "cpu_cores_logical": 0,
        "cpu_name": "",
        "cpu_freq_mhz": 0,
        "ram_total_gb": 0,
        "ram_available_gb": 0,
        "gpu_name": "",
        "gpu_vram_mb": 0,
        "gpu_vendor": "",          # nvidia, amd, intel, none
        "gpu_encoder": "",         # h264_nvenc, h264_amf, h264_qsv, libx264
        "gpu_encoder_flags": [],
        "gpu_utilization_pct": 0,
        "gpu_decode_available": False,
    }

    # ── CPU ────────────────────────────────────────────────────────────────
    info["cpu_cores_logical"] = os.cpu_count() or 1

    # Physical cores via wmic (Windows)
    try:
        out = subprocess.run(
            ["wmic", "cpu", "get", "NumberOfCores", "/value"],
            capture_output=True, text=True, timeout=5,
        ).stdout
        for line in out.strip().splitlines():
            if "NumberOfCores=" in line:
                info["cpu_cores_physical"] = int(line.split("=")[1].strip())
                break
    except Exception:
        info["cpu_cores_physical"] = max(1, info["cpu_cores_logical"] // 2)

    # CPU name
    try:
        out = subprocess.run(
            ["wmic", "cpu", "get", "Name", "/value"],
            capture_output=True, text=True, timeout=5,
        ).stdout
        for line in out.strip().splitlines():
            if "Name=" in line:
                info["cpu_name"] = line.split("=", 1)[1].strip()
                break
    except Exception:
        pass

    # CPU frequency
    try:
        out = subprocess.run(
            ["wmic", "cpu", "get", "MaxClockSpeed", "/value"],
            capture_output=True, text=True, timeout=5,
        ).stdout
        for line in out.strip().splitlines():
            if "MaxClockSpeed=" in line:
                info["cpu_freq_mhz"] = int(line.split("=")[1].strip())
                break
    except Exception:
        pass

    # ── RAM ────────────────────────────────────────────────────────────────
    try:
        out = subprocess.run(
            ["wmic", "os", "get", "TotalVisibleMemorySize,FreePhysicalMemory", "/value"],
            capture_output=True, text=True, timeout=5,
        ).stdout
        for line in out.strip().splitlines():
            if "TotalVisibleMemorySize=" in line:
                info["ram_total_gb"] = round(int(line.split("=")[1].strip()) / 1024 / 1024, 1)
            elif "FreePhysicalMemory=" in line:
                info["ram_available_gb"] = round(int(line.split("=")[1].strip()) / 1024 / 1024, 1)
    except Exception:
        pass

    # ── GPU (NVIDIA via nvidia-smi) ────────────────────────────────────────
    nvidia_smi = shutil.which("nvidia-smi")
    if nvidia_smi:
        try:
            out = subprocess.run(
                [nvidia_smi, "--query-gpu=name,memory.total,memory.free,utilization.gpu",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=10,
            ).stdout.strip()
            if out:
                parts = [p.strip() for p in out.split(",")]
                info["gpu_name"] = parts[0] if len(parts) > 0 else ""
                info["gpu_vram_mb"] = int(parts[1]) if len(parts) > 1 else 0
                info["gpu_vendor"] = "nvidia"
                info["gpu_utilization_pct"] = int(parts[3]) if len(parts) > 3 else 0
        except Exception:
            pass

    # ── GPU (AMD — fallback to wmic) ──────────────────────────────────────
    if not info["gpu_vendor"]:
        try:
            out = subprocess.run(
                ["wmic", "path", "win32_videocontroller", "get",
                 "Name,AdapterRAM", "/value"],
                capture_output=True, text=True, timeout=5,
            ).stdout
            name = ""
            vram = 0
            for line in out.strip().splitlines():
                if "Name=" in line:
                    name = line.split("=", 1)[1].strip()
                elif "AdapterRAM=" in line:
                    try:
                        vram = int(line.split("=")[1].strip()) // (1024 * 1024)
                    except (ValueError, ZeroDivisionError):
                        pass
            if name:
                info["gpu_name"] = name
                info["gpu_vram_mb"] = vram
                nl = name.lower()
                if "nvidia" in nl or "geforce" in nl or "rtx" in nl or "gtx" in nl:
                    info["gpu_vendor"] = "nvidia"
                elif "amd" in nl or "radeon" in nl or "rx " in nl:
                    info["gpu_vendor"] = "amd"
                elif "intel" in nl or "uhd" in nl or "iris" in nl or "arc" in nl:
                    info["gpu_vendor"] = "intel"
        except Exception:
            pass

    # ── FFmpeg encoder detection ──────────────────────────────────────────
    ffmpeg = _find_ffmpeg()
    info["gpu_encoder"], info["gpu_encoder_flags"] = _detect_encoder(ffmpeg, info["gpu_vendor"])

    # GPU decode (hwaccel) availability
    if info["gpu_vendor"] == "nvidia":
        info["gpu_decode_available"] = _check_ffmpeg_decoder(ffmpeg, "h264_cuvid")
    elif info["gpu_vendor"] == "amd":
        info["gpu_decode_available"] = _check_ffmpeg_decoder(ffmpeg, "h264_amf")
    elif info["gpu_vendor"] == "intel":
        info["gpu_decode_available"] = _check_ffmpeg_decoder(ffmpeg, "h264_qsv")

    return info


def _find_ffmpeg():
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return "ffmpeg"


def _detect_encoder(ffmpeg, gpu_vendor):
    """Detect best available H.264 encoder from FFmpeg."""
    try:
        out = subprocess.run(
            [ffmpeg, "-hide_banner", "-encoders"],
            capture_output=True, text=True, timeout=10,
        ).stdout
    except Exception:
        return "libx264", ["-preset", "fast"]

    if gpu_vendor == "nvidia" and "h264_nvenc" in out:
        return "h264_nvenc", [
            "-preset", "p4", "-rc", "vbr", "-cq", "22", "-b_ref_mode", "disabled",
        ]
    if gpu_vendor == "amd" and "h264_amf" in out:
        return "h264_amf", ["-quality", "balanced", "-rc", "vbr_latency"]
    if gpu_vendor == "intel" and "h264_qsv" in out:
        return "h264_qsv", ["-preset", "medium", "-look_ahead", "1"]
    # Any GPU even if vendor mismatch
    if "h264_nvenc" in out:
        return "h264_nvenc", [
            "-preset", "p4", "-rc", "vbr", "-cq", "22", "-b_ref_mode", "disabled",
        ]
    if "h264_amf" in out:
        return "h264_amf", ["-quality", "balanced", "-rc", "vbr_latency"]
    if "h264_qsv" in out:
        return "h264_qsv", ["-preset", "medium", "-look_ahead", "1"]

    return "libx264", ["-preset", "fast"]


def _check_ffmpeg_decoder(ffmpeg, decoder_name):
    try:
        out = subprocess.run(
            [ffmpeg, "-hide_banner", "-decoders"],
            capture_output=True, text=True, timeout=10,
        ).stdout
        return decoder_name in out
    except Exception:
        return False


def compute_allocation(hw=None, target_utilization=0.95):
    """Compute optimal CPU/GPU allocation for 95% utilization.

    Returns dict with:
        frame_workers     — number of ProcessPoolExecutor workers for frame rendering
        encode_threads    — FFmpeg -threads value for encoding
        gpu_encoder       — encoder name (h264_nvenc, etc.)
        gpu_encoder_flags — extra FFmpeg flags for the encoder
        is_gpu_encode     — whether GPU encoding is available
        chunk_strategy    — 'large' for high-core, 'small' for low-core systems
    """
    if hw is None:
        hw = detect_hardware()

    logical = hw["cpu_cores_logical"]
    physical = hw["cpu_cores_physical"] or max(1, logical // 2)
    ram_gb = hw["ram_available_gb"] or 4
    gpu_vram = hw["gpu_vram_mb"]
    is_gpu = hw["gpu_encoder"] != "libx264"

    # ── Frame rendering workers (CPU-bound, uses ProcessPoolExecutor) ─────
    # Use 95% of logical cores for rendering.
    # Each worker ~200-400 MB RAM for Pillow frame rendering.
    # Cap by available RAM: max workers = available_ram / 0.4 GB per worker
    target_workers = max(1, int(logical * target_utilization))
    ram_cap = max(1, int(ram_gb / 0.4))
    frame_workers = min(target_workers, ram_cap)

    # ── Encoding threads ──────────────────────────────────────────────────
    if is_gpu:
        # GPU encoding: let FFmpeg auto-manage threads, GPU handles heavy lifting
        encode_threads = "0"
    else:
        # CPU encoding: use 95% of cores
        encode_threads = str(max(1, int(logical * target_utilization)))

    # ── Chunk strategy ────────────────────────────────────────────────────
    # High-core systems: larger chunks = less overhead
    # Low-core systems: smaller chunks = better load balancing
    chunk_strategy = "large" if physical >= 8 else "small"

    return {
        "frame_workers": frame_workers,
        "encode_threads": encode_threads,
        "gpu_encoder": hw["gpu_encoder"],
        "gpu_encoder_flags": hw["gpu_encoder_flags"],
        "is_gpu_encode": is_gpu,
        "gpu_decode_available": hw["gpu_decode_available"],
        "chunk_strategy": chunk_strategy,
    }


def print_hardware_summary(hw=None, alloc=None):
    """Print a formatted hardware summary to stdout."""
    if hw is None:
        hw = detect_hardware()
    if alloc is None:
        alloc = compute_allocation(hw)

    print("=" * 60)
    print("  HARDWARE PROFILE")
    print("=" * 60)
    print(f"  CPU : {hw['cpu_name'] or 'Unknown'}")
    print(f"        {hw['cpu_cores_physical']}P / {hw['cpu_cores_logical']}L cores @ {hw['cpu_freq_mhz']} MHz")
    print(f"  RAM : {hw['ram_total_gb']} GB total, {hw['ram_available_gb']} GB available")
    print(f"  GPU : {hw['gpu_name'] or 'None detected'}")
    if hw["gpu_vram_mb"]:
        print(f"        {hw['gpu_vram_mb']} MB VRAM | Encoder: {hw['gpu_encoder']}")
    print("-" * 60)
    print(f"  ALLOCATION (95% target)")
    print(f"  Frame workers : {alloc['frame_workers']} processes")
    print(f"  Encode threads: {alloc['encode_threads']}")
    print(f"  GPU encode    : {'YES' if alloc['is_gpu_encode'] else 'NO (CPU libx264)'}")
    print(f"  GPU decode    : {'YES' if alloc['gpu_decode_available'] else 'NO'}")
    print(f"  Chunk strategy: {alloc['chunk_strategy']}")
    print("=" * 60)
