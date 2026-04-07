"""
管理员接口 - 用户管理测试
============================
测试管理员对用户的管理操作：重新生成 Key、更新身份设定、启用/禁用。
"""
import pytest
import requests


class TestAddUser:
    """POST /admin/users"""
    
    def test_add_user_success(self, base_url, admin_session, db_manager):
        """管理员应能新增员工，但响应中绝不应包含 Private Key 明文"""
        resp = admin_session.post(f"{base_url}/admin/users", json={"nickname": "TestNewUser"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["emp_id"].startswith("TZ")
        assert data["nickname"] == "TestNewUser"
        # [安全] 新增接口不应回显 private_key
        assert "private_key" not in data
        assert "new_key" not in data

        # Verify in DB
        user_info = db_manager.get_user_info(data["emp_id"])
        assert user_info is not None
        assert user_info["nickname"] == "TestNewUser"
        assert user_info["private_key"].startswith("sk-")

        # 通过 reveal 接口可以拿到明文 Key
        reveal = admin_session.get(f"{base_url}/admin/users/{data['emp_id']}/key")
        assert reveal.status_code == 200
        assert reveal.json()["private_key"] == user_info["private_key"]


class TestRevealKey:
    """GET /admin/users/{emp_id}/key —— 按需取明文 Key（用于复制按钮）"""

    def test_reveal_key_returns_db_key(self, base_url, admin_session, user2, db_manager):
        resp = admin_session.get(f"{base_url}/admin/users/{user2['emp_id']}/key")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["private_key"] == db_manager.get_user_info(user2["emp_id"])["private_key"]

    def test_reveal_key_nonexistent(self, base_url, admin_session):
        resp = admin_session.get(f"{base_url}/admin/users/TZ_NONEXISTENT/key")
        assert resp.status_code == 404

    def test_reveal_key_requires_admin(self, base_url, user1, user2):
        """非管理员不得调用 reveal 接口"""
        s = requests.Session()
        s.post(f"{base_url}/login", data={"private_key": user1["key"]}, allow_redirects=False)
        resp = s.get(f"{base_url}/admin/users/{user2['emp_id']}/key")
        assert resp.status_code in (401, 403)

    def test_admin_dashboard_html_contains_no_plaintext_keys(self, base_url, admin_session, user1, user2):
        """管理后台 HTML 源码中绝不应出现任何 sk- 开头的 32 位十六进制明文 Key"""
        page = admin_session.get(f"{base_url}/admin/dashboard")
        assert page.status_code == 200
        # 用户 1/2 的真实 key 都不应在源码中出现
        assert user1["key"] not in page.text
        assert user2["key"] not in page.text


class TestRegenerateKey:
    """POST /admin/users/{emp_id}/regenerate-key"""

    def test_regenerate_key_success(self, base_url, admin_session, user2, db_manager):
        """管理员应能为员工重新生成 Private Key（响应不回显明文）"""
        old_key = db_manager.get_user_info(user2["emp_id"])["private_key"]
        resp = admin_session.post(f"{base_url}/admin/users/{user2['emp_id']}/regenerate-key")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        # [安全] 不应回显 new_key
        assert "new_key" not in data
        assert "private_key" not in data
        # DB 中的 Key 已更新
        new_key = db_manager.get_user_info(user2["emp_id"])["private_key"]
        assert new_key.startswith("sk-")
        assert new_key != old_key
        # 更新 fixture 供后续测试使用
        user2["key"] = new_key

    def test_regenerate_key_nonexistent_user(self, base_url, admin_session):
        """为不存在的用户重新生成 key 应返回 404"""
        resp = admin_session.post(f"{base_url}/admin/users/TZ_NONEXISTENT/regenerate-key")
        assert resp.status_code == 404


class TestUpdateIdentity:
    """POST /admin/users/{emp_id}/identity"""

    def test_update_identity_success(self, base_url, admin_session, user1):
        """管理员应能更新员工的身份设定 Markdown"""
        resp = admin_session.post(f"{base_url}/admin/users/{user1['emp_id']}/identity",
                                  json={"identity_md": "# AI Agent\n\n你是一个专业的数据分析助手。"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"


class TestUpdateUserStatus:
    """POST /admin/users/{emp_id}/status"""

    def test_disable_user_success(self, base_url, admin_session, db_manager):
        """管理员应能禁用员工"""
        tmp_emp = "TZtmpDisable"
        db_manager.ensure_user_exists(tmp_emp, "临时用户", "[]", "sk-tmpdisablekey000000000000000099")

        resp = admin_session.post(f"{base_url}/admin/users/{tmp_emp}/status", json={"status": "disabled"})
        assert resp.status_code == 200
        assert db_manager.get_user_info(tmp_emp)["status"] == "disabled"

    def test_enable_user_success(self, base_url, admin_session, db_manager):
        """管理员应能重新启用员工"""
        resp = admin_session.post(f"{base_url}/admin/users/TZtmpDisable/status", json={"status": "active"})
        assert resp.status_code == 200
        assert db_manager.get_user_info("TZtmpDisable")["status"] == "active"

    def test_invalid_status_returns_400(self, base_url, admin_session, user1):
        """无效的 status 值应返回 400"""
        resp = admin_session.post(f"{base_url}/admin/users/{user1['emp_id']}/status",
                                  json={"status": "unknown_status"})
        assert resp.status_code == 400
