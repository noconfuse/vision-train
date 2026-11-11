"""Web 后端测试包。

测试要建任务、建数据集记录，这些读写落在 data/vision-train.db 里会污染开发机正在用的库，
所以先在本模块导入任何东西之前把库地址指到一个临时 sqlite 文件，跑完删掉。
"""

import atexit
import os
import shutil
import tempfile

_DB_DIR = tempfile.mkdtemp(prefix="vt_test_db_")
os.environ.setdefault("VISION_TRAIN_DB_URL", f"sqlite:///{os.path.join(_DB_DIR, 'test.db')}")
atexit.register(shutil.rmtree, _DB_DIR, ignore_errors=True)

from db import init_db  # noqa: E402  必须在库地址定下来之后才能导入

init_db()
