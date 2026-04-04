"""
员工接口 - 认证测试
===================
测试 Bearer Token 认证机制的各种场景。
"""
import pytest
import requests


class TestEmployeeAuth:
    """员工 Bearer Token 认证"""

    def test_valid_token_can_access(self, api_url, user1):
        """有效 Token 应能正常访问 API"""
        resp = requests.get(f"{api_url}/projects", headers={"Authorization": f"Bearer {user1['key']}"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    def test_missing_token_returns_401(self, api_url):
        """缺少 Authorization header 应返回 401"""
        resp = requests.get(f"{api_url}/projects")
        assert resp.status_code == 401

    def test_invalid_token_returns_error(self, api_url):
        """无效的 Token 应返回错误"""
        resp = requests.get(f"{api_url}/projects", headers={"Authorization": "Bearer sk-this-key-does-not-exist"})
        assert resp.status_code in (401, 403)

    def test_malformed_auth_header_returns_401(self, api_url):
        """格式错误的 Authorization header（无 Bearer 前缀）应返回 401"""
        resp = requests.get(f"{api_url}/projects", headers={"Authorization": "Token some-random-value"})
        assert resp.status_code == 401

    def test_disabled_account_returns_403(self, api_url, disabled_user):
        """被禁用账号的 Token 应返回 403"""
        resp = requests.get(f"{api_url}/projects", headers={"Authorization": f"Bearer {disabled_user['key']}"})
        assert resp.status_code == 403

    def test_empty_bearer_token_returns_error(self, api_url):
        """空的 Bearer Token 应返回错误"""
        resp = requests.get(f"{api_url}/projects", headers={"Authorization": "Bearer "})
        assert resp.status_code in (401, 403)
