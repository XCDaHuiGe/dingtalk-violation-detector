import json
import socket
from datetime import datetime
from typing import Dict

try:
    import requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False
    import urllib.request
    import urllib.error

SMARTSHEET_URL = "https://qyapi.weixin.qq.com/cgi-bin/wedoc/smartsheet/webhook?key=2t3O9RxNlNiCviNwSrVnMAzY8ZGOLhkYK7BmLjGeNTto39LKMPS4fOADPCCIfcjSQPFQLfIt0ZL9QYp8ftgd3Cc4j5AssHF9T2Mf19Nmhqpm"


def _post_json(url: str, payload: dict) -> dict:
    if _HAS_REQUESTS:
        resp = requests.post(url, json=payload, timeout=30)
        return resp.json()
    req = urllib.request.Request(
        url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def push_results_to_smartsheet(
    username: str,
    results: list,
    webhook_url: str = None,
) -> Dict:
    """
    推送本次检测摘要到企业微信智能表（一条记录）
    表结构 — 全部字段均为文本:
      ftk5Tx → 检测人
      fn8TJd → 检测时间
      ffFwIh → 违规数量
      f04Gwj → 机器名
      ftQMc5 → 检测结果
    """
    url = webhook_url or SMARTSHEET_URL
    if not url:
        return {"success": False, "message": "\u672a\u914d\u7f6e\u667a\u80fd\u8868 Webhook"}

    hostname = socket.gethostname()
    total = len(results)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    payload = {
        "add_records": [
            {
                "values": {
                    "ftk5Tx": [{"type": "text", "text": username}],
                    "fn8TJd": [{"type": "text", "text": now_str}],
                    "ffFwIh": [{"type": "text", "text": str(total)}],
                    "f04Gwj": [{"type": "text", "text": hostname}],
                    "ftQMc5": [{"type": "text", "text": "\u6709\u8fdd\u89c4" if total > 0 else "\u65e0\u8fdd\u89c4"}],
                }
            }
        ]
    }

    try:
        resp_data = _post_json(url, payload)
        if resp_data.get("errcode") == 0:
            return {"success": True, "message": f"\u5df2\u63a8\u9001\u5230\u667a\u80fd\u8868 {total}\u4e2a\u8fdd\u89c4"}
        return {"success": False, "message": f"\u63a8\u9001\u5931\u8d25: {resp_data.get('errmsg', str(resp_data))}"}
    except Exception as e:
        return {"success": False, "message": f"\u63a8\u9001\u5f02\u5e38: {e}"}
