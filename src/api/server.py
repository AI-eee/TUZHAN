# [修改原因]: 兼容低版本 Python 中的 `str | None` 类型注解
from __future__ import annotations
from fastapi import FastAPI, HTTPException, Request, Form, Response, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import os
import yaml
import logging
from dotenv import load_dotenv
from openai import OpenAI
import markdown2
import bleach

# 加载 .env 环境变量
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from core.message_manager import MessageManager
from core.database import DatabaseManager

# 初始化基础日志和应用
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="TUZHAN 协作中心 API & Web",
    description="提供给员工/Agent 收发 Markdown 信息的接口服务，现已通过SQLite落库管理。",
    version="2.0.0"
)

current_dir = os.path.dirname(os.path.abspath(__file__))
# [修改原因]: 引入 Jinja2 模板和静态文件支持
templates = Jinja2Templates(directory=os.path.join(current_dir, "..", "templates"))

# [新增原因]: 增加 Jinja2 过滤器，用于安全地将 Markdown 渲染为 HTML (防 XSS)
def safe_markdown_filter(text):
    if not text:
        return ""
    # 1. 转换 markdown 为 HTML
    html = markdown2.markdown(text)
    # 2. 清洗 HTML
    allowed_tags = list(bleach.ALLOWED_TAGS) + ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'br', 'pre', 'code', 'blockquote', 'hr', 'img']
    allowed_attrs = {**bleach.ALLOWED_ATTRIBUTES, 'img': ['src', 'alt', 'title']}
    clean_html = bleach.clean(html, tags=allowed_tags, attributes=allowed_attrs)
    return clean_html

templates.env.filters["render_markdown"] = safe_markdown_filter

app.mount("/static", StaticFiles(directory=os.path.join(current_dir, "..", "static")), name="static")

# [修改原因]: 读取环境配置，初始化对应环境的数据库
settings_file = os.path.join(current_dir, '..', '..', 'config', 'settings.yaml')
env = os.getenv("TUZHAN_ENV", "development")
with open(settings_file, 'r', encoding='utf-8') as f:
    settings = yaml.safe_load(f)
    db_url = settings.get(env, settings["development"]).get("database_url", "sqlite:///./data/dev.sqlite")

# 将 "sqlite:///./data/dev.sqlite" 转换为绝对路径，确保在不同目录启动时不报错
db_path = db_url.replace("sqlite:///", "")
if db_path.startswith("./"):
    db_path = os.path.join(current_dir, "..", "..", db_path[2:])
else:
    db_path = os.path.abspath(db_path)

db_manager = DatabaseManager(db_path)
message_manager = MessageManager(db_manager)

# [修改原因]: 统一的会话校验函数，防止 Cookie 伪造绕过认证 (BUG-01 修复)
# [修改原因]: 将 active_only 改为 True，已禁用用户的会话立即失效 (BUG-17 修复)
def _verify_session(emp_id: str, private_key: str) -> str | None:
    """
    校验 Cookie 中的 private_key 是否与 emp_id 匹配，且用户状态为 active。
    返回验证通过的 emp_id，否则返回 None。
    """
    if not emp_id or not private_key:
        return None
    verified_emp_id = db_manager.get_user_by_key(private_key, active_only=True)
    if not verified_emp_id or verified_emp_id != emp_id:
        return None
    return verified_emp_id

# [新增原因]: 统一的管理员权限校验函数，同时验证 session 和 is_admin (BUG-16 修复)
def _require_admin(emp_id: str, private_key: str):
    """
    校验当前请求是否来自合法的管理员。
    同时验证 private_key 与 emp_id 的匹配关系，以及 is_admin 字段。
    校验失败时直接抛出 HTTPException。
    """
    if not _verify_session(emp_id, private_key):
        raise HTTPException(status_code=401, detail="未授权：会话无效或已过期")
    user_info = db_manager.get_user_info(emp_id)
    if not user_info or not user_info.get("is_admin"):
        raise HTTPException(status_code=403, detail="Access Denied: You are not the administrator.")

# [修改原因]: Cookie 安全属性常量，防止 XSS/CSRF 窃取凭证 (BUG-02 修复)
COOKIE_OPTS = {"httponly": True, "samesite": "Lax"}

# ----------------- WEB UI 路由 -----------------

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, emp_id: str = Cookie(None), private_key: str = Cookie(None)):
    """Web 入口：如果登录过且会话有效则进工作台，否则进登录页"""
    if _verify_session(emp_id, private_key):
        return RedirectResponse(url="/dashboard", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(request: Request, private_key: str = Form(...)):
    """[修改原因]: 改为通过 Private Key 登录，获取 emp_id 并在全局废弃 username"""
    emp_id = db_manager.get_user_by_key(private_key, active_only=False)
    
    if not emp_id:
        # 登录失败，回到登录页并报错
        return templates.TemplateResponse("login.html", {
            "request": request, 
            "error": "无效的 Private Key，请联系管理员获取。"
        })
        
    user_info = db_manager.get_user_info(emp_id)
    if user_info and user_info.get("status") == "disabled":
        return templates.TemplateResponse("login.html", {
            "request": request, 
            "error": "您的账号已被禁用，请联系管理员。"
        })
        
    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie(key="emp_id", value=emp_id, **COOKIE_OPTS)
    response.set_cookie(key="private_key", value=private_key, **COOKIE_OPTS)
    return response

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("emp_id")
    response.delete_cookie("private_key")
    response.delete_cookie("admin_logged_in")
    return response

import json

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, emp_id: str = Cookie(None), private_key: str = Cookie(None)):
    """用户控制台"""
    if not _verify_session(emp_id, private_key):
        return RedirectResponse(url="/", status_code=303)

    user_info = db_manager.get_user_info(emp_id)
    projects = []
    if user_info and user_info.get("projects"):
        try:
            projects = json.loads(user_info["projects"])
        except:
            pass
            
    messages = message_manager.get_inbox_messages(emp_id)
    sent_messages = message_manager.get_outbox_messages(emp_id)
    return templates.TemplateResponse("dashboard.html", {
        "request": request, 
        "current_emp_id": emp_id,
        "user_info": user_info,
        "projects": projects,
        "messages": messages,
        "sent_messages": sent_messages
    })

@app.get("/admin/login", response_class=HTMLResponse)
async def admin_login_page(request: Request, emp_id: str = Cookie(None), private_key: str = Cookie(None), admin_logged_in: str = Cookie(None)):
    """[新增原因]: 单独的管理员登录页面"""
    if admin_logged_in == "true" and _verify_session(emp_id, private_key):
        return RedirectResponse(url="/admin/dashboard", status_code=303)
    return templates.TemplateResponse("admin_login.html", {"request": request})

@app.post("/admin/login")
async def admin_login(request: Request, private_key: str = Form(...)):
    """[修改原因]: 验证管理员身份，改为检查 is_admin 字段而非硬编码 emp_id"""
    emp_id = db_manager.get_user_by_key(private_key, active_only=False)
    
    if not emp_id:
        return templates.TemplateResponse("admin_login.html", {
            "request": request, 
            "error": "无效的 Private Key。"
        })
        
    user_info = db_manager.get_user_info(emp_id)
    if not user_info or not user_info.get("is_admin"):
        return templates.TemplateResponse("admin_login.html", {
            "request": request, 
            "error": "抱歉，您不是系统管理员，无权访问此页面。"
        })
        
    response = RedirectResponse(url="/admin/dashboard", status_code=303)
    response.set_cookie(key="emp_id", value=emp_id, **COOKIE_OPTS)
    response.set_cookie(key="private_key", value=private_key, **COOKIE_OPTS)
    response.set_cookie(key="admin_logged_in", value="true", **COOKIE_OPTS)
    return response

@app.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request, emp_id: str = Cookie(None), private_key: str = Cookie(None), admin_logged_in: str = Cookie(None)):
    """
    [修改原因]: 管理员后台，改为检查 is_admin 字段而非硬编码 emp_id。
    """
    if not _verify_session(emp_id, private_key) or admin_logged_in != "true":
        return RedirectResponse(url="/admin/login", status_code=303)

    user_info = db_manager.get_user_info(emp_id)
    if not user_info or not user_info.get("is_admin"):
        # 如果不是管理员，强制踢回普通控制台或提示无权限
        return RedirectResponse(url="/admin/login", status_code=303)
        
    all_users = db_manager.get_all_users()
    all_messages = db_manager.get_all_messages()
    
    # 将 projects JSON 字符串反序列化供模板渲染
    for u in all_users:
        if u.get("projects"):
            try:
                u["projects_list"] = json.loads(u["projects"])
            except:
                u["projects_list"] = []
                
    # 使用 DB 中存储的项目信息
    org_projects = db_manager.get_all_projects()
    
    # 提取系统配置以供后台展示
    api_key = os.getenv("LLM_API_KEY", "")
    masked_api_key = f"{api_key[:6]}******{api_key[-4:]}" if len(api_key) > 10 else "未配置"
    
    system_config = {
        "env": env,
        "db_path": db_path,
        "llm_api_key": masked_api_key,
        "base_url": settings.get(env, {}).get("client_base_url", "未配置")
    }
    
    return templates.TemplateResponse("admin_dashboard.html", {
        "request": request, 
        "current_emp_id": emp_id,
        "user_info": user_info,
        "all_users": all_users,
        "all_messages": all_messages,
        "system_config": system_config,
        "org_projects": org_projects
    })

import uuid
import secrets

@app.post("/admin/users/{target_emp_id}/regenerate-key")
async def regenerate_user_key(target_emp_id: str, emp_id: str = Cookie(None), private_key: str = Cookie(None)):
    """[修改原因]: 允许管理员为员工重新生成 Private Key。增加 private_key 会话校验 (BUG-16 修复)"""
    _require_admin(emp_id, private_key)
        
    # 查找被修改用户
    target_users = db_manager.get_all_users()
    target_user = next((u for u in target_users if u["emp_id"] == target_emp_id), None)
    if not target_user:
        raise HTTPException(status_code=404, detail="未找到对应的员工")
        
    # 生成 sk- + 32位安全的随机字符串
    random_str = secrets.token_hex(16) # 16 bytes = 32 hex chars
    new_key = f"sk-{random_str}"
    success = db_manager.update_user_key_by_emp_id(target_emp_id, new_key)
    
    if success:
        return {"status": "success", "new_key": new_key}
    else:
        raise HTTPException(status_code=500, detail="重新生成失败，数据库更新错误")

class IdentityRequest(BaseModel):
    identity_md: str

@app.post("/admin/users/{target_emp_id}/identity")
async def update_user_identity(target_emp_id: str, req: IdentityRequest, emp_id: str = Cookie(None), private_key: str = Cookie(None)):
    """[新增原因]: 允许管理员更新员工身份设定的 Markdown。增加 private_key 会话校验 (BUG-16 修复)"""
    _require_admin(emp_id, private_key)
        
    success = db_manager.update_user_identity(target_emp_id, req.identity_md)
    if success:
        return {"status": "success"}
    else:
        raise HTTPException(status_code=500, detail="保存失败")

class StatusRequest(BaseModel):
    status: str

@app.post("/admin/users/{target_emp_id}/status")
async def update_user_status(target_emp_id: str, req: StatusRequest, emp_id: str = Cookie(None), private_key: str = Cookie(None)):
    """[新增原因]: 允许管理员启用/禁用员工。增加 private_key 会话校验 (BUG-16 修复)"""
    _require_admin(emp_id, private_key)
        
    if req.status not in ["active", "disabled"]:
        raise HTTPException(status_code=400, detail="Invalid status")
        
    success = db_manager.update_user_status(target_emp_id, req.status)
    if success:
        return {"status": "success"}
    else:
        raise HTTPException(status_code=500, detail="更新状态失败")

def sync_org_to_db():
    """将 projects 表同步到 users 数据库，确保项目成员变更生效"""
    db_manager.sync_projects_to_users_json()

class ProjectCreateRequest(BaseModel):
    name: str
    description: str

@app.post("/admin/projects")
async def add_project(req: ProjectCreateRequest, emp_id: str = Cookie(None), private_key: str = Cookie(None)):
    """[新增原因]: 增加新项目到数据库。增加 private_key 会话校验 (BUG-16 修复)"""
    _require_admin(emp_id, private_key)
        
    success = db_manager.add_project(req.name, req.description)
    if not success:
        raise HTTPException(status_code=400, detail="项目已存在")
        
    return {"status": "success"}

class MemberCreateRequest(BaseModel):
    emp_ids: list[str]
    role: str

@app.post("/admin/projects/{project_name}/members")
async def add_project_member(project_name: str, req: MemberCreateRequest, emp_id: str = Cookie(None), private_key: str = Cookie(None)):
    """[修改原因]: 向项目批量添加新成员（从库中选择）。增加 private_key 会话校验 (BUG-16 修复)"""
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

class ProjectDescRequest(BaseModel):
    description: str

@app.post("/admin/projects/{project_name}/description")
async def update_project_description(project_name: str, req: ProjectDescRequest, emp_id: str = Cookie(None), private_key: str = Cookie(None)):
    """[新增原因]: 允许管理员双击修改项目说明并保存到数据库。增加 private_key 会话校验 (BUG-16 修复)"""
    _require_admin(emp_id, private_key)
        
    success = db_manager.update_project_description(project_name, req.description)
    if not success:
        raise HTTPException(status_code=404, detail="项目未找到")
        
    sync_org_to_db()
    return {"status": "success"}

@app.delete("/admin/projects/{project_name}/members/{target_emp_id}")
async def remove_project_member(project_name: str, target_emp_id: str, emp_id: str = Cookie(None), private_key: str = Cookie(None)):
    """[新增原因]: 从项目中移除成员。增加 private_key 会话校验 (BUG-16 修复)"""
    _require_admin(emp_id, private_key)
        
    success = db_manager.remove_project_member(project_name, target_emp_id)
    if not success:
        raise HTTPException(status_code=404, detail="该员工不在项目中")
        
    sync_org_to_db()
    return {"status": "success"}

class MemberRoleUpdateRequest(BaseModel):
    role: str

@app.post("/admin/projects/{project_name}/members/{target_emp_id}/role")
async def update_project_member_role(project_name: str, target_emp_id: str, req: MemberRoleUpdateRequest, emp_id: str = Cookie(None), private_key: str = Cookie(None)):
    """[新增原因]: 允许管理员编辑项目成员的角色。增加 private_key 会话校验 (BUG-16 修复)"""
    _require_admin(emp_id, private_key)
        
    success = db_manager.update_project_member_role(project_name, target_emp_id, req.role)
    if not success:
        raise HTTPException(status_code=404, detail="更新失败或员工不在项目中")
        
    sync_org_to_db()
    return {"status": "success"}

class LLMKeyRequest(BaseModel):
    llm_api_key: str

@app.post("/admin/config/llm-key")
async def update_llm_key(req: LLMKeyRequest, emp_id: str = Cookie(None), private_key: str = Cookie(None)):
    """[新增原因]: 允许管理员更新 LLM_API_KEY。增加 private_key 会话校验 (BUG-16 修复)"""
    _require_admin(emp_id, private_key)
        
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
            
    # 动态更新当前运行环境中的环境变量
    os.environ["LLM_API_KEY"] = req.llm_api_key
    return {"status": "success"}

@app.post("/dashboard/send")
async def dashboard_send(
    request: Request,
    receiver: str = Form(...),
    content: str = Form(...),
    emp_id: str = Cookie(None),
    private_key: str = Cookie(None)
):
    """Web端发消息处理，增加对 Key 的校验及群发支持"""
    if not private_key or db_manager.get_user_by_key(private_key, active_only=False) != emp_id:
        return RedirectResponse(url="/", status_code=303)
        
    user_info = db_manager.get_user_info(emp_id)
    if user_info and user_info.get("status") == "disabled":
        return RedirectResponse(url="/", status_code=303)
        
    projects_json = user_info.get("projects", "[]") if user_info else "[]"
    if projects_json == "[]" or not projects_json:
        # 如果不属于任何项目，禁止发送消息
        return RedirectResponse(url="/dashboard", status_code=303)
        
    receivers = [r.strip() for r in receiver.split(",")]
    msg_ids, invalid_receivers = message_manager.send_message(
        sender=emp_id,
        receivers=receivers,
        content=content
    )
    # 发送后回到主控台（Web 端暂不展示无效接收人提示）
    return RedirectResponse(url="/dashboard", status_code=303)

@app.post("/dashboard/profile")
async def update_profile(
    nickname: str = Form(None),
    bio: str = Form(None),
    emp_id: str = Cookie(None),
    private_key: str = Cookie(None)
):
    """[新增原因]: 用户更新个人资料"""
    if not private_key or db_manager.get_user_by_key(private_key, active_only=False) != emp_id:
        return RedirectResponse(url="/", status_code=303)
        
    user_info = db_manager.get_user_info(emp_id)
    if user_info and user_info.get("status") == "disabled":
        return RedirectResponse(url="/", status_code=303)
        
    db_manager.update_user_profile(emp_id, nickname or "", bio or "")
    
    return RedirectResponse(url="/dashboard#tab-profile", status_code=303)

# ----------------- API 接口 (供 Agent 和 Client 使用) -----------------

from fastapi import Header

class MessageRequest(BaseModel):
    """发送消息的请求结构（去除sender，由Token自动解析）"""
    receiver: str
    content: str

class ConvertRequest(BaseModel):
    content: str

@app.get("/api/projects", summary="获取项目及成员列表")
async def get_projects(authorization: str = Header(None), private_key: str = Cookie(None)):
    """
    [修改原因]: 同时支持 Bearer Token 和 Cookie 认证，使 API 客户端和 Web 端均可调用 (BUG-06 修复)。
    [新增权限控制]: 只有当该员工属于某个项目时，才能拉取到该项目的信息。如果不属于任何项目，返回空列表。
    """
    # 优先使用 Bearer Token，其次使用 Cookie
    key = None
    if authorization and authorization.startswith("Bearer "):
        key = authorization.split(" ")[1]
    elif private_key:
        key = private_key

    if not key:
        raise HTTPException(status_code=401, detail="未授权")

    emp_id = db_manager.get_user_by_key(key, active_only=False)
    if not emp_id:
        raise HTTPException(status_code=401, detail="未授权")
        
    user_info = db_manager.get_user_info(emp_id)
    if user_info and user_info.get("status") == "disabled":
        raise HTTPException(status_code=403, detail="您的账号已被禁用")
        
    try:
        all_projects = db_manager.get_all_projects()
        # 仅返回该员工所在的项目
        user_projects = []
        for p in all_projects:
            if any(m.get("emp_id") == emp_id for m in p.get("members", [])):
                user_projects.append(p)
                
        return {"status": "success", "data": user_projects}
    except Exception as e:
        logger.error(f"读取组织架构失败: {e}")
        return {"status": "error", "data": []}

@app.post("/api/llm/convert", summary="大模型辅助 Markdown 转换接口")
async def convert_to_markdown(req: ConvertRequest, authorization: str = Header(None), private_key: str = Cookie(None)):
    """[修改原因]: 同时支持 Bearer Token 和 Cookie 认证 (BUG-06 修复)"""
    # 优先使用 Bearer Token，其次使用 Cookie
    key = None
    if authorization and authorization.startswith("Bearer "):
        key = authorization.split(" ")[1]
    elif private_key:
        key = private_key

    if not key:
        raise HTTPException(status_code=401, detail="未授权")

    emp_id = db_manager.get_user_by_key(key, active_only=False)
    if not emp_id:
        raise HTTPException(status_code=401, detail="未授权")
        
    user_info = db_manager.get_user_info(emp_id)
    if user_info and user_info.get("status") == "disabled":
        raise HTTPException(status_code=403, detail="您的账号已被禁用")

    api_key = os.getenv("LLM_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="服务端尚未配置 LLM_API_KEY")
        
    try:
        # [修改原因]: 按照接入文档要求配置 OpenAI 兼容客户端
        # 注意: 之前的 base_url 配置没有带最后的 / 或者是 sdk 版本问题。
        # 按照文档：base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        client = OpenAI(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        
        completion = client.chat.completions.create(
            # [修改原因]: 根据业务需求，改为使用指定版本的 qwen3.6-plus 模型
            model="qwen3.6-plus",
            messages=[
                {"role": "system", "content": "你是一个Markdown格式化专家。用户的任何输入，你都要将其转换为结构清晰、易于阅读的专业Markdown格式，不要包含任何多余的自我介绍或寒暄。只返回Markdown本身的代码。"},
                {"role": "user", "content": req.content}
            ]
        )
        
        md_content = completion.choices[0].message.content
        return {"status": "success", "data": md_content}
    except Exception as e:
        logger.error(f"大模型调用失败: {e}")
        # [修改原因]：将具体的错误抛给前端，方便调试
        raise HTTPException(status_code=500, detail=f"智能转换失败: {str(e)}")

@app.post("/api/messages/send", summary="发送消息接口")
async def send_message(req: MessageRequest, authorization: str = Header(None)):
    """
    [修改原因]: API 端现在强制要求 Header 中携带 `Authorization: Bearer <private_key>`，
    通过 Key 自动推导 sender (emp_id)，防止伪造发件人。支持群发。并拦截禁用账号。
    [新增权限控制]: 如果发送者不属于任何项目，则禁止发送消息。
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="缺少身份凭证 (Bearer Token)")
        
    private_key = authorization.split(" ")[1]
    sender_emp_id = db_manager.get_user_by_key(private_key, active_only=False)
    
    if not sender_emp_id:
        raise HTTPException(status_code=403, detail="无效的 Private Key")
        
    user_info = db_manager.get_user_info(sender_emp_id)
    if user_info and user_info.get("status") == "disabled":
        raise HTTPException(status_code=403, detail="您的账号已被禁用")

    projects_json = user_info.get("projects", "[]") if user_info else "[]"
    if projects_json == "[]" or not projects_json:
        raise HTTPException(status_code=403, detail="您不属于任何项目，无法与任何人通信")

    receivers = [r.strip() for r in req.receiver.split(",")]
    try:
        msg_ids, invalid_receivers = message_manager.send_message(
            sender=sender_emp_id,
            receivers=receivers,
            content=req.content
        )
        result = {"status": "success", "msg_ids": msg_ids, "message": "消息已成功存入数据库"}
        if invalid_receivers:
            result["invalid_receivers"] = invalid_receivers
            result["message"] = f"部分消息已发送，以下接收人不存在: {', '.join(invalid_receivers)}"
        return result
    except Exception as e:
        logger.error(f"发送消息失败: {e}")
        raise HTTPException(status_code=500, detail="消息发送失败，请检查服务器日志")

@app.get("/api/messages/receive", summary="接收消息接口")
async def receive_messages(authorization: str = Header(None)):
    """
    [修改原因]: API 收件也改为验证 Token，只有提供正确的 Key 才能看自己的收件箱。并拦截禁用账号。
    [新增权限控制]: 如果接收者不属于任何项目，则禁止拉取收件箱。
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="缺少身份凭证 (Bearer Token)")
        
    private_key = authorization.split(" ")[1]
    emp_id = db_manager.get_user_by_key(private_key, active_only=False)
    
    if not emp_id:
        raise HTTPException(status_code=403, detail="无效的 Private Key")
        
    user_info = db_manager.get_user_info(emp_id)
    if user_info and user_info.get("status") == "disabled":
        raise HTTPException(status_code=403, detail="您的账号已被禁用")

    projects_json = user_info.get("projects", "[]") if user_info else "[]"
    if projects_json == "[]" or not projects_json:
        raise HTTPException(status_code=403, detail="您不属于任何项目，无法拉取收件箱")

    try:
        messages = message_manager.get_inbox_messages(emp_id)
        return {"status": "success", "data": messages}
    except Exception as e:
        logger.error(f"读取收件箱失败: {e}")
        raise HTTPException(status_code=500, detail="收件箱读取失败")

@app.get("/api/messages/sent", summary="获取发件箱接口")
async def sent_messages(authorization: str = Header(None)):
    """
    [新增原因]: API 获取发件箱内容，并拦截禁用账号。
    [新增权限控制]: 如果发送者不属于任何项目，则禁止拉取发件箱。
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="缺少身份凭证 (Bearer Token)")
        
    private_key = authorization.split(" ")[1]
    emp_id = db_manager.get_user_by_key(private_key, active_only=False)
    
    if not emp_id:
        raise HTTPException(status_code=403, detail="无效的 Private Key")
        
    user_info = db_manager.get_user_info(emp_id)
    if user_info and user_info.get("status") == "disabled":
        raise HTTPException(status_code=403, detail="您的账号已被禁用")

    projects_json = user_info.get("projects", "[]") if user_info else "[]"
    if projects_json == "[]" or not projects_json:
        raise HTTPException(status_code=403, detail="您不属于任何项目，无法拉取发件箱")

    try:
        messages = message_manager.get_outbox_messages(emp_id)
        return {"status": "success", "data": messages}
    except Exception as e:
        logger.error(f"读取发件箱失败: {e}")
        raise HTTPException(status_code=500, detail="发件箱读取失败")

from typing import Optional

@app.get("/api")
async def api_docs(request: Request, format: Optional[str] = None):
    """
    [新增原因]: 返回 API 接口文档页面，供所有员工学习如何使用接口与其他同事协作。
    支持通过 format=markdown 参数返回纯 Markdown 格式的文档，供 AI Agent 直接读取。
    """
    if format == "markdown" or format == "md":
        md_file = os.path.join(current_dir, '..', 'templates', 'api_docs.md')
        try:
            with open(md_file, 'r', encoding='utf-8') as f:
                md_content = f.read()
            return Response(content=md_content, media_type="text/markdown; charset=utf-8")
        except Exception as e:
            logger.error(f"读取 Markdown API 文档失败: {e}")
            return Response(content="Markdown 文档加载失败", media_type="text/plain", status_code=500)
            
    return templates.TemplateResponse("api_docs.html", {"request": request, "base_url": request.base_url})
