import os
import torch

# 项目根目录: src/web/utils.py -> src/web -> src -> root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_device():
    try:
        if torch.cuda.is_available():
            return '0'
        if hasattr(torch, 'backends') and hasattr(torch.backends, 'mps'):
            if torch.backends.mps.is_built() and torch.backends.mps.is_available():
                return 'mps'
        return 'cpu'
    except Exception:
        return 'cpu'
