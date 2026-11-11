"""计算域对外抛出的错误类型。"""

from shared.kernel.errors import ApplicationError


class RemoteExecutionError(ApplicationError):
    """远端 GPU 服务器没能完成我们要求的动作。

    消息里带上主机名、退出码和服务器原始输出：远端不行就是不行，界面要看得见，
    不回退到本机跑。
    """
