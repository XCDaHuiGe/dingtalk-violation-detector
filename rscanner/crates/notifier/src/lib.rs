use scanner_core::types::DetectionResult;
use serde::Serialize;
use std::collections::HashMap;

const WEBHOOK_URL: &str =
    "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=50ef613f-81a5-4bbf-9da4-02e07b9b2b36";
const SMARTSHEET_URL: &str =
    "https://qyapi.weixin.qq.com/cgi-bin/wedoc/smartsheet/webhook?key=2t3O9RxNlNiCviNwSrVnMAz8YZGOLhkYK7BmLjGeNTto39LKMPS4fOADPCCIfcjSQPFQLfIt0ZL9QYp8ftgd3Cc4j5AssHF9T2Mf19Nmhqpm";

#[derive(Serialize)]
struct WebhookPayload {
    msgtype: String,
    markdown: MarkdownContent,
}

#[derive(Serialize)]
struct MarkdownContent {
    content: String,
}

pub fn send_notification(
    username: &str,
    results: &[DetectionResult],
    webhook_url: Option<&str>,
    city: &str,
) -> Result<(), String> {
    let url = webhook_url.unwrap_or(WEBHOOK_URL);
    let hostname = get_hostname();
    let now = chrono::Local::now().format("%Y-%m-%d %H:%M:%S").to_string();
    let location = if city.is_empty() { "未知" } else { city };

    let content = if results.is_empty() {
        format!(
            "### 钉钉违规检测报告\n\
            > 人员：<font color=\"comment\">{}</font>\n\
            > 主机：<font color=\"comment\">{}</font>\n\
            > 位置：<font color=\"comment\">{}</font>\n\
            > 时间：<font color=\"comment\">{}</font>\n\
            > 状态：<font color=\"info\">✅ 无违规</font>",
            username, hostname, location, now
        )
    } else {
        let total = results.len();
        let mut type_counts: HashMap<&str, usize> = HashMap::new();
        for r in results {
            *type_counts.entry(&r.file_type).or_insert(0) += 1;
        }
        let type_summary: String = type_counts
            .iter()
            .map(|(k, v)| format!("{} <font color=\"warning\">{}</font> 个", k, v))
            .collect::<Vec<_>>()
            .join("; ");

        let mut file_list = String::new();
        let max_show = 20;
        for r in results.iter().take(max_show) {
            let display = if r.path.len() > 70 {
                format!("...{}", &r.path[r.path.len().saturating_sub(67)..])
            } else {
                r.path.clone()
            };
            file_list.push_str(&format!("> {} [{}]\n", display, r.file_type));
        }
        if results.len() > max_show {
            file_list.push_str(&format!("> + 还有 {} 项\n", results.len() - max_show));
        }

        format!(
            "### 钉钉违规检测报告\n\
            > 人员：<font color=\"comment\">{}</font>\n\
            > 主机：<font color=\"comment\">{}</font>\n\
            > 位置：<font color=\"comment\">{}</font>\n\
            > 时间：<font color=\"comment\">{}</font>\n\
            > 状态：<font color=\"warning\">⚠️ 发现违规</font>\n\
            > 总数：<font color=\"warning\">{}</font> 项\n\
            > 类型：{}\n\
            ---\n\
            {}",
            username, hostname, location, now, total, type_summary, file_list
        )
    };

    let payload = WebhookPayload {
        msgtype: "markdown".to_string(),
        markdown: MarkdownContent { content },
    };

    let mut response = ureq::post(url)
        .send_json(&payload)
        .map_err(|e| format!("HTTP 请求失败: {}", e))?;

    let body: serde_json::Value = response.body_mut().read_json()
        .map_err(|e| format!("解析响应失败: {}", e))?;

    if body["errcode"] != 0 {
        return Err(format!(
            "企业微信返回错误: {} - {}",
            body["errcode"], body["errmsg"]
        ));
    }

    Ok(())
}

#[derive(Serialize)]
struct SmartsheetPayload {
    add_records: Vec<SmartsheetRecord>,
}

#[derive(Serialize)]
struct SmartsheetRecord {
    values: SmartsheetValues,
}

#[derive(Serialize)]
struct SmartsheetValues {
    #[serde(rename = "ftk5Tx")]
    person_name: String,
    #[serde(rename = "fn8TJd")]
    time: String,
    #[serde(rename = "ffFwIh")]
    count: String,
    #[serde(rename = "f04Gwj")]
    hostname: String,
    #[serde(rename = "ftQMc5")]
    status: String,
    #[serde(rename = "fLocation")]
    location: String,
}

pub fn push_results_to_smartsheet(
    username: &str,
    results: &[DetectionResult],
    webhook_url: Option<&str>,
    city: &str,
) -> Result<(), String> {
    let url = webhook_url.unwrap_or(SMARTSHEET_URL);
    let now = chrono::Local::now().format("%Y-%m-%d %H:%M:%S").to_string();
    let status = if results.is_empty() { "无违规" } else { "有违规" };

    let payload = SmartsheetPayload {
        add_records: vec![SmartsheetRecord {
            values: SmartsheetValues {
                person_name: username.to_string(),
                time: now,
                count: results.len().to_string(),
                hostname: get_hostname(),
                status: status.to_string(),
                location: city.to_string(),
            },
        }],
    };

    let mut response = ureq::post(url)
        .send_json(&payload)
        .map_err(|e| format!("HTTP 请求失败: {}", e))?;

    let body: serde_json::Value = response.body_mut().read_json()
        .map_err(|e| format!("解析响应失败: {}", e))?;

    if body["errcode"] != 0 {
        return Err(format!(
            "智能表返回错误: {} - {}",
            body["errcode"], body["errmsg"]
        ));
    }

    Ok(())
}

fn get_hostname() -> String {
    std::env::var("COMPUTERNAME")
        .or_else(|_| std::env::var("HOSTNAME"))
        .unwrap_or_else(|_| "unknown".to_string())
}

/// 通过公共 IP 接口获取城市信息（带 5 秒超时）
pub fn get_city_from_ip() -> String {
    use std::sync::mpsc;
    use std::time::Duration;

    let (tx, rx) = mpsc::channel();
    std::thread::spawn(move || {
        let resp = ureq::get("http://ip-api.com/json/?lang=zh-CN").call();
        let result = match resp {
            Ok(mut r) => {
                let body: serde_json::Value = r
                    .body_mut()
                    .read_json()
                    .unwrap_or_default();
                if body["status"] == "success" {
                    let city = body["city"].as_str().unwrap_or("");
                    let region = body["regionName"].as_str().unwrap_or("");
                    let country = body["country"].as_str().unwrap_or("");
                    let loc = format!("{} {} {}", country, region, city);
                    let loc = loc.trim().to_string();
                    if loc.is_empty() { "未知".to_string() } else { loc }
                } else {
                    "未知".to_string()
                }
            }
            Err(_) => "未知".to_string(),
        };
        let _ = tx.send(result);
    });

    rx.recv_timeout(Duration::from_secs(5))
        .unwrap_or_else(|_| "未知（超时）".to_string())
}
