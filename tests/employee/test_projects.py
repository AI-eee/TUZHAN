"""
员工接口 - 项目查询测试
========================
测试员工通过 API 获取自己所属项目及成员列表的功能。
"""
import pytest
import requests


def _auth(key):
    return {"Authorization": f"Bearer {key}"}


class TestGetProjects:
    """GET /api/projects"""

    def test_get_projects_success(self, api_url, user1, project_name):
        """员工应能获取自己所属的项目列表"""
        resp = requests.get(f"{api_url}/projects", headers=_auth(user1["key"]))
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert project_name in [p["name"] for p in data["data"]]

    def test_project_contains_members(self, api_url, user1, user2, project_name):
        """项目数据应包含成员列表"""
        resp = requests.get(f"{api_url}/projects", headers=_auth(user1["key"]))
        test_proj = next(p for p in resp.json()["data"] if p["name"] == project_name)
        member_ids = [m["emp_id"] for m in test_proj["members"]]
        assert user1["emp_id"] in member_ids
        assert user2["emp_id"] in member_ids

    def test_member_has_correct_fields(self, api_url, user1, project_name):
        """每个成员应包含 emp_id, role, nickname 字段"""
        resp = requests.get(f"{api_url}/projects", headers=_auth(user1["key"]))
        test_proj = next(p for p in resp.json()["data"] if p["name"] == project_name)
        member = test_proj["members"][0]
        for field in ("emp_id", "role", "nickname"):
            assert field in member

    def test_project_has_description(self, api_url, user1, project_name):
        """项目应包含 description 字段"""
        resp = requests.get(f"{api_url}/projects", headers=_auth(user1["key"]))
        test_proj = next(p for p in resp.json()["data"] if p["name"] == project_name)
        assert "description" in test_proj

    def test_noproj_user_sees_empty_list(self, api_url, noproj_user):
        """不属于任何项目的员工应获取到空列表"""
        resp = requests.get(f"{api_url}/projects", headers=_auth(noproj_user["key"]))
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    def test_disabled_user_cannot_get_projects(self, api_url, disabled_user):
        """被禁用的员工不能获取项目列表"""
        resp = requests.get(f"{api_url}/projects", headers=_auth(disabled_user["key"]))
        assert resp.status_code == 403

    def test_only_sees_own_projects(self, api_url, user1):
        """员工只能看到自己所属的项目"""
        resp = requests.get(f"{api_url}/projects", headers=_auth(user1["key"]))
        for p in resp.json()["data"]:
            member_ids = [m["emp_id"] for m in p.get("members", [])]
            assert user1["emp_id"] in member_ids
