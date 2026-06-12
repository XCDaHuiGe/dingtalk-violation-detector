import os
import time
import json
import socket
from datetime import datetime
from typing import List, Dict

try:
    import requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False
    import urllib.request
    import urllib.error


# 企业微信 Webhook（写死）
WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=50ef613f-81a5-4bbf-9da4-02e07b9b2b36"


def get_hostname() -> str:
    return socket.gethostname()


def build_markdown_content(username: str, hostname: str,
                           total_count: int, results: List, source_name: str = "") -> str:
    """构建 Markdown 报警内容"""

    # 类型汇总
    type_summary: Dict[str, int] = {}
    for r in results:
        t = getattr(r, "file_type", "未知")
        type_summary[t] = type_summary.get(t, 0) + 1

    type_lines = "\n".join(f"- **{t}**: {c} 个" for t, c in type_summary.items())

    # 文件列表（最多 20 条）
    file_lines_parts = []
    for r in results[:20]:
        fn = getattr(r, "filename", "未知")
        p = getattr(r, "path", "未知")
        full_path = os.path.join(p, fn)
        if len(full_path) > 70:
            full_path = full_path[:67] + "..."
        file_lines_parts.append(f"> - `{full_path}`")

    more = ""
    if total_count > 20:
        more = f"\n> ...还有 {total_count - 20} 个文件未显示"

    content = (
        f"## <font color=\"warning\">违规软件检测报警</font>\n"
        f"\n"
        f"**检测信息**\n"
        f"- 姓名: <font color=\"comment\">{username}</font>\n"
        f"- 机器名: <font color=\"comment\">{hostname}</font>\n"
        f"- 检测时间: <font color=\"comment\">{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</font>\n"
        f"- 来源: <font color=\"comment\">{source_name}</font>\n"
        f"\n"
        f"**检测结果**: 发现钉钉相关文件 <font color=\"warning\">**{total_count}**</font> 个\n"
        f"\n"
        f"**文件类型分布**\n"
        f"{type_lines}\n"
        f"\n"
        f"**文件列表**\n"
        f"{chr(10).join(file_lines_parts)}{more}"
    )
    return content


def send_notification(username: str, results: List, webhook_url: str = None,
                      source_name: str = "") -> Dict:
    """发送企业微信通知"""
    url = webhook_url or WEBHOOK_URL
    if not url:
        return {"success": False, "message": "未配置 Webhook URL"}

    total = len(results)
    hostname = get_hostname()

    if total == 0:
        # 发送无违规通知
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "content": (
                    f"## <font color=\"info\">违规软件检测结果</font>\n"
                    f"\n"
                    f"**检测信息**\n"
                    f"- 姓名: {username}\n"
                    f"- 机器名: {hostname}\n"
                    f"- 检测时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"\n"
                    f"**检测结果**: 未发现钉钉相关文件 ✅"
                )
            }
        }
    else:
        content = build_markdown_content(username, hostname, total, results, source_name)
        payload = {"msgtype": "markdown", "markdown": {"content": content}}

    try:
        if _HAS_REQUESTS:
            response = requests.post(url, json=payload, timeout=10)
            resp_data = response.json()
        else:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))

        if resp_data.get("errcode") == 0:
            return {"success": True, "message": "发送成功"}
        return {"success": False, "message": f"发送失败: {resp_data.get('errmsg', '未知')}"}
    except Exception as e:
        return {"success": False, "message": f"网络错误: {e}"}
