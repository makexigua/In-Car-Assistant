from pathlib import Path

from dotenv import load_dotenv


def _locate_project_root() -> Path:
    """
    从当前文件向上回溯，定位仓库根目录（包含 kb/main/task 的目录）。
    """
    current_file = Path(__file__).resolve()
    for parent in current_file.parents:
        if (parent / "kb").exists() and (parent / "main").exists() and (parent / "task").exists():
            return parent
    # 理论上不会走到这里；兜底保持可运行。
    return current_file.parents[4]


def load_project_env() -> None:
    """
    优先加载项目根目录 .env，其次加载 kb 目录下 .env。
    """
    project_root = _locate_project_root()
    kb_dir = project_root / "kb"
    load_dotenv(project_root / ".env", override=False)
    load_dotenv(kb_dir / ".env", override=False)


load_project_env()
