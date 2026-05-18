# 作用：统一从项目根目录的 .env 加载配置，避免各模块重复读取。

"""
统一加载环境变量，避免每个文件都重复写一遍 `load_dotenv`。
这里明确只读取项目根目录的 `.env`，不再读取 `main/.env`。
"""

from pathlib import Path

from dotenv import load_dotenv


def load_project_env() -> None:
    """
    加载项目根目录 .env：
    `/xxx/车载agent/.env`
    """
    current_file = Path(__file__).resolve()
    main_dir = current_file.parent.parent
    project_root = main_dir.parent

    # 只加载项目根目录 .env，保证配置来源唯一。
    load_dotenv(project_root / ".env", override=False)


# 模块导入时自动执行一次，减少业务代码心智负担
load_project_env()
