"""定义领域层、应用层与接口层错误类型。"""

class DomainError(ValueError):
    pass


class ApplicationError(ValueError):
    pass


class ApiError(ValueError):
    def __init__(self, message, **extra):
        """记录接口错误消息与附加响应字段。"""
        super().__init__(message)
        self.extra = extra
