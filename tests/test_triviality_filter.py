"""Tests for Nous — Triviality Filter (M7.3 Layer 2)"""
import pytest
from nous.triviality_filter import TrivialityConfig, is_trivial


class TestTrivialityFilter:
    """Triviality filter 核心测试。"""

    def test_read_file_is_trivial(self):
        facts = {"action_type": "read_file"}
        assert is_trivial(facts) is True

    def test_web_search_is_trivial(self):
        facts = {"action_type": "web_search"}
        assert is_trivial(facts) is True

    def test_web_fetch_is_trivial(self):
        facts = {"action_type": "web_fetch"}
        assert is_trivial(facts) is True

    def test_read_data_is_trivial(self):
        facts = {"action_type": "read_data"}
        assert is_trivial(facts) is True

    def test_download_is_trivial(self):
        facts = {"action_type": "download"}
        assert is_trivial(facts) is True

    def test_transform_is_trivial(self):
        facts = {"action_type": "transform"}
        assert is_trivial(facts) is True

    def test_write_file_is_not_trivial(self):
        facts = {"action_type": "write_file"}
        assert is_trivial(facts) is False

    def test_exec_destructive_is_not_trivial(self):
        facts = {"action_type": "exec_destructive"}
        assert is_trivial(facts) is False

    def test_publish_post_is_not_trivial(self):
        facts = {"action_type": "publish_post"}
        assert is_trivial(facts) is False

    def test_delete_file_is_not_trivial(self):
        facts = {"action_type": "delete_file"}
        assert is_trivial(facts) is False

    def test_send_message_is_not_trivial(self):
        facts = {"action_type": "send_message"}
        assert is_trivial(facts) is False

    def test_unknown_action_is_not_trivial(self):
        facts = {"action_type": "unknown"}
        assert is_trivial(facts) is False

    def test_empty_action_is_not_trivial(self):
        facts = {"action_type": ""}
        assert is_trivial(facts) is False

    def test_missing_action_type_is_not_trivial(self):
        facts = {}
        assert is_trivial(facts) is False


class TestTrivialityFilterExecCommand:
    """exec_command 只读命令匹配测试。"""

    def test_ls_is_trivial(self):
        facts = {"action_type": "exec_command", "command": "ls"}
        assert is_trivial(facts) is True

    def test_ls_with_args_is_trivial(self):
        facts = {"action_type": "exec_command", "command": "ls -la /tmp"}
        assert is_trivial(facts) is True

    def test_git_status_is_trivial(self):
        facts = {"action_type": "exec_command", "command": "git status"}
        assert is_trivial(facts) is True

    def test_git_diff_is_trivial(self):
        facts = {"action_type": "exec_command", "command": "git diff HEAD~1"}
        assert is_trivial(facts) is True

    def test_cat_is_trivial(self):
        facts = {"action_type": "exec_command", "command": "cat README.md"}
        assert is_trivial(facts) is True

    def test_rm_is_not_trivial(self):
        facts = {"action_type": "exec_command", "command": "rm -rf /tmp/data"}
        assert is_trivial(facts) is False

    def test_git_push_is_not_trivial(self):
        facts = {"action_type": "exec_command", "command": "git push origin main"}
        assert is_trivial(facts) is False

    def test_pip_install_is_not_trivial(self):
        facts = {"action_type": "exec_command", "command": "pip install malware"}
        assert is_trivial(facts) is False

    def test_empty_command_is_not_trivial(self):
        facts = {"action_type": "exec_command", "command": ""}
        assert is_trivial(facts) is False

    def test_missing_command_is_not_trivial(self):
        facts = {"action_type": "exec_command"}
        assert is_trivial(facts) is False


class TestTrivialityFilterConfig:
    """配置相关测试。"""

    def test_disabled_returns_false(self):
        config = TrivialityConfig(enabled=False)
        facts = {"action_type": "read_file"}
        assert is_trivial(facts, config) is False

    def test_custom_allow_action_types(self):
        config = TrivialityConfig(
            allow_action_types=frozenset({"custom_safe_op"})
        )
        assert is_trivial({"action_type": "custom_safe_op"}, config) is True
        assert is_trivial({"action_type": "read_file"}, config) is False

    def test_extra_predicate_works(self):
        config = TrivialityConfig(
            extra_predicates=[lambda f: f.get("special") == "safe"]
        )
        assert is_trivial({"action_type": "unknown", "special": "safe"}, config) is True
        assert is_trivial({"action_type": "unknown", "special": "danger"}, config) is False

    def test_extra_predicate_exception_is_safe(self):
        """谓词异常 → 保守处理，不视为 trivial。"""
        def bad_predicate(facts):
            raise RuntimeError("oops")

        config = TrivialityConfig(extra_predicates=[bad_predicate])
        assert is_trivial({"action_type": "unknown"}, config) is False

    def test_default_config_matches_doc(self):
        """默认配置包含预期的安全 action_type。"""
        config = TrivialityConfig()
        assert "read_file" in config.allow_action_types
        assert "web_search" in config.allow_action_types
        assert "delete_file" not in config.allow_action_types
