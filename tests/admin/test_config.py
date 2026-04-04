"""
管理员接口 - 系统配置测试
============================
测试管理员修改系统配置的能力：
- 更新 LLM API Key
"""
import pytest
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from conftest import _cookie_header


def _admin_headers(admin_user):
    cookies = {"emp_id": admin_user["emp_id"], "private_key": admin_user["key"]}
    return {"Cookie": _cookie_header(cookies)}


class TestLLMKeyConfig:
    """POST /admin/config/llm-key"""

    def test_update_llm_key_success(self, client, admin_user):
        """管理员应能更新 LLM API Key"""
        new_key = "sk-new-test-llm-api-key-12345"
        resp = client.post(
            "/admin/config/llm-key",
            headers=_admin_headers(admin_user),
            json={"llm_api_key": new_key},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"
        assert os.environ.get("LLM_API_KEY") == new_key

    def test_non_admin_cannot_update_llm_key(self, client, user1):
        """普通员工不能更新 LLM API Key"""
        cookies = {"emp_id": user1["emp_id"], "private_key": user1["key"]}
        resp = client.post(
            "/admin/config/llm-key",
            headers={"Cookie": _cookie_header(cookies)},
            json={"llm_api_key": "sk-hacker-key"},
        )
        assert resp.status_code in (401, 403)

    def test_no_auth_cannot_update_llm_key(self, client):
        """未认证不能更新 LLM API Key"""
        client.cookies.clear()
        resp = client.post(
            "/admin/config/llm-key",
            json={"llm_api_key": "sk-anonymous-key"},
        )
        assert resp.status_code in (401, 403)
