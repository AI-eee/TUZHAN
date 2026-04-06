"""
管理员接口 - 项目管理测试
============================
测试管理员对项目和成员的管理操作。
"""
import pytest
import requests


class TestProjectCRUD:
    """项目创建与更新"""

    def test_create_project_success(self, base_url, admin_session):
        """管理员应能创建新项目"""
        resp = admin_session.post(f"{base_url}/admin/projects",
                                  json={"name": "_TestNewProject", "description": "管理员创建的测试项目"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    def test_create_duplicate_project_returns_400(self, base_url, admin_session):
        """创建同名项目应返回 400"""
        resp = admin_session.post(f"{base_url}/admin/projects",
                                  json={"name": "_TestNewProject", "description": "重复项目"})
        assert resp.status_code == 400

    def test_update_project_description(self, base_url, admin_session):
        """管理员应能更新项目描述"""
        resp = admin_session.post(f"{base_url}/admin/projects/_TestNewProject/description",
                                  json={"description": "更新后的项目描述"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    def test_update_nonexistent_project_returns_404(self, base_url, admin_session):
        """更新不存在的项目描述应返回 404"""
        resp = admin_session.post(f"{base_url}/admin/projects/NonExistentProject/description",
                                  json={"description": "无效更新"})
        assert resp.status_code == 404

    def test_delete_project_with_members_fails(self, base_url, admin_session, noproj_user, db_manager):
        """删除有成员的项目应失败，返回 400"""
        import uuid
        proj_name = f"ProjectToDelete_{uuid.uuid4().hex[:8]}"
        # Create a new project
        resp = admin_session.post(
            f"{base_url}/admin/projects",
            json={"name": proj_name, "description": "Desc"}
        )
        assert resp.status_code == 200
        
        # Add a member
        resp = admin_session.post(
            f"{base_url}/admin/projects/{proj_name}/members",
            json={"emp_ids": [noproj_user["emp_id"]], "role": "Member"}
        )
        assert resp.status_code == 200
        
        # Try to delete
        resp = admin_session.delete(f"{base_url}/admin/projects/{proj_name}")
        assert resp.status_code == 400
        assert "请先移除所有成员" in resp.json()["detail"]
        
        # [修改原因]: 清理测试产生的数据，避免 noproj_user 被错误地关联项目而污染后续的测试用例
        admin_session.delete(f"{base_url}/admin/projects/{proj_name}/members/{noproj_user['emp_id']}")
        admin_session.delete(f"{base_url}/admin/projects/{proj_name}")

    def test_delete_project_without_members_success(self, base_url, admin_session, noproj_user):
        """删除没有成员的项目应成功，并且后续查不到"""
        import uuid
        proj_name = f"ProjectToDelete2_{uuid.uuid4().hex[:8]}"
        # Create a new project
        resp = admin_session.post(
            f"{base_url}/admin/projects",
            json={"name": proj_name, "description": "Desc"}
        )
        assert resp.status_code == 200
        
        # Delete project
        resp = admin_session.delete(f"{base_url}/admin/projects/{proj_name}")
        assert resp.status_code == 200
        
        # Try to fetch all projects and verify it's not there
        # We can just check the dashboard response
        dashboard_resp = admin_session.get(f"{base_url}/admin/dashboard")
        assert proj_name not in dashboard_resp.text


class TestProjectMembers:
    """项目成员管理"""

    def test_add_member_success(self, base_url, admin_session, user1):
        """管理员应能向项目添加成员"""
        resp = admin_session.post(f"{base_url}/admin/projects/_TestNewProject/members",
                                  json={"emp_ids": [user1["emp_id"]], "role": "Developer"})
        assert resp.status_code == 200
        assert resp.json()["added"] == 1

    def test_add_multiple_members(self, base_url, admin_session, user2, noproj_user):
        """管理员应能批量添加多个成员"""
        resp = admin_session.post(f"{base_url}/admin/projects/_TestNewProject/members",
                                  json={"emp_ids": [user2["emp_id"], noproj_user["emp_id"]], "role": "Member"})
        assert resp.status_code == 200
        assert resp.json()["added"] == 2

    def test_add_duplicate_member_returns_400(self, base_url, admin_session, user1):
        """重复添加已有成员应返回 400"""
        resp = admin_session.post(f"{base_url}/admin/projects/_TestNewProject/members",
                                  json={"emp_ids": [user1["emp_id"]], "role": "Developer"})
        assert resp.status_code == 400

    def test_add_empty_list_returns_400(self, base_url, admin_session):
        """空成员列表应返回 400"""
        resp = admin_session.post(f"{base_url}/admin/projects/_TestNewProject/members",
                                  json={"emp_ids": [], "role": "Member"})
        assert resp.status_code == 400

    def test_update_member_role(self, base_url, admin_session, user1):
        """管理员应能修改成员角色"""
        resp = admin_session.post(f"{base_url}/admin/projects/_TestNewProject/members/{user1['emp_id']}/role",
                                  json={"role": "Tech Lead"})
        assert resp.status_code == 200

    def test_update_nonexistent_member_role_returns_404(self, base_url, admin_session):
        """更新不在项目中的成员角色应返回 404"""
        resp = admin_session.post(f"{base_url}/admin/projects/_TestNewProject/members/TZ_GHOST/role",
                                  json={"role": "Leader"})
        assert resp.status_code == 404

    def test_remove_member_success(self, base_url, admin_session, noproj_user):
        """管理员应能从项目中移除成员"""
        resp = admin_session.delete(f"{base_url}/admin/projects/_TestNewProject/members/{noproj_user['emp_id']}")
        assert resp.status_code == 200

    def test_remove_nonexistent_member_returns_404(self, base_url, admin_session):
        """移除不在项目中的成员应返回 404"""
        resp = admin_session.delete(f"{base_url}/admin/projects/_TestNewProject/members/TZ_NOT_IN_PROJECT")
        assert resp.status_code == 404
