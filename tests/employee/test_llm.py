"""
员工接口 - LLM 转换测试
========================
测试大模型辅助 Markdown 转换接口的认证和参数校验。
注意：test_convert_success 会真实调用 LLM，需要服务器配置了有效的 LLM_API_KEY。
"""
import pytest
import requests


def _auth(key):
    return {"Authorization": f"Bearer {key}"}


class TestLLMConvert:
    """POST /api/llm/convert"""

    def test_convert_without_token_returns_401(self, api_url):
        """未携带 Token 应返回 401"""
        resp = requests.post(f"{api_url}/llm/convert", json={"content": "一些文本"})
        assert resp.status_code == 401

    def test_convert_disabled_user_returns_403(self, api_url, disabled_user):
        """被禁用的员工不能调用 LLM 接口"""
        resp = requests.post(f"{api_url}/llm/convert", headers=_auth(disabled_user["key"]),
                             json={"content": "一些文本"})
        assert resp.status_code == 403

    def test_convert_invalid_token_returns_error(self, api_url):
        """无效 Token 应返回认证错误"""
        resp = requests.post(f"{api_url}/llm/convert", headers=_auth("sk-invalid-key"),
                             json={"content": "一些文本"})
        assert resp.status_code in (401, 403)

    def test_convert_missing_content_returns_422(self, api_url, user1):
        """缺少 content 字段应返回 422（参数校验失败）"""
        resp = requests.post(f"{api_url}/llm/convert", headers=_auth(user1["key"]), json={})
        assert resp.status_code == 422
