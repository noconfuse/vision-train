"""这台机器现在用哪块计算设备：判定只有一处，训练和探测问的是同一件事。"""

import os


def pick_torch_device():
    """返回 torch 认的设备名：优先 CUDA，其次 Apple Silicon 的 MPS，都没有就用 CPU。"""
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda"
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
    except Exception:
        pass
    return os.environ.get("VT_DEVICE", "cpu")
