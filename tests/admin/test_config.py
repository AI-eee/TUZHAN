"""
管理员接口 - 系统配置测试
============================
测试管理员修改系统配置的能力。
"""
import pytest
import requests


class TestLLMKeyConfig:
    """POST /admin/config/llm-key"""

    def test_update_llm_key_success(self, base_url, admin_session):
        """管理员应能更新 LLM API Key"""
        resp = admin_session.post(f"{base_url}/admin/config/llm-key",
                                  json={"llm_api_key": "sk-new-test-llm-api-key-12345"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    def test_non_admin_cannot_update_llm_key(self, base_url, user1):
        """普通员工不能更新 LLM API Key"""
        s = requests.Session()
        s.cookies.set("emp_id", user1["emp_id"])
        s.cookies.set("private_key", user1["key"])
        resp = s.post(f"{base_url}/admin/config/llm-key", json={"llm_api_key": "sk-hacker-key"})
        assert resp.status_code in (401, 403)

    def test_no_auth_cannot_update_llm_key(self, base_url):
        """未认证不能更新 LLM API Key"""
        resp = requests.post(f"{base_url}/admin/config/llm-key", json={"llm_api_key": "sk-anonymous-key"})
        assert resp.status_code in (401, 403)
