"""跨上下文共享的视觉能力契约（纯数据，无 IO）。"""

from protocols.capabilities.dataset_capabilities import *  # noqa: F401,F403
from protocols.capabilities.model_capabilities import *  # noqa: F401,F403
from protocols.capabilities.export_profile import *  # noqa: F401,F403
from protocols.capabilities.result_profile import *  # noqa: F401,F403
from protocols.capabilities.training_profile import *  # noqa: F401,F403
from protocols.capabilities.snapshot import *  # noqa: F401,F403
