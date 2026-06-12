"""
kb.offline.scripts — 离线文档处理脚本。

文件解析相关代码已迁移至 file_processors/ 子包:
    from kb.offline.scripts.file_processors import parse_document, ...

注意: semantic_splitter.py 在加载时会自动初始化 OpenAI 客户端,
所以本 __init__.py 不做顶层导入以避免触发不必要的连接。
"""
