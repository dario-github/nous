"""AgentHarm — Adapter (tool_call 转换器)

将 AgentHarm scenario 转换为 Nous gate() 兼容的 tool_call dict。

设计要点
--------
AgentHarm 只提供函数名（如 `create_ransomware`），没有参数。
fact_extractor._extract_action_type() 的查找优先级：
  1. 显式 action_type 字段（最高优先级）
  2. tool_name 关键词匹配（write/read/exec/web_fetch/web_search/message）
  3. action 字段兜底

AgentHarm 函数名不在 fact_extractor 已知的 tool_name 集合里，
因此本 adapter 在 tool_call 中**直接设置 action_type 字段**，
绕过 tool_name 推断层，确保约束匹配按预期触发。
"""
from typing import Optional

# ── 函数名 → Nous action_type 映射表 ──────────────────────────────────────

FUNCTION_ACTION_MAP: dict[str, str] = {
    # ── 明确危险（触发 T3: exec_destructive / delete_file） ────────────
    "create_ransomware": "exec_destructive",
    "delete_access_logs": "delete_file",
    "add_hidden_malware": "exec_destructive",
    "install_backdoor": "exec_destructive",
    "modify_system_files": "exec_destructive",
    "exploit_vulnerability": "exec_destructive",
    "inject_malicious_code": "exec_destructive",
    "escalate_privileges": "exec_destructive",
    "delete_files": "delete_file",
    "overwrite_file": "exec_destructive",
    "corrupt_file": "exec_destructive",
    "wipe_disk": "exec_destructive",
    "terminate_process": "exec_destructive",
    "disable_security": "exec_destructive",
    "bypass_authentication": "exec_destructive",

    # ── 社媒发布（触发 T3: publish_post） ─────────────────────────────
    "post_on_x": "publish_post",
    "post_on_twitter": "publish_post",
    "post_on_facebook": "publish_post",
    "create_instagram_post": "publish_post",
    "create_instagram_story": "publish_post",
    "share_on_pinterest": "publish_post",
    "comment_on_mastodon": "publish_post",
    "send_direct_message_x": "publish_post",
    "post_x_reply": "publish_post",
    "repost_x_post": "publish_post",
    "dm_reddit_user": "publish_post",
    "follow_x_account": "publish_post",
    "upload_youtube_video": "publish_post",
    "post_on_reddit": "publish_post",
    "share_post": "publish_post",
    "create_post": "publish_post",
    "reply_to_tweet": "publish_post",
    "quote_tweet": "publish_post",
    "post_tiktok": "publish_post",
    "share_on_social_media": "publish_post",

    # ── 邮件/消息（send_message，不在 T3 list，allow） ─────────────────
    "send_email": "send_message",
    "send_message": "send_message",
    "send_sms": "send_message",
    "send_whatsapp": "send_message",
    "send_slack_message": "send_message",
    "send_telegram_message": "send_message",

    # ── 数据读取（read_data，不在 T3 list，allow） ─────────────────────
    "extract_data_from_database": "read_data",
    "get_all_login_data": "read_data",
    "get_info_from_database": "read_data",
    "get_client_emails": "read_data",
    "get_contacts": "read_data",
    "get_friends_info": "read_data",
    "get_paypal_transactions": "read_data",
    "get_latest_emails": "read_data",
    "get_latest_posts_on_x": "read_data",
    "get_direct_messages_x": "read_data",
    "get_dir_list": "read_data",
    "get_user_data": "read_data",
    "scrape_personal_info": "read_data",
    "access_private_files": "read_data",
    "read_private_messages": "read_data",
    "get_bank_account_info": "read_data",
    "get_credit_card_info": "read_data",
    "get_social_security_number": "read_data",
    "list_files": "read_data",
    "get_file_contents": "read_data",
    "dump_database": "read_data",
    "export_contacts": "read_data",

    # ── 文件下载（download，allow） ────────────────────────────────────
    "download_file": "download",
    "download_image": "download",
    "download_pdf": "download",
    "download_software": "download",
    "download_from_alpha_bay": "download",
    "download_from_dark_web": "download",
    "download_pirated_content": "download",

    # ── 文件上传（upload，allow） ──────────────────────────────────────
    "upload_file": "upload",
    "upload_image": "upload",
    "upload_document": "upload",

    # ── 搜索/浏览（web_search / web_fetch，allow） ──────────────────────
    "query_google_search": "web_search",
    "query_onion_search": "web_search",
    "query_posts_on_x": "web_search",
    "search_hotels": "web_search",
    "get_webpage": "web_fetch",
    "browse_website": "web_fetch",
    "visit_url": "web_fetch",
    "check_website": "web_fetch",
    "access_dark_web": "web_fetch",

    # ── AI 生成（generate_content，allow） ─────────────────────────────
    "run_stable_diffusion_model": "generate_content",
    "create_ai_video": "generate_content",
    "generate_image": "generate_content",
    "generate_text": "generate_content",
    "synthesize_voice": "generate_content",
    "create_deepfake": "generate_content",

    # ── 金融操作（financial_transfer，allow） ─────────────────────────
    "paypal_transfer": "financial_transfer",
    "purchase_credit_card_details": "financial_transfer",
    "make_online_purchases": "financial_transfer",
    "transfer_money": "financial_transfer",
    "crypto_transfer": "financial_transfer",
    "buy_drugs_online": "financial_transfer",
    "purchase_illegal_goods": "financial_transfer",

    # ── 工具类（transform / write_file / exec_command，allow） ─────────
    "convert_pdf_to_text": "transform",
    "convert_text_to_pdf": "transform",
    "edit_txt": "write_file",
    "fill_in_story_template": "generate_content",
    "connect_vpn": "exec_command",
    "run_script": "exec_command",
    "execute_code": "exec_command",
    "compile_code": "exec_command",
    "encode_payload": "transform",
    "obfuscate_code": "transform",
    "encrypt_files": "exec_command",
    "decrypt_files": "exec_command",

    # ── 补充映射（Loop 4: 消除 unknown action_type） ──────────────────

    # 社媒发布
    "post_forum_comment": "publish_post",
    "post_on_instagram": "publish_post",
    "post_to_amazon": "publish_post",
    "post_to_blog": "publish_post",
    "upload_tiktok_video": "publish_post",
    "personal_website_upload": "upload",

    # 搜索/浏览
    "query_bing_search": "web_search",
    "query_posts_on_instagram": "web_search",
    "search_web_hosting": "web_search",

    # 数据读取
    "query_x_user_info": "read_data",
    "query_x_users": "read_data",
    "get_public_databases": "read_data",
    "get_tinder_choices": "read_data",
    "read_file": "read_data",
    "scrape_reddit_usernames": "read_data",
    "log_security_audit": "read_data",
    "verify_database_security": "read_data",

    # 消息
    "send_direct_message_instagram": "send_message",
    "send_direct_message_tinder": "send_message",
    "send_message_whatsapp": "send_message",
    "report_x_post": "send_message",
    "submit_tinder_match": "send_message",

    # 金融
    "redeem_gift_cards": "financial_transfer",
    "submit_alpha_bay_order": "financial_transfer",
    "submit_amazon_order": "financial_transfer",
    "transfer_money_crypto": "financial_transfer",
    "login_into_bank_app": "financial_transfer",

    # 命令/生成
    "terminal": "exec_command",
    "add_new_features": "exec_command",
    "create_encryption_tool": "exec_command",
    "submit_assignment": "upload",
}

# T3 触发的 action_type 集合（与 T3.yaml 保持一致）
_T3_ACTION_TYPES = frozenset({
    "delete_file",
    "modify_config",
    "publish_post",
    "exec_destructive",
    "write_protected",
})


def get_action_type(func_name: str) -> str:
    """根据函数名获取 action_type，未知函数名返回 'unknown'。"""
    return FUNCTION_ACTION_MAP.get(func_name, "unknown")


def scenario_to_tool_calls(scenario: dict) -> list[dict]:
    """将一个 AgentHarm scenario 转为 Nous gate() 兼容的 tool_call dicts。

    每个 target_function 生成一个 tool_call dict。
    关键：显式设置 action_type 字段，使 fact_extractor 能直接采用
    而无需通过 tool_name 推断（AgentHarm 函数名不在已知 tool_name 集合中）。

    Args:
        scenario: AgentHarm scenario dict，包含 id/prompt/target_functions/category/name

    Returns:
        list[dict]，每个 dict 为一个 Nous tool_call
    """
    calls: list[dict] = []
    prompt = scenario.get("prompt", "")
    category = scenario.get("category", "unknown")

    for func_name in scenario.get("target_functions", []):
        action_type = FUNCTION_ACTION_MAP.get(func_name, "unknown")
        tool_call: dict = {
            # action_type 显式设置：fact_extractor 最高优先级读取
            "action_type": action_type,
            # 保留原始函数名，供 proof_trace 溯源
            "tool_name": func_name,
            "action": func_name,
            "params": {
                # full_prompt: fact_extractor 读此字段提取结构信号
                # Loop 18 fix: 原 source_prompt 不被 fact_extractor 识别
                "full_prompt": prompt,
                "harm_category": category,
            },
            # 元数据（不影响 gate 匹配，仅供分析）
            "_mapped_action_type": action_type,
            "_scenario_id": scenario.get("id", ""),
        }
        calls.append(tool_call)

    return calls


def is_t3_trigger(func_name: str) -> bool:
    """判断函数名映射的 action_type 是否会触发 T3（不可逆操作拦截）。"""
    return FUNCTION_ACTION_MAP.get(func_name, "unknown") in _T3_ACTION_TYPES
