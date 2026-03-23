"""Tests for _normalize_tool_action and its integration with _extract_action_type."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from nous.fact_extractor import _normalize_tool_action, _extract_action_type, extract_facts


class TestNormalizeToolAction:
    """Unit tests for _normalize_tool_action mapping."""

    def test_standard_names_unchanged(self):
        """Standard Datalog tool names should pass through unchanged."""
        standard = [
            "send_email", "send_slack_message", "post_to_forum", "post_tweet",
            "create_github_issue", "make_http_request", "upload_file", "call_api",
            "create_webhook", "send_sms", "git_push", "read_file", "read_env_vars",
            "publish_post",  # known interceptor action type
        ]
        for name in standard:
            assert _normalize_tool_action(name) == name, f"{name} should be unchanged"

    def test_send_external_variants(self):
        """Messaging variants should map to send_email or send_slack_message."""
        assert _normalize_tool_action("broadcast_message") == "send_email"
        assert _normalize_tool_action("write_message") == "send_email"
        assert _normalize_tool_action("notify") == "send_email"
        assert _normalize_tool_action("send_notification") == "send_email"
        assert _normalize_tool_action("log_to_channel") == "send_slack_message"
        assert _normalize_tool_action("direct_message") == "send_email"

    def test_post_public_variants(self):
        """Publishing variants should map to post_to_forum."""
        assert _normalize_tool_action("publish") == "post_to_forum"
        assert _normalize_tool_action("publish_page") == "post_to_forum"
        # publish_post is a known action type (interceptor T3), passes through
        assert _normalize_tool_action("publish_post") == "publish_post"
        assert _normalize_tool_action("create_post") == "post_to_forum"

    def test_network_request_variants(self):
        """Network request variants should map to make_http_request or call_api."""
        assert _normalize_tool_action("fetch_url") == "make_http_request"
        assert _normalize_tool_action("dns_update") == "call_api"
        assert _normalize_tool_action("curl") == "make_http_request"

    def test_file_transfer_variants(self):
        """File transfer variants should map to upload_file."""
        assert _normalize_tool_action("sync_file") == "upload_file"
        assert _normalize_tool_action("transfer_file") == "upload_file"
        assert _normalize_tool_action("s3_upload") == "upload_file"

    def test_substring_matching(self):
        """Prefixed/suffixed variants should match via substring."""
        assert _normalize_tool_action("slack_broadcast_message") == "send_email"
        assert _normalize_tool_action("auto_publish_page") == "post_to_forum"
        assert _normalize_tool_action("my_fetch_url_helper") == "make_http_request"

    def test_case_insensitive(self):
        """Matching should be case-insensitive."""
        assert _normalize_tool_action("Broadcast_Message") == "send_email"
        assert _normalize_tool_action("PUBLISH") == "post_to_forum"

    def test_unknown_passes_through(self):
        """Unrecognized names should pass through unchanged."""
        assert _normalize_tool_action("custom_tool_xyz") == "custom_tool_xyz"
        assert _normalize_tool_action("") == ""

    def test_empty_and_none(self):
        """Edge cases."""
        assert _normalize_tool_action("") == ""
        assert _normalize_tool_action(None) is None


class TestExtractActionTypeIntegration:
    """Integration: _extract_action_type should use normalization."""

    def test_explicit_action_type_normalized(self):
        """Explicit action_type field should be normalized."""
        tc = {"action_type": "broadcast_message"}
        assert _extract_action_type(tc) == "send_email"

    def test_explicit_standard_action_type_unchanged(self):
        """Standard explicit action_type should pass through."""
        tc = {"action_type": "send_email"}
        assert _extract_action_type(tc) == "send_email"

    def test_fallback_tool_name_normalized(self):
        """Fallback via tool_name should normalize non-standard names."""
        tc = {"tool_name": "publish"}
        assert _extract_action_type(tc) == "post_to_forum"

    def test_fallback_action_normalized(self):
        """Fallback via action field should normalize."""
        tc = {"action": "notify"}
        assert _extract_action_type(tc) == "send_email"

    def test_standard_mappings_still_work(self):
        """Existing standard mappings (write/read/exec) should still work."""
        assert _extract_action_type({"tool_name": "write"}) == "write_file"
        assert _extract_action_type({"tool_name": "read"}) == "read_file"
        assert _extract_action_type({"tool_name": "web_fetch"}) == "open_url"


class TestExtractFactsIntegration:
    """Integration: extract_facts should produce normalized action_type."""

    def test_broadcast_message_scenario(self):
        """Scenario using broadcast_message should get send_email action_type."""
        tc = {
            "tool_name": "broadcast_message",
            "action_type": "broadcast_message",
            "params": {"content": "test message", "full_prompt": "send this out"},
        }
        facts = extract_facts(tc)
        assert facts["action_type"] == "send_email"

    def test_publish_scenario(self):
        """Scenario using publish should get post_to_forum action_type."""
        tc = {
            "tool_name": "publish",
            "action_type": "publish",
            "params": {"content": "blog post", "full_prompt": "publish this"},
        }
        facts = extract_facts(tc)
        assert facts["action_type"] == "post_to_forum"
