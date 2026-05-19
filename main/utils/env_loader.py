# 作用：统一从项目根目录的 .env 加载配置，避免各模块重复读取。

from pathlib import Path

from dotenv import load_dotenv


def load_project_env() -> None:

    current_file = Path(__file__).resolve()
    main_dir = current_file.parent.parent
    project_root = main_dir.parent

    # 只加载项目根目录 .env，保证配置来源唯一。
    load_dotenv(project_root / ".env", override=False)


# 模块导入时自动执行一次，减少业务代码心智负担
load_project_env()
