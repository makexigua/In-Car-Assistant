from typing import Text, Optional, Callable
from utils import logger


def _load_dm_module(name: Text):
    """
    懒加载 DM 模块。
    这样即使某个可选依赖（如音乐/MCP）未安装，也不会影响服务启动。
    """
    if name == "weather":
        from dm import weather
        return weather
    if name == "maps":
        from dm import maps
        return maps
    if name == "music":
        from dm import music
        return music
    return None

class DMFactory:
    """
    build dm instance by name.
    """

    @staticmethod
    def get(name: Text):
        try:
            module = _load_dm_module(name)
            if module:
                return module.process
            return None
        except Exception as err:
            logger.error(f"load dm module failed, name={name}, err={err}")
            return None
