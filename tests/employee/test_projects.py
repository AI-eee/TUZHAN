"""
员工接口 - 项目查询测试
========================
测试员工通过 API 获取自己所属项目及成员列表的功能：
- 正常获取
- 项目数据结构验证
- 权限过滤（只能看到自己所属的项目）
"""
import pytest


class TestGetProjects:
    """GET /api/projects"""

    def test_get_projects_success(self, client, user1, project_name):
        """员工应能获取自己所属的项目列表"""
        resp = client.get(
            "/api/projects",
            headers={"Authorization": f"Bearer {user1['key']}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert isinstance(data["data"], list)

        project_names = [p["name"] for p in data["data"]]
        assert project_name in project_names

    def test_project_contains_members(self, client, user1, user2, project_name):
        """项目数据应包含成员列表"""
        resp = client.get(
            "/api/projects",
            headers={"Authorization": f"Bearer {user1['key']}"},
        )
        projects = resp.json()["data"]
        test_proj = next(p for p in projects if p["name"] == project_name)

        assert "members" in test_proj
        member_ids = [m["emp_id"] for m in test_proj["members"]]
        assert user1["emp_id"] in member_ids
        assert user2["emp_id"] in member_ids

    def test_member_has_correct_fields(self, client, user1, project_name):
        """每个成员应包含 emp_id, role, nickname 字段"""
        resp = client.get(
            "/api/projects",
            headers={"Authorization": f"Bearer {user1['key']}"},
        )
        projects = resp.json()["data"]
        test_proj = next(p for p in projects if p["name"] == project_name)
        member = test_proj["members"][0]

        assert "emp_id" in member
        assert "role" in member
        assert "nickname" in member

    def test_project_has_description(self, client, user1, project_name):
        """项目应包含 description 字段"""
        resp = client.get(
            "/api/projects",
            headers={"Authorization": f"Bearer {user1['key']}"},
        )
        projects = resp.json()["data"]
        test_proj = next(p for p in projects if p["name"] == project_name)
        assert "description" in test_proj

    def test_noproj_user_sees_empty_list(self, client, noproj_user):
        """不属于任何项目的员工应获取到空列表"""
        resp = client.get(
            "/api/projects",
            headers={"Authorization": f"Bearer {noproj_user['key']}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["data"] == []

    def test_disabled_user_cannot_get_projects(self, client, disabled_user):
        """被禁用的员工不能获取项目列表"""
        resp = client.get(
            "/api/projects",
            headers={"Authorization": f"Bearer {disabled_user['key']}"},
        )
        assert resp.status_code == 403

    def test_only_sees_own_projects(self, client, user1):
        """员工只能看到自己所属的项目，不能看到其他项目"""
        resp = client.get(
            "/api/projects",
            headers={"Authorization": f"Bearer {user1['key']}"},
        )
        projects = resp.json()["data"]
        for p in projects:
            member_ids = [m["emp_id"] for m in p.get("members", [])]
            assert user1["emp_id"] in member_ids
