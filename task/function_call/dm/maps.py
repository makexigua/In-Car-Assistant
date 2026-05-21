import json
from pathlib import Path
from datetime import datetime
from task.client.nlg import request_nlg
from task.mcp_core.mcp_client import MCPClient


mcp_client = MCPClient()
AMP_SERVER_PATH = str((Path(__file__).resolve().parents[2] / "mcp_core" / "amp_server.py"))


async def process(func_name, query, slots):

    if func_name not in ["Go_POI"]:
        return

    # 调用MCP接口
    slots["date"] = datetime.now().strftime("%Y-%m-%d")
    
    formated_slots = {}
    keyword = ""
    if "city" in slots:
        keyword += slots["city"]
    if "landmark" in slots:
        keyword += slots["landmark"]
    if "POI" in slots:
        keyword += slots["POI"]
    formated_slots["keywords"] = keyword
    if "city" in slots:
        formated_slots["city"] = slots["city"]


    await mcp_client.connect_to_server(AMP_SERVER_PATH)
    tool_response = await mcp_client.execute("maps_text_search", formated_slots)
    tool_response = json.loads(tool_response)
    nlg = request_nlg(query, tool_response)

    return (tool_response, nlg)

