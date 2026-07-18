"""执行批次校准试跑并搜索可启动的最大 batch。"""

import gc
import os
import subprocess
import time

from shared.utils.json_utils import load_json_file, save_json_file


def clear_accelerator_cache():
    """Release Python, CUDA and MPS caches between calibration attempts."""
    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        if getattr(torch.backends, 'mps', None) and torch.backends.mps.is_available():
            try:
                torch.mps.empty_cache()
            except Exception:
                pass
    except Exception:
        pass


def is_resource_exhaustion(error_text, exit_code=0):
    """Judge whether one failed probe most likely died because of memory pressure."""
    text = str(error_text or '').lower()
    resource_markers = (
        'out of memory',
        'cuda out of memory',
        'mps backend out of memory',
        'mps out of memory',
        'not enough memory',
        'killed',
        'cannot allocate memory',
    )
    if any(marker in text for marker in resource_markers):
        return True
    return int(exit_code or 0) < 0


def run_batch_probe(
    task_id,
    batch,
    model_path,
    data_yaml,
    probe_dir,
    imgsz,
    device_type,
    *,
    fraction,
    time_hours,
    workers,
    probe_script_path,
):
    """Run one tiny training probe and return a normalized result payload."""
    probe_input_path = os.path.join(probe_dir, f'probe-b{batch}.json')
    probe_output_path = os.path.join(probe_dir, f'probe-b{batch}.result.json')
    probe_log_path = os.path.join(probe_dir, f'probe-b{batch}.log')
    payload = {
        'task_id': task_id,
        'batch': int(batch),
        'imgsz': int(imgsz),
        'model_path': model_path,
        'data_yaml': data_yaml,
        'save_dir': os.path.join(probe_dir, f'run-b{batch}'),
        'device': device_type,
        'fraction': fraction,
        'time_hours': time_hours,
        'workers': workers,
    }
    save_json_file(probe_input_path, payload)

    started = time.perf_counter()
    with open(probe_log_path, 'ab') as log_file:
        proc = subprocess.Popen(
            [os.sys.executable, probe_script_path, probe_input_path, probe_output_path],
            cwd=os.path.dirname(probe_script_path),
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            close_fds=True,
            env=os.environ.copy(),
        )
        exit_code = proc.wait()
    duration_ms = int((time.perf_counter() - started) * 1000)

    result = {}
    if os.path.isfile(probe_output_path):
        try:
            result = load_json_file(probe_output_path, default={}) or {}
        except Exception:
            result = {}

    return {
        'batch': int(batch),
        'ok': bool(result.get('ok')),
        'exit_code': int(result.get('exit_code', exit_code)),
        'duration_ms': duration_ms,
        'log_path': probe_log_path,
        'error': result.get('error') or '',
        'failure_kind': result.get('failure_kind') or '',
    }


def search_calibration_limit(
    *,
    task_id,
    stop_signal_path,
    max_attempts,
    max_batch,
    run_probe,
    is_stop_requested,
    update_progress,
    clear_cache,
):
    """Search the maximum runnable batch size using power-of-two expansion plus binary search."""
    attempts = []
    passed_batch = 0
    low = 1
    high = int(max_batch)
    phase = 'power'
    current = 1

    while low <= high and len(attempts) < int(max_attempts):
        if is_stop_requested(stop_signal_path):
            raise InterruptedError('用户终止校准')

        progress = min(95, max(5, int(len(attempts) / int(max_attempts) * 100)))
        update_progress(task_id, progress, f'正在实测 batch={current}...')
        attempt = run_probe(current)
        attempts.append(attempt)
        clear_cache()

        if attempt['ok']:
            passed_batch = current
            if phase == 'power':
                if current >= high:
                    break
                current = min(high, current * 2)
                if current == passed_batch:
                    break
            else:
                low = current + 1
                if low > high:
                    break
                current = (low + high) // 2
            continue

        if is_resource_exhaustion(attempt.get('error'), attempt.get('exit_code')):
            if passed_batch == 0 and current <= 1:
                raise ValueError(
                    f'batch=1 也无法启动，最近错误: {attempt.get("error") or "未知资源错误"}'
                )
            if phase == 'power':
                phase = 'binary'
                high = max(current - 1, passed_batch)
                low = max(passed_batch + 1, 1)
            else:
                high = current - 1
            if low > high:
                break
            current = (low + high) // 2
            continue

        raise ValueError(attempt.get('error') or f'校准试跑失败（exit_code={attempt.get("exit_code")}）')

    return {
        'max_batch': passed_batch,
        'attempt_count': len(attempts),
        'attempts': attempts,
    }
