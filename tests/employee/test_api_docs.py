"""
员工接口 - API 文档页面测试
============================
测试 /api 文档端点的 HTML 和 Markdown 两种输出格式。
"""
import pytest


class TestAPIDocs:
    """GET /api"""

    def test_api_docs_html(self, client):
        """访问 /api 应返回 HTML 文档页面"""
        resp = client.get("/api")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")

    def test_api_docs_markdown_format(self, client):
        """带 format=markdown 参数应返回 Markdown 纯文本"""
        resp = client.get("/api?format=markdown")
        assert resp.status_code == 200
        content_type = resp.headers.get("content-type", "")
        assert "markdown" in content_type or "text/" in content_type

    def test_api_docs_md_format_alias(self, client):
        """format=md 也应返回 Markdown"""
        resp = client.get("/api?format=md")
        assert resp.status_code == 200
