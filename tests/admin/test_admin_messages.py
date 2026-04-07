"""
管理员后台 - 邮件分页接口测试
============================
覆盖：/api/admin/messages 的鉴权、分页参数、返回结构。
"""
import requests


class TestAdminMessagesEndpoint:
    def test_unauthenticated_returns_401(self, base_url):
        r = requests.get(f"{base_url}/api/admin/messages")
        assert r.status_code == 401

    def test_non_admin_returns_401(self, base_url, user1):
        # 普通用户的 cookie 没有 admin_logged_in 标记
        s = requests.Session()
        s.post(f"{base_url}/login", data={"private_key": user1["key"]}, allow_redirects=False)
        r = s.get(f"{base_url}/api/admin/messages")
        assert r.status_code == 401

    def test_admin_can_list_messages(self, base_url, admin_session):
        r = admin_session.get(f"{base_url}/api/admin/messages")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "success"
        d = body["data"]
        assert "messages" in d and isinstance(d["messages"], list)
        assert "total_count" in d
        assert d["page"] == 1
        assert d["limit"] == 50

    def test_admin_pagination(self, base_url, admin_session):
        r = admin_session.get(f"{base_url}/api/admin/messages?page=2&limit=5")
        assert r.status_code == 200
        d = r.json()["data"]
        assert d["page"] == 2
        assert d["limit"] == 5

    def test_invalid_limit_rejected(self, base_url, admin_session):
        r = admin_session.get(f"{base_url}/api/admin/messages?limit=999")
        assert r.status_code == 422
