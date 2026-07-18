"""探测训练页面所需的设备、内存与导出能力信息。"""

import os
import platform
import re
import subprocess

def get_device():
    """返回 Ultralytics 可接受的 device 表达。优先用首个 CUDA GPU，否则回退 CPU。"""
    try:
        import torch

        if torch.cuda.is_available():
            return "0"
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
    except Exception:
        pass
    return os.environ.get("VT_DEVICE", "cpu")


def get_export_hardware_formats():
    """返回当前硬件可用的导出格式矩阵。"""
    device_type = get_device()
    engine_available = str(device_type).isdigit()
    return {
        "onnx": {"available": True, "reason": ""},
        "openvino": {"available": True, "reason": ""},
        "engine": {
            "available": engine_available,
            "reason": "" if engine_available else "需要NVIDIA支持",
        },
    }


def run_command_text(args):
    """Run one short system command and return trimmed stdout on success."""
    try:
        result = subprocess.run(
            list(args),
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception:
        return ''
    if result.returncode != 0:
        return ''
    return (result.stdout or '').strip()


def read_meminfo():
    """Read Linux `/proc/meminfo` into bytes for total and available memory fallback."""
    data = {}
    try:
        with open('/proc/meminfo', 'r', encoding='utf-8', errors='replace') as handle:
            for line in handle:
                if ':' not in line:
                    continue
                key, raw_value = line.split(':', 1)
                parts = raw_value.strip().split()
                if not parts:
                    continue
                try:
                    data[key] = int(parts[0]) * 1024
                except ValueError:
                    continue
    except OSError:
        pass
    return data


def get_visible_memory():
    """Return total and currently visible available system memory in bytes."""
    if platform.system() == 'Darwin':
        total_bytes = 0
        available_bytes = 0
        total_text = run_command_text(['sysctl', '-n', 'hw.memsize'])
        try:
            total_bytes = int(total_text or 0)
        except ValueError:
            total_bytes = 0

        vm_stat = run_command_text(['vm_stat'])
        if vm_stat:
            page_size = 4096
            first_line, *lines = vm_stat.splitlines()
            match = re.search(r'page size of (\d+) bytes', first_line or '')
            if match:
                page_size = int(match.group(1))

            pages = {}
            for line in lines:
                if ':' not in line:
                    continue
                key, value = line.split(':', 1)
                raw = value.strip().rstrip('.').replace('.', '').replace(',', '')
                try:
                    pages[key.strip()] = int(raw)
                except ValueError:
                    continue

            available_pages = (
                pages.get('Pages free', 0)
                + pages.get('Pages inactive', 0)
                + pages.get('Pages speculative', 0)
            )
            available_bytes = available_pages * page_size

        return {
            'total_bytes': int(total_bytes or 0),
            'available_bytes': int(available_bytes or 0),
        }

    meminfo = read_meminfo()
    total_bytes = meminfo.get('MemTotal')
    available_bytes = meminfo.get('MemAvailable')

    if total_bytes is None:
        try:
            page_size = os.sysconf('SC_PAGE_SIZE')
            phys_pages = os.sysconf('SC_PHYS_PAGES')
            avail_pages = os.sysconf('SC_AVPHYS_PAGES')
            total_bytes = page_size * phys_pages
            available_bytes = page_size * avail_pages
        except (ValueError, OSError, AttributeError):
            total_bytes = 0
            available_bytes = 0

    return {
        'total_bytes': int(total_bytes or 0),
        'available_bytes': int(available_bytes or 0),
    }


def get_cpu_model():
    """Return one human-readable CPU model string for the current host."""
    if platform.system() == 'Darwin':
        brand = run_command_text(['sysctl', '-n', 'machdep.cpu.brand_string'])
        if brand:
            return brand
        brand = run_command_text(['sysctl', '-n', 'hw.model'])
        if brand:
            return brand
    cpuinfo = '/proc/cpuinfo'
    if os.path.exists(cpuinfo):
        try:
            with open(cpuinfo, 'r', encoding='utf-8', errors='replace') as handle:
                for line in handle:
                    if ':' not in line:
                        continue
                    key, value = line.split(':', 1)
                    if key.strip().lower() in ('model name', 'hardware'):
                        model = value.strip()
                        if model:
                            return model
        except OSError:
            pass
    return platform.processor() or platform.machine() or 'Unknown CPU'


def build_runtime_profile():
    """Build the frontend-facing runtime profile payload for training pages."""
    memory = get_visible_memory()
    device_type = get_device()
    device_label = {
        'cpu': 'CPU',
        'mps': 'Apple Silicon (MPS)',
    }.get(device_type, 'CUDA GPU' if str(device_type).isdigit() else str(device_type).upper())
    gpu = None
    cuda_available = False

    try:
        import torch

        cuda_available = bool(torch.cuda.is_available())
        if str(device_type).isdigit() and cuda_available:
            index = int(device_type)
            props = torch.cuda.get_device_properties(index)
            free_mem, total_mem = torch.cuda.mem_get_info(index)
            gpu = {
                'name': props.name,
                'total_memory_bytes': int(total_mem),
                'free_memory_bytes': int(free_mem),
            }
        elif device_type == 'mps':
            gpu = {
                'name': 'Apple Silicon Unified Memory',
                'total_memory_bytes': int(memory.get('total_bytes') or 0),
                'free_memory_bytes': int(memory.get('available_bytes') or 0),
            }
    except Exception:
        gpu = None

    return {
        'device': {
            'type': device_type,
            'label': device_label,
        },
        'platform': {
            'system': platform.system(),
            'release': platform.release(),
            'machine': platform.machine(),
            'python_version': platform.python_version(),
        },
        'cpu': {
            'model': get_cpu_model(),
            'logical_cores': os.cpu_count() or 0,
        },
        'memory': memory,
        'gpu': gpu,
        'hardware': {
            'cuda_available': cuda_available,
        },
        'export': {
            'formats': get_export_hardware_formats(),
        },
    }
