"""
管理员接口 - 用户管理测试
============================
测试管理员对用户的管理操作：重新生成 Key、更新身份设定、启用/禁用。
"""
import pytest
import requests


class TestRegenerateKey:
    """POST /admin/users/{emp_id}/regenerate-key"""

    def test_regenerate_key_success(self, base_url, admin_session, user2):
        """管理员应能为员工重新生成 Private Key"""
        resp = admin_session.post(f"{base_url}/admin/users/{user2['emp_id']}/regenerate-key")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["new_key"].startswith("sk-")
        assert len(data["new_key"]) == 35  # "sk-" + 32 hex chars
        # 更新 key 供后续测试使用
        user2["key"] = data["new_key"]

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
