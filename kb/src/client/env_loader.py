from pathlib import Path

from dotenv import load_dotenv


def load_project_env() -> None:
    """
    优先加载项目根目录 .env，其次加载 kb 目录下 .env。
    """
    current_file = Path(__file__).resolve()
    kb_dir = current_file.parents[2]
    project_root = kb_dir.parent
    load_dotenv(project_root / ".env", override=False)
    load_dotenv(kb_dir / ".env", override=False)


load_project_env()
