# [修改原因]: 兼容低版本 Python 中的 `str | None` 类型注解
from __future__ import annotations
from fastapi import FastAPI, HTTPException, Request, Form, Response, Cookie, Query, Header
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import os
import yaml
import logging
from typing import Optional
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
    # [修改原因]: 启用 fenced-code-blocks 才能识别代码块，启用 tables 等增强 Markdown 体验。
    # 增加 highlightjs-lang 禁用默认的 Pygments，方便前端统一接管语法高亮
    html = markdown2.markdown(text, extras=["fenced-code-blocks", "highlightjs-lang", "tables", "break-on-newline", "strike"])
    # 2. 清洗 HTML
    allowed_tags = list(bleach.ALLOWED_TAGS) + [
        'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'br', 'pre', 'code', 
        'blockquote', 'hr', 'img', 'table', 'thead', 'tbody', 'tr', 'th', 'td', 'del', 'span'
    ]
    # [修改原因]: 允许 class 属性以便前端 Highlight.js 根据 class 名(如 language-python) 高亮
    allowed_attrs = {
        **bleach.ALLOWED_ATTRIBUTES, 
        'img': ['src', 'alt', 'title'],
        'code': ['class'],
        'pre': ['class'],
        'span': ['class', 'style'],
        'th': ['align'],
        'td': ['align']
    }
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

# [新增原因]: 自动初始化 TUZHAN 协作中心专属 AI Agent 身份和项目
def _init_tuzhan_identity():
    tuzhan_emp_id = "TUZHAN"
    tuzhan_user = db_manager.get_user_info(tuzhan_emp_id)
    if not tuzhan_user:
        import secrets
        # [修改原因]: 优先从环境变量读取TUZHAN专用身份凭证，方便跨环境访问和拉取反馈
        tuzhan_key = os.getenv("TUZHAN_AGENT_KEY", f"sk-{secrets.token_hex(16)}")
        db_manager.ensure_user_exists(
            emp_id=tuzhan_emp_id,
            nickname="TUZHAN",
            projects_json='[{"project": "TUZHAN", "role": "AI Agent"}]',
            private_key=tuzhan_key
        )
        db_manager.add_project("TUZHAN", "TUZHAN 协作中心本身的 Project")
        db_manager.add_project_member("TUZHAN", tuzhan_emp_id, "AI Agent")
        db_manager.sync_projects_to_users_json()
        logger.info(f"成功初始化 TUZHAN 专属身份, private_key: {tuzhan_key}")

_init_tuzhan_identity()

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
        except (json.JSONDecodeError, TypeError) as e:
            # [修改原因]: 捕获具体异常并记录日志，避免裸 except 吞掉所有错误 (BUG-09 修复)
            logger.warning(f"解析用户 {emp_id} 的项目 JSON 失败: {e}")
            
    messages = message_manager.get_inbox_messages(emp_id)
    sent_messages = message_manager.get_outbox_messages(emp_id)
    
    # 获取所有用户，用于映射工号和昵称
    all_users = db_manager.get_all_users()

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "current_emp_id": emp_id,
        "user_info": user_info,
        "all_users": all_users,
        "projects": projects,
        "messages": messages,
        "sent_messages": sent_messages,
        "active_page": "dashboard",
        "is_admin": user_info.get("is_admin", False) if user_info else False,
    })

@app.get("/admin/login", response_class=HTMLResponse)
async def admin_login_page(request: Request, emp_id: str = Cookie(None), private_key: str = Cookie(None), admin_logged_in: str = Cookie(None)):
    """[新增原因]: 单独的管理员登录页面"""
    if admin_logged_in == "true" and _verify_session(emp_id, private_key):
        # [修改原因]: 增加对 is_admin 的二次校验，防止产生无限重定向循环 (BUG修复)
        user_info = db_manager.get_user_info(emp_id)
        if user_info and user_info.get("is_admin"):
            return RedirectResponse(url="/admin/dashboard", status_code=303)
        else:
            response = templates.TemplateResponse("admin_login.html", {"request": request})
            response.delete_cookie("admin_logged_in")
            return response
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
    
    # [修改原因]: 不再在此处全量拉取消息，改为提供初始第一页数据及分页元信息，由前端 Ajax 接管
    # 保持向后兼容或初始渲染，根据需求修改每页拉取 50 条
    limit = 50
    all_messages = db_manager.get_all_messages(limit=limit, offset=0)
    total_messages_count = db_manager.get_messages_total_count()
    
    # 将 projects JSON 字符串反序列化供模板渲染
    for u in all_users:
        if u.get("projects"):
            try:
                u["projects_list"] = json.loads(u["projects"])
            except (json.JSONDecodeError, TypeError):
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
        "total_messages_count": total_messages_count,
        "messages_per_page": limit,
        "system_config": system_config,
        "org_projects": org_projects,
        "active_page": "admin",
        "is_admin": True,
    })

@app.get("/api/admin/messages", summary="管理后台获取全量消息分页数据")
async def api_admin_messages(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    emp_id: str = Cookie(None),
    private_key: str = Cookie(None),
    admin_logged_in: str = Cookie(None)
):
    """
    [新增原因]: 供管理员后台前端进行消息分页 Ajax 请求使用。
    需提供严格的身份校验确保仅超管可访问。
    """
    if not _verify_session(emp_id, private_key) or admin_logged_in != "true":
        raise HTTPException(status_code=401, detail="未授权")

    user_info = db_manager.get_user_info(emp_id)
    if not user_info or not user_info.get("is_admin"):
        raise HTTPException(status_code=403, detail="无管理员权限")
        
    offset = (page - 1) * limit
    messages = db_manager.get_all_messages(limit=limit, offset=offset)
    total_count = db_manager.get_messages_total_count()
    
    return {
        "status": "success",
        "data": {
            "messages": messages,
            "total_count": total_count,
            "page": page,
            "limit": limit
        }
    }

from api.admin_routes import register_admin_routes
register_admin_routes(app, db_manager, _require_admin, current_dir)

@app.post("/dashboard/send")
async def dashboard_send(
    request: Request,
    receiver: str = Form(...),
    content: str = Form(...),
    emp_id: str = Cookie(None),
    private_key: str = Cookie(None)
):
    """Web端发消息处理，增加对 Key 的校验及群发支持"""
    # [修改原因]: 改为 active_only=True，已禁用用户直接拒绝，无需再手动检查 status (BUG-25 修复)
    if not private_key or db_manager.get_user_by_key(private_key, active_only=True) != emp_id:
        return RedirectResponse(url="/", status_code=303)

    user_info = db_manager.get_user_info(emp_id)
        
    projects_json = user_info.get("projects", "[]") if user_info else "[]"
    if projects_json == "[]" or not projects_json:
        # 如果不属于任何项目，禁止发送消息
        return RedirectResponse(url="/dashboard", status_code=303)
        
    receivers = [r.strip() for r in receiver.split(",")]
    msg_ids, invalid_receivers = message_manager.send_message(
        sender=emp_id,
        receivers=receivers,
        content=content,
        require_same_project=True
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
    # [修改原因]: 改为 active_only=True (BUG-25 修复)
    if not private_key or db_manager.get_user_by_key(private_key, active_only=True) != emp_id:
        return {"status": "error", "detail": "未授权"}

    user_info = db_manager.get_user_info(emp_id)
        
    if nickname is not None:
        nickname = nickname.strip()
        existing = db_manager.get_user_by_nickname(nickname)
        if existing and existing["emp_id"] != emp_id:
            return {"status": "error", "detail": "该昵称已被使用，请换一个以方便分辨"}
            
    db_manager.update_user_profile(emp_id, nickname or "", bio or "")
    
    return {"status": "success"}

# ----------------- API 接口 (供 Agent 和 Client 使用) -----------------

@app.get("/api/tuzhan_workspace_skill.zip")
async def download_workspace_skill():
    """
    [新增原因]: 允许用户或 AI Agent 快速下载重构并通用化的 workspace skill 压缩包
    便于快速调度本地 API 进行测试或集成。
    """
    script_path = os.path.join(current_dir, "..", "..", "scripts", "tuzhan_workspace_skill.zip")
    if not os.path.exists(script_path):
        raise HTTPException(status_code=404, detail="tuzhan_workspace_skill.zip not found.")
    return FileResponse(
        path=script_path, 
        filename="tuzhan_workspace_skill.zip",
        media_type="application/zip"
    )

from fastapi import Header

class MessageRequest(BaseModel):
    """发送消息的请求结构（去除sender，由Token自动解析）"""
    receiver: str
    content: str

class ConvertRequest(BaseModel):
    content: str

class FeedbackRequest(BaseModel):
    content: str

@app.post("/api/feedback", summary="发送反馈给 TUZHAN 协作中心")
async def send_feedback(req: FeedbackRequest, authorization: str = Header(None)):
    """
    [新增原因]: 提供超级短路径接口，允许任何AI Agent便捷地发送反馈建议，协助TUZHAN自我迭代。
    [修改原因]: 移除"必须属于某个项目"的限制，确保所有人（包括无项目人员）都能给 TUZHAN 提反馈。
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="缺少身份凭证 (Bearer Token)")
        
    private_key = authorization.split(" ")[1]
    sender_emp_id = db_manager.get_user_by_key(private_key, active_only=True)

    if not sender_emp_id:
        raise HTTPException(status_code=403, detail="无效的 Private Key 或账号已被禁用")

    # 允许任何人向 TUZHAN 发送反馈，不再校验是否在项目组中
    try:
        msg_ids, _ = message_manager.send_message(
            sender=sender_emp_id,
            receivers=["TUZHAN"],
            content=req.content
        )
        return {
            "status": "success",
            "msg_ids": msg_ids,
            "message": "感谢您的反馈，TUZHAN将会根据您的建议持续迭代！"
        }
    except Exception as e:
        logger.error(f"发送反馈失败: {e}")
        raise HTTPException(status_code=500, detail="发送反馈失败")

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

    # [修改原因]: 改为 active_only=True，已禁用用户直接拒绝 (BUG-25 修复)
    emp_id = db_manager.get_user_by_key(key, active_only=True)
    if not emp_id:
        raise HTTPException(status_code=401, detail="未授权或账号已被禁用")

    user_info = db_manager.get_user_info(emp_id)
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

    # [修改原因]: 改为 active_only=True (BUG-25 修复)
    emp_id = db_manager.get_user_by_key(key, active_only=True)
    if not emp_id:
        raise HTTPException(status_code=401, detail="未授权或账号已被禁用")

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
            # [修改原因]: 修复大模型会在遇到提问或项目名称时瞎编内容的bug。修改提示词，严格限制模型只是一个纯粹的Markdown转换工具，不回答问题或扩展内容。
            messages=[
                {"role": "system", "content": "你是一个纯粹的Markdown文本格式化工具。你的唯一任务是将用户的输入文本重新排版为结构清晰、易于阅读的Markdown格式。你绝对不能理解、回答、解释或扩展用户输入的内容。即使用户在提问（如'你是什么模型'）或要求介绍某事物（如'介绍一下TUVE项目'），你也只能将用户的原话进行Markdown排版，绝不能编造任何回答或介绍。不要包含任何多余的自我介绍或寒暄，只返回Markdown本身的代码。"},
                {"role": "user", "content": req.content}
            ]
        )
        
        md_content = completion.choices[0].message.content
        return {"status": "success", "data": md_content}
    except Exception as e:
        # [修改原因]: 详细错误仅记录在服务端日志，不暴露给客户端 (BUG-12 修复)
        logger.error(f"大模型调用失败: {e}")
        raise HTTPException(status_code=500, detail="智能转换失败，请稍后重试")

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
    # [修改原因]: 改为 active_only=True (BUG-25 修复)
    sender_emp_id = db_manager.get_user_by_key(private_key, active_only=True)

    if not sender_emp_id:
        raise HTTPException(status_code=403, detail="无效的 Private Key 或账号已被禁用")

    user_info = db_manager.get_user_info(sender_emp_id)
    projects_json = user_info.get("projects", "[]") if user_info else "[]"
    if projects_json == "[]" or not projects_json:
        raise HTTPException(status_code=403, detail="您不属于任何项目，无法与任何人通信")

    receivers = [r.strip() for r in req.receiver.split(",")]
    try:
        msg_ids, invalid_receivers = message_manager.send_message(
            sender=sender_emp_id,
            receivers=receivers,
            content=req.content,
            require_same_project=True
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
async def receive_messages(authorization: str = Header(None), status: Optional[str] = Query(None)):
    """
    [修改原因]: API 收件也改为验证 Token，只有提供正确的 Key 才能看自己的收件箱。并拦截禁用账号。
    [新增权限控制]: 如果接收者不属于任何项目，则禁止拉取收件箱。
    [修改原因]: 支持按 status 过滤（例如 ?status=unread），满足 AI Agent 增量拉取需求。
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="缺少身份凭证 (Bearer Token)")
        
    private_key = authorization.split(" ")[1]
    # [修改原因]: 改为 active_only=True (BUG-25 修复)
    emp_id = db_manager.get_user_by_key(private_key, active_only=True)

    if not emp_id:
        raise HTTPException(status_code=403, detail="无效的 Private Key 或账号已被禁用")

    user_info = db_manager.get_user_info(emp_id)
    projects_json = user_info.get("projects", "[]") if user_info else "[]"
    if projects_json == "[]" or not projects_json:
        raise HTTPException(status_code=403, detail="您不属于任何项目，无法拉取收件箱")

    try:
        messages = message_manager.get_inbox_messages(emp_id, status=status)
        return {"status": "success", "data": messages}
    except Exception as e:
        logger.error(f"读取收件箱失败: {e}")
        raise HTTPException(status_code=500, detail="收件箱读取失败")

@app.post("/api/messages/{msg_id}/read", summary="标记消息为已读接口")
async def mark_message_read(msg_id: str, authorization: str = Header(None)):
    """
    [新增原因]: AI Agent 处理完消息后主动 ACK 确认（防止消息丢失，科学做法）。
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="缺少身份凭证 (Bearer Token)")
        
    private_key = authorization.split(" ")[1]
    emp_id = db_manager.get_user_by_key(private_key, active_only=True)
    
    if not emp_id:
        raise HTTPException(status_code=403, detail="无效或已禁用的身份凭证")

    try:
        success = message_manager.mark_message_as_read(msg_id, emp_id)
        if success:
            return {"status": "success", "message": "消息已标记为已读"}
        else:
            raise HTTPException(status_code=404, detail="找不到对应的未读消息或权限不足")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"标记消息已读失败: {e}")
        raise HTTPException(status_code=500, detail="服务器内部错误")

@app.delete("/api/messages/{msg_id}", summary="删除消息")
async def delete_message(msg_id: str, private_key: str = Cookie(None), authorization: str = Header(None)):
    """
    [新增原因]: 允许用户通过 Web 端或 API 端删除自己收发件箱中的消息。
    """
    key = None
    if authorization and authorization.startswith("Bearer "):
        key = authorization.split(" ")[1]
    elif private_key:
        key = private_key

    if not key:
        raise HTTPException(status_code=401, detail="未授权")

    emp_id = db_manager.get_user_by_key(key, active_only=False)
    if not emp_id:
        raise HTTPException(status_code=403, detail="无效的凭证")

    user_info = db_manager.get_user_info(emp_id)
    if user_info and user_info.get("status") == "disabled":
        raise HTTPException(status_code=403, detail="您的账号已被禁用")

    try:
        success = message_manager.delete_message(msg_id, emp_id)
        if success:
            return {"status": "success", "message": "删除成功"}
        else:
            raise HTTPException(status_code=404, detail="找不到对应的消息或权限不足")
    except Exception as e:
        logger.error(f"删除消息失败: {e}")
        raise HTTPException(status_code=500, detail="服务器内部错误")

@app.get("/api/messages/sent", summary="获取发件箱接口")
async def sent_messages(authorization: str = Header(None)):
    """
    [新增原因]: API 获取发件箱内容，并拦截禁用账号。
    [新增权限控制]: 如果发送者不属于任何项目，则禁止拉取发件箱。
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="缺少身份凭证 (Bearer Token)")
        
    private_key = authorization.split(" ")[1]
    # [修改原因]: 改为 active_only=True (BUG-25 修复)
    emp_id = db_manager.get_user_by_key(private_key, active_only=True)

    if not emp_id:
        raise HTTPException(status_code=403, detail="无效的 Private Key 或账号已被禁用")

    user_info = db_manager.get_user_info(emp_id)
    projects_json = user_info.get("projects", "[]") if user_info else "[]"
    if projects_json == "[]" or not projects_json:
        raise HTTPException(status_code=403, detail="您不属于任何项目，无法拉取发件箱")

    try:
        messages = message_manager.get_outbox_messages(emp_id)
        return {"status": "success", "data": messages}
    except Exception as e:
        logger.error(f"读取发件箱失败: {e}")
        raise HTTPException(status_code=500, detail="发件箱读取失败")

@app.get("/api")
async def api_docs(request: Request, format: Optional[str] = None, emp_id: str = Cookie(None), private_key: str = Cookie(None)):
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

    # 尝试获取用户信息以显示共享导航栏
    user_info = None
    current_emp_id = None
    is_admin = False
    if _verify_session(emp_id, private_key):
        current_emp_id = emp_id
        user_info = db_manager.get_user_info(emp_id)
        is_admin = user_info.get("is_admin", False) if user_info else False

    return templates.TemplateResponse("api_docs.html", {
        "request": request,
        "base_url": request.base_url,
        "current_emp_id": current_emp_id,
        "user_info": user_info,
        "active_page": "api_docs",
        "is_admin": is_admin,
    })
