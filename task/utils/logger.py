# File: logger.py

"""
For example:
    import logger
    logger.session.trace_id = 'test123'
    logger.info("Test info.")
    logger.error("Error happened!")
"""


import logging
import os
import sys
from logging import LoggerAdapter


__all__ = []

# 从环境变量读取日志级别，默认 INFO。
levelname = os.environ.get('LOG_LEVEL', "INFO")

# 统一维护日志级别和导出的方法名，避免散落硬编码。
_LEVEL_SET = {"DEBUG": 10, "INFO": 20, "WARN": 30, "ERROR": 40}
_LOGGING_METHOD = ["info", "warning", "error", "debug"]


class _Formatter(logging.Formatter):
    def format(self, record):
        # 这里按“时间 + 级别 + 进程 + 文件行号 + 消息”统一拼日志头，方便排障定位。
        msg = "%(message)s"
        pattern = "%(asctime)s.%(msecs)03d %(levelname)s [pid-%(process)d] @%(filename)s:%(lineno)d"
        fmt = pattern + " " + msg
        if hasattr(self, "_style"):
            self._style._fmt = fmt
        self._fmt = fmt
        return super(_Formatter, self).format(record)


class _SesssionLoggerAdapter(LoggerAdapter):

    def process(self, msg, kwargs):
        # 如果有会话 trace_id，就自动打到每条日志前面，方便串联一次请求。
        if 'session' not in self.extra or self.extra['session'] is None:
            return msg, kwargs
        session = self.extra['session']
        if hasattr(session, 'trace_id'):
            msg = '{} {}'.format(session.trace_id, msg)
        if 'extra' not in kwargs:
            kwargs["extra"] = self.extra
        else:
            kwargs['extra'].update(self.extra)
        return super().process(msg, kwargs)


def Singleton(cls):
    # 简单单例装饰器：确保 Session 在进程内只有一个实例。
    _instance = {}

    def _singleton(*args, **kargs):
        if cls not in _instance:
            _instance[cls] = cls(*args, **kargs)
        return _instance[cls]

    return _singleton


@Singleton
class Session():
    def __init__(self):
        super().__init__()

    @property
    def trace_id(self):
        # trace_id 由业务侧在每次请求入口写入，用于日志链路追踪。
        return self._trace_id

    @trace_id.setter
    def trace_id(self, trace_id):
        self._trace_id = trace_id


def _getlogger():
    # 统一构建 logger：只输出到 stdout，关闭向上冒泡，避免重复打印。
    package_name = "http_serving"
    logger = logging.getLogger(package_name)
    logger.propagate = False
    logger.setLevel(_LEVEL_SET.get(levelname))
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_Formatter(datefmt="%Y-%m-%d %H:%M:%S"))
    logger.addHandler(handler)
    return logger


# Logger hander callback
session = Session()


# Logger instance
_logger = _getlogger()
_logger = _SesssionLoggerAdapter(_logger, {'session': session})


# Export logger functions
# 把适配器方法直接暴露成模块级函数，业务侧可直接 logger.info(...) 调用。
for func in _LOGGING_METHOD:
    locals()[func] = getattr(_logger, func)
    __all__.append(func)
