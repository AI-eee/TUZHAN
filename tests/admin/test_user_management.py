"""
管理员接口 - 用户管理测试
============================
测试管理员对用户的管理操作：
- 重新生成 Private Key
- 更新用户身份设定
- 启用/禁用用户
"""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from conftest import _cookie_header


def _admin_headers(admin_user):
    cookies = {"emp_id": admin_user["emp_id"], "private_key": admin_user["key"]}
    return {"Cookie": _cookie_header(cookies)}


class TestRegenerateKey:
    """POST /admin/users/{emp_id}/regenerate-key"""

    def test_regenerate_key_success(self, client, admin_user, user2):
        """管理员应能为员工重新生成 Private Key"""
        resp = client.post(
            f"/admin/users/{user2['emp_id']}/regenerate-key",
            headers=_admin_headers(admin_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["new_key"].startswith("sk-")
        assert len(data["new_key"]) == 35  # "sk-" + 32 hex chars

        # 更新 fixture 中的 key 以便后续测试使用
        user2["key"] = data["new_key"]

    def test_regenerate_key_nonexistent_user(self, client, admin_user):
        """为不存在的用户重新生成 key 应返回 404"""
        resp = client.post(
            "/admin/users/TZ_NONEXISTENT/regenerate-key",
            headers=_admin_headers(admin_user),
        )
        assert resp.status_code == 404


class TestUpdateIdentity:
    """POST /admin/users/{emp_id}/identity"""

    def test_update_identity_success(self, client, admin_user, user1):
        """管理员应能更新员工的身份设定 Markdown"""
        identity = "# AI Agent\n\n你是一个专业的数据分析助手。"
        resp = client.post(
            f"/admin/users/{user1['emp_id']}/identity",
            headers=_admin_headers(admin_user),
            json={"identity_md": identity},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"


class TestUpdateUserStatus:
    """POST /admin/users/{emp_id}/status"""

    def test_disable_user_success(self, client, admin_user, db_manager):
        """管理员应能禁用员工"""
        tmp_emp = "TZtmpDisable"
        tmp_key = "sk-tmpdisablekey000000000000000099"
        db_manager.ensure_user_exists(tmp_emp, "临时用户", "[]", tmp_key)

        resp = client.post(
            f"/admin/users/{tmp_emp}/status",
            headers=_admin_headers(admin_user),
            json={"status": "disabled"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

        user_info = db_manager.get_user_info(tmp_emp)
        assert user_info["status"] == "disabled"

    def test_enable_user_success(self, client, admin_user, db_manager):
        """管理员应能重新启用员工"""
        resp = client.post(
            "/admin/users/TZtmpDisable/status",
            headers=_admin_headers(admin_user),
            json={"status": "active"},
        )
        assert resp.status_code == 200
        user_info = db_manager.get_user_info("TZtmpDisable")
        assert user_info["status"] == "active"

    def test_invalid_status_returns_400(self, client, admin_user, user1):
        """无效的 status 值应返回 400"""
        resp = client.post(
            f"/admin/users/{user1['emp_id']}/status",
            headers=_admin_headers(admin_user),
            json={"status": "unknown_status"},
        )
        assert resp.status_code == 400
