"""执行单轮训练探测并输出批量大小探测结果。"""

import os
import sys
import traceback

from shared.utils.fs_utils import remove_path_silent
from shared.utils.json_utils import load_json_file, save_json_file
from ultralytics import YOLO


def _stderr(message):
    """向标准错误输出探测过程日志。"""
    try:
        os.write(2, f'{message}\n'.encode('utf-8', errors='replace'))
    except Exception:
        pass


def _failure_kind(error_text):
    """根据错误文本归类资源不足或致命失败。"""
    text = str(error_text or '').lower()
    resource_markers = (
        'out of memory',
        'cuda out of memory',
        'mps backend out of memory',
        'mps out of memory',
        'not enough memory',
        'cannot allocate memory',
    )
    if any(marker in text for marker in resource_markers):
        return 'resource'
    return 'fatal'


def main():
    """执行单轮训练探测并写出结构化结果。"""
    if len(sys.argv) < 3:
        _stderr('batch_probe: missing input/output path')
        return 2

    input_path = sys.argv[1]
    output_path = sys.argv[2]
    payload = load_json_file(input_path, default={}) or {}

    save_dir = payload['save_dir']
    os.makedirs(save_dir, exist_ok=True)
    result = {
        'ok': False,
        'exit_code': 1,
        'failure_kind': '',
        'error': '',
    }

    try:
        model = YOLO(payload['model_path'])
        model.train(
            data=payload['data_yaml'],
            imgsz=int(payload.get('imgsz') or 640),
            batch=int(payload['batch']),
            device=payload.get('device'),
            project=os.path.dirname(save_dir),
            name=os.path.basename(save_dir),
            exist_ok=True,
            workers=int(payload.get('workers') or 0),
            epochs=1,
            time=float(payload.get('time_hours') or 0),
            fraction=float(payload.get('fraction') or 1.0),
            save=False,
            val=False,
            plots=False,
            cache=False,
            verbose=False,
            patience=0,
        )
        result['ok'] = True
        result['exit_code'] = 0
    except Exception as e:
        text = f'{e}\n{traceback.format_exc()}'
        result['error'] = text
        result['failure_kind'] = _failure_kind(text)
        _stderr(f'batch_probe: failed batch={payload.get("batch")} error={e}')
    finally:
        save_json_file(output_path, result)
        remove_path_silent(save_dir)

    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
