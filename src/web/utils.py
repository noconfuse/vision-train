import os
import torch

# 项目根目录: src/web/utils.py -> src/web -> src -> root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_device():
    try:
        return '0' if torch.cuda.is_available() else 'cpu'
    except Exception:
        return 'cpu'
