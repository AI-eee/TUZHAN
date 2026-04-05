import os
import uuid
import secrets
import random
import string
import json
from fastapi import HTTPException, Cookie
from pydantic import BaseModel

class IdentityRequest(BaseModel):
    identity_md: str

class StatusRequest(BaseModel):
    status: str

class UserCreateRequest(BaseModel):
    nickname: str

class ProjectCreateRequest(BaseModel):
    name: str
    description: str

class MemberCreateRequest(BaseModel):
    emp_ids: list[str]
    role: str

class ProjectDescRequest(BaseModel):
    description: str

class MemberRoleUpdateRequest(BaseModel):
    role: str

class LLMKeyRequest(BaseModel):
    llm_api_key: str

def register_admin_routes(app, db_manager, _require_admin, current_dir):
    
    @app.post("/admin/users/{target_emp_id}/regenerate-key")
    async def regenerate_user_key(target_emp_id: str, emp_id: str = Cookie(None), private_key: str = Cookie(None)):
        _require_admin(emp_id, private_key)
        target_users = db_manager.get_all_users()
        target_user = next((u for u in target_users if u["emp_id"] == target_emp_id), None)
        if not target_user:
            raise HTTPException(status_code=404, detail="未找到对应的员工")
        new_key = f"sk-{secrets.token_hex(16)}"
        success = db_manager.update_user_key_by_emp_id(target_emp_id, new_key)
        if success:
            return {"status": "success", "new_key": new_key}
        else:
            raise HTTPException(status_code=500, detail="重新生成失败，数据库更新错误")

    @app.post("/admin/users/{target_emp_id}/identity")
    async def update_user_identity(target_emp_id: str, req: IdentityRequest, emp_id: str = Cookie(None), private_key: str = Cookie(None)):
        _require_admin(emp_id, private_key)
        success = db_manager.update_user_identity(target_emp_id, req.identity_md)
        if success:
            return {"status": "success"}
        else:
            raise HTTPException(status_code=500, detail="保存失败")

    @app.post("/admin/users/{target_emp_id}/status")
    async def update_user_status(target_emp_id: str, req: StatusRequest, emp_id: str = Cookie(None), private_key: str = Cookie(None)):
        _require_admin(emp_id, private_key)
        if req.status not in ["active", "disabled"]:
            raise HTTPException(status_code=400, detail="Invalid status")
        success = db_manager.update_user_status(target_emp_id, req.status)
        if success:
            return {"status": "success"}
        else:
            raise HTTPException(status_code=500, detail="更新状态失败")

    def sync_org_to_db():
        db_manager.sync_projects_to_users_json()

    @app.post("/admin/users")
    async def add_user(req: UserCreateRequest, emp_id: str = Cookie(None), private_key: str = Cookie(None)):
        _require_admin(emp_id, private_key)
        req.nickname = req.nickname.strip()
        existing = db_manager.get_user_by_nickname(req.nickname)
        if existing:
            return {"status": "error", "detail": "该昵称已被使用，请换一个以方便分辨"}
        while True:
            random_chars = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
            new_emp_id = f"TZ{random_chars}"
            if not db_manager.get_user_info(new_emp_id):
                break
        new_key = f"sk-{secrets.token_hex(16)}"
        db_manager.ensure_user_exists(emp_id=new_emp_id, nickname=req.nickname, projects_json="[]", private_key=new_key)
        return {"status": "success", "emp_id": new_emp_id, "nickname": req.nickname, "private_key": new_key}

    @app.post("/admin/projects")
    async def add_project(req: ProjectCreateRequest, emp_id: str = Cookie(None), private_key: str = Cookie(None)):
        _require_admin(emp_id, private_key)
        success = db_manager.add_project(req.name, req.description)
        if not success:
            raise HTTPException(status_code=400, detail="项目已存在")
        return {"status": "success"}

    @app.delete("/admin/projects/{project_name}")
    async def delete_project(project_name: str, emp_id: str = Cookie(None), private_key: str = Cookie(None)):
        _require_admin(emp_id, private_key)
        member_count = db_manager.get_project_member_count(project_name)
        if member_count > 0:
            raise HTTPException(status_code=400, detail="删除失败：项目中仍有成员，请先移除所有成员。")
        success = db_manager.delete_project(project_name)
        if not success:
            raise HTTPException(status_code=404, detail="项目未找到")
        sync_org_to_db()
        return {"status": "success"}

    @app.post("/admin/projects/{project_name}/members")
    async def add_project_member(project_name: str, req: MemberCreateRequest, emp_id: str = Cookie(None), private_key: str = Cookie(None)):
        _require_admin(emp_id, private_key)
        if not req.emp_ids:
            raise HTTPException(status_code=400, detail="至少需要选择一个成员")
        added_count = 0
        for e_id in req.emp_ids:
            if db_manager.add_project_member(project_name, e_id, req.role):
                added_count += 1
        if added_count == 0:
            raise HTTPException(status_code=400, detail="所选成员已在项目中或不存在")
        sync_org_to_db()
        return {"status": "success", "added": added_count}

    @app.post("/admin/projects/{project_name}/description")
    async def update_project_description(project_name: str, req: ProjectDescRequest, emp_id: str = Cookie(None), private_key: str = Cookie(None)):
        _require_admin(emp_id, private_key)
        success = db_manager.update_project_description(project_name, req.description)
        if not success:
            raise HTTPException(status_code=404, detail="项目未找到")
        sync_org_to_db()
        return {"status": "success"}

    @app.delete("/admin/projects/{project_name}/members/{target_emp_id}")
    async def remove_project_member(project_name: str, target_emp_id: str, emp_id: str = Cookie(None), private_key: str = Cookie(None)):
        _require_admin(emp_id, private_key)
        success = db_manager.remove_project_member(project_name, target_emp_id)
        if not success:
            raise HTTPException(status_code=404, detail="该员工不在项目中")
        sync_org_to_db()
        return {"status": "success"}

    @app.post("/admin/projects/{project_name}/members/{target_emp_id}/role")
    async def update_project_member_role(project_name: str, target_emp_id: str, req: MemberRoleUpdateRequest, emp_id: str = Cookie(None), private_key: str = Cookie(None)):
        _require_admin(emp_id, private_key)
        success = db_manager.update_project_member_role(project_name, target_emp_id, req.role)
        if not success:
            raise HTTPException(status_code=404, detail="更新失败或员工不在项目中")
        sync_org_to_db()
        return {"status": "success"}

    @app.post("/admin/config/llm-key")
    async def update_llm_key(req: LLMKeyRequest, emp_id: str = Cookie(None), private_key: str = Cookie(None)):
        _require_admin(emp_id, private_key)
        if '\n' in req.llm_api_key or '\r' in req.llm_api_key or '=' in req.llm_api_key:
            raise HTTPException(status_code=400, detail="API Key 包含非法字符")
        env_file = os.path.join(current_dir, '..', '..', '.env')
        lines = []
        key_found = False
        if os.path.exists(env_file):
            with open(env_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        with open(env_file, 'w', encoding='utf-8') as f:
            for line in lines:
                if line.startswith("LLM_API_KEY="):
                    f.write(f"LLM_API_KEY={req.llm_api_key}\n")
                    key_found = True
                else:
                    f.write(line)
            if not key_found:
                f.write(f"LLM_API_KEY={req.llm_api_key}\n")
        os.environ["LLM_API_KEY"] = req.llm_api_key
        return {"status": "success"}
