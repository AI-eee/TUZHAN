"""
管理员接口 - 认证与权限测试
==============================
测试管理员后台的认证机制和权限拦截。
"""
import pytest
import requests


class TestAdminLogin:
    """POST /admin/login"""

    def test_admin_login_success(self, base_url, admin_user):
        """管理员使用正确的 key 应能登录"""
        resp = requests.post(f"{base_url}/admin/login",
                             data={"private_key": admin_user["key"]}, allow_redirects=False)
        assert resp.status_code == 303
        assert "/admin/dashboard" in resp.headers.get("location", "")

    def test_non_admin_login_rejected(self, base_url, user1):
        """普通员工不能登录管理后台"""
        resp = requests.post(f"{base_url}/admin/login", data={"private_key": user1["key"]})
        assert resp.status_code == 200
        assert "不是系统管理员" in resp.text or "error" in resp.text.lower()

    def test_invalid_key_login_rejected(self, base_url):
        """无效 key 不能登录管理后台"""
        resp = requests.post(f"{base_url}/admin/login", data={"private_key": "sk-invalid-admin-key"})
        assert resp.status_code == 200
        assert "无效" in resp.text


class TestAdminPermissionGuard:
    """验证管理员端点的权限控制：非管理员应被拒绝"""

    def test_admin_can_access_dashboard(self, base_url, admin_session):
        """管理员应能访问管理后台"""
        resp = admin_session.get(f"{base_url}/admin/dashboard")
        assert resp.status_code == 200

    def test_non_admin_cannot_access_dashboard(self, base_url, user1):
        """普通员工即使伪造 admin_logged_in cookie 也不能访问管理后台"""
        s = requests.Session()
        s.cookies.set("emp_id", user1["emp_id"])
        s.cookies.set("private_key", user1["key"])
        s.cookies.set("admin_logged_in", "true")
        resp = s.get(f"{base_url}/admin/dashboard", allow_redirects=False)
        assert resp.status_code == 303
        assert "/admin/login" in resp.headers.get("location", "")

    def test_non_admin_cannot_regenerate_key(self, base_url, user1):
        """普通员工不能调用重新生成 key 的管理接口"""
        s = requests.Session()
        s.cookies.set("emp_id", user1["emp_id"])
        s.cookies.set("private_key", user1["key"])
        resp = s.post(f"{base_url}/admin/users/{user1['emp_id']}/regenerate-key")
        assert resp.status_code in (401, 403)

    def test_non_admin_cannot_change_user_status(self, base_url, user1):
        """普通员工不能调用禁用/启用用户的管理接口"""
        s = requests.Session()
        s.cookies.set("emp_id", user1["emp_id"])
        s.cookies.set("private_key", user1["key"])
        resp = s.post(f"{base_url}/admin/users/{user1['emp_id']}/status", json={"status": "disabled"})
        assert resp.status_code in (401, 403)

    def test_no_cookie_cannot_access_admin(self, base_url):
        """没有任何 cookie 不能访问管理后台"""
        resp = requests.get(f"{base_url}/admin/dashboard", allow_redirects=False)
        assert resp.status_code == 303
