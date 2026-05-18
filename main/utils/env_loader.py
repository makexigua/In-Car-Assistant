# -*- coding: utf-8 -*-
# --------------------------------------------
# 项目名称: LLM任务型对话Agent
# 版权所有  ©2025丁师兄大模型
# 生成时间: 2026-05
# --------------------------------------------

"""
统一加载环境变量，避免每个文件都重复写一遍 load_dotenv。
优先读取项目根目录的 .env，其次读取 main 目录下的 .env。
"""

import os
from pathlib import Path

from dotenv import load_dotenv


def load_project_env() -> None:
    """
    加载 .env 配置：
    1) 项目根目录：/xxx/车载agent/.env
    2) main 子目录：/xxx/车载agent/main/.env
    """
    current_file = Path(__file__).resolve()
    main_dir = current_file.parent.parent
    project_root = main_dir.parent

    # 先加载项目根目录 .env
    load_dotenv(project_root / ".env", override=False)
    # 再尝试加载 main 目录 .env（如果有）
    load_dotenv(main_dir / ".env", override=False)


# 模块导入时自动执行一次，减少业务代码心智负担
load_project_env()
