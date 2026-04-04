"""
管理员接口 - 认证与权限测试
==============================
测试管理员后台的认证机制：
- 管理员登录
- 非管理员不能访问管理端点
- Cookie 会话验证
"""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from conftest import _cookie_header


class TestAdminLogin:
    """POST /admin/login"""

    def test_admin_login_success(self, client, admin_user):
        """管理员使用正确的 key 应能登录"""
        resp = client.post(
            "/admin/login",
            data={"private_key": admin_user["key"]},
        )
        assert resp.status_code == 303
        assert "/admin/dashboard" in resp.headers.get("location", "")

    def test_non_admin_login_rejected(self, client, user1):
        """普通员工不能登录管理后台"""
        resp = client.post(
            "/admin/login",
            data={"private_key": user1["key"]},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert "不是系统管理员" in resp.text or "error" in resp.text.lower()

    def test_invalid_key_login_rejected(self, client):
        """无效 key 不能登录管理后台"""
        resp = client.post(
            "/admin/login",
            data={"private_key": "sk-invalid-admin-key"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert "无效" in resp.text


class TestAdminPermissionGuard:
    """验证管理员端点的权限控制：非管理员应被拒绝"""

    def _admin_headers(self, admin_user):
        cookies = {"emp_id": admin_user["emp_id"], "private_key": admin_user["key"], "admin_logged_in": "true"}
        return {"Cookie": _cookie_header(cookies)}

    def _user_headers(self, user1):
        cookies = {"emp_id": user1["emp_id"], "private_key": user1["key"], "admin_logged_in": "true"}
        return {"Cookie": _cookie_header(cookies)}

    def test_admin_can_access_dashboard(self, client, admin_user):
        """管理员应能访问管理后台"""
        resp = client.get("/admin/dashboard", headers=self._admin_headers(admin_user), follow_redirects=True)
        assert resp.status_code == 200

    def test_non_admin_cannot_access_dashboard(self, client, user1):
        """普通员工即使伪造 admin_logged_in cookie 也不能访问管理后台"""
        resp = client.get("/admin/dashboard", headers=self._user_headers(user1))
        assert resp.status_code == 303
        assert "/admin/login" in resp.headers.get("location", "")

    def test_non_admin_cannot_regenerate_key(self, client, user1):
        """普通员工不能调用重新生成 key 的管理接口"""
        resp = client.post(
            f"/admin/users/{user1['emp_id']}/regenerate-key",
            headers=self._user_headers(user1),
        )
        assert resp.status_code in (401, 403)

    def test_non_admin_cannot_change_user_status(self, client, user1):
        """普通员工不能调用禁用/启用用户的管理接口"""
        resp = client.post(
            f"/admin/users/{user1['emp_id']}/status",
            headers={**self._user_headers(user1), "Content-Type": "application/json"},
            content='{"status": "disabled"}',
        )
        assert resp.status_code in (401, 403)

    def test_no_cookie_cannot_access_admin(self, client):
        """没有任何 cookie 不能访问管理后台"""
        # 清除 TestClient 中残留的 cookie（来自之前的登录测试）
        client.cookies.clear()
        resp = client.get("/admin/dashboard")
        assert resp.status_code == 303
