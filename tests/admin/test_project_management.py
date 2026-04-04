"""
管理员接口 - 项目管理测试
============================
测试管理员对项目和成员的管理操作：
- 创建项目
- 添加/移除成员
- 修改成员角色
- 更新项目描述
"""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from conftest import _cookie_header


def _admin_headers(admin_user):
    cookies = {"emp_id": admin_user["emp_id"], "private_key": admin_user["key"]}
    return {"Cookie": _cookie_header(cookies)}


class TestProjectCRUD:
    """项目创建与更新"""

    def test_create_project_success(self, client, admin_user):
        """管理员应能创建新项目"""
        resp = client.post(
            "/admin/projects",
            headers=_admin_headers(admin_user),
            json={"name": "NewTestProject", "description": "管理员创建的测试项目"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    def test_create_duplicate_project_returns_400(self, client, admin_user):
        """创建同名项目应返回 400"""
        resp = client.post(
            "/admin/projects",
            headers=_admin_headers(admin_user),
            json={"name": "NewTestProject", "description": "重复项目"},
        )
        assert resp.status_code == 400

    def test_update_project_description(self, client, admin_user):
        """管理员应能更新项目描述"""
        resp = client.post(
            "/admin/projects/NewTestProject/description",
            headers=_admin_headers(admin_user),
            json={"description": "更新后的项目描述"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    def test_update_nonexistent_project_returns_404(self, client, admin_user):
        """更新不存在的项目描述应返回 404"""
        resp = client.post(
            "/admin/projects/NonExistentProject/description",
            headers=_admin_headers(admin_user),
            json={"description": "无效更新"},
        )
        assert resp.status_code == 404


class TestProjectMembers:
    """项目成员管理"""

    def test_add_member_success(self, client, admin_user, user1):
        """管理员应能向项目添加成员"""
        resp = client.post(
            "/admin/projects/NewTestProject/members",
            headers=_admin_headers(admin_user),
            json={"emp_ids": [user1["emp_id"]], "role": "Developer"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["added"] == 1

    def test_add_multiple_members(self, client, admin_user, user2, noproj_user):
        """管理员应能批量添加多个成员"""
        resp = client.post(
            "/admin/projects/NewTestProject/members",
            headers=_admin_headers(admin_user),
            json={
                "emp_ids": [user2["emp_id"], noproj_user["emp_id"]],
                "role": "Member",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["added"] == 2

    def test_add_duplicate_member_returns_400(self, client, admin_user, user1):
        """重复添加已有成员应返回 400"""
        resp = client.post(
            "/admin/projects/NewTestProject/members",
            headers=_admin_headers(admin_user),
            json={"emp_ids": [user1["emp_id"]], "role": "Developer"},
        )
        assert resp.status_code == 400

    def test_add_empty_list_returns_400(self, client, admin_user):
        """空成员列表应返回 400"""
        resp = client.post(
            "/admin/projects/NewTestProject/members",
            headers=_admin_headers(admin_user),
            json={"emp_ids": [], "role": "Member"},
        )
        assert resp.status_code == 400

    def test_update_member_role(self, client, admin_user, user1):
        """管理员应能修改成员角色"""
        resp = client.post(
            f"/admin/projects/NewTestProject/members/{user1['emp_id']}/role",
            headers=_admin_headers(admin_user),
            json={"role": "Tech Lead"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    def test_update_nonexistent_member_role_returns_404(self, client, admin_user):
        """更新不在项目中的成员角色应返回 404"""
        resp = client.post(
            "/admin/projects/NewTestProject/members/TZ_GHOST/role",
            headers=_admin_headers(admin_user),
            json={"role": "Leader"},
        )
        assert resp.status_code == 404

    def test_remove_member_success(self, client, admin_user, noproj_user):
        """管理员应能从项目中移除成员"""
        resp = client.delete(
            f"/admin/projects/NewTestProject/members/{noproj_user['emp_id']}",
            headers=_admin_headers(admin_user),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    def test_remove_nonexistent_member_returns_404(self, client, admin_user):
        """移除不在项目中的成员应返回 404"""
        resp = client.delete(
            "/admin/projects/NewTestProject/members/TZ_NOT_IN_PROJECT",
            headers=_admin_headers(admin_user),
        )
        assert resp.status_code == 404
