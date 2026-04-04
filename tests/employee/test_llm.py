"""
员工接口 - LLM 转换测试
========================
测试大模型辅助 Markdown 转换接口。
注意：实际 LLM 调用会被 mock，只测试接口层面的认证和参数校验。
"""
import pytest
from unittest.mock import patch, MagicMock


class TestLLMConvert:
    """POST /api/llm/convert"""

    def test_convert_without_token_returns_401(self, client):
        """未携带 Token 应返回 401"""
        resp = client.post(
            "/api/llm/convert",
            json={"content": "一些文本"},
        )
        assert resp.status_code == 401

    def test_convert_disabled_user_returns_403(self, client, disabled_user):
        """被禁用的员工不能调用 LLM 接口"""
        resp = client.post(
            "/api/llm/convert",
            headers={"Authorization": f"Bearer {disabled_user['key']}"},
            json={"content": "一些文本"},
        )
        assert resp.status_code == 403

    def test_convert_invalid_token_returns_error(self, client):
        """无效 Token 应返回认证错误"""
        resp = client.post(
            "/api/llm/convert",
            headers={"Authorization": "Bearer sk-invalid-key"},
            json={"content": "一些文本"},
        )
        assert resp.status_code in (401, 403)

    @patch("api.server.OpenAI")
    def test_convert_success_with_mock(self, mock_openai_cls, client, user1):
        """使用 mock LLM 验证接口正常返回"""
        # 构造 mock 返回
        mock_choice = MagicMock()
        mock_choice.message.content = "# 格式化后的 Markdown\n\n内容已整理。"
        mock_completion = MagicMock()
        mock_completion.choices = [mock_choice]
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_completion
        mock_openai_cls.return_value = mock_client

        resp = client.post(
            "/api/llm/convert",
            headers={"Authorization": f"Bearer {user1['key']}"},
            json={"content": "这是一段需要格式化的文本"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert "Markdown" in data["data"]

    def test_convert_missing_content_returns_422(self, client, user1):
        """缺少 content 字段应返回 422（参数校验失败）"""
        resp = client.post(
            "/api/llm/convert",
            headers={"Authorization": f"Bearer {user1['key']}"},
            json={},
        )
        assert resp.status_code == 422
