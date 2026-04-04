import os
import sys
import uuid
import secrets
import string
import yaml
import json
from dotenv import load_dotenv

# 将 src 目录加入环境变量以便能够正确引用 core 模块
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, "..", "src"))

# [修改原因]: 加载 .env 环境变量
load_dotenv(os.path.join(current_dir, "..", ".env"))

from core.database import DatabaseManager

def get_env(override_env=None):
    """如果命令行未指定环境，优先从 .env 读取"""
    if override_env:
        return override_env
    return os.getenv("TUZHAN_ENV", "development")

def get_db_path(env="development"):
    env = get_env(env)
    settings_file = os.path.join(current_dir, '..', 'config', 'settings.yaml')
    with open(settings_file, 'r', encoding='utf-8') as f:
        settings = yaml.safe_load(f)
        db_url = settings.get(env, settings["development"]).get("database_url", "sqlite:///./data/dev.sqlite")
        
    db_path = db_url.replace("sqlite:///", "")
    if db_path.startswith("./"):
        db_path = os.path.join(current_dir, "..", db_path[2:])
    return os.path.abspath(db_path)

def sync_projects_to_db(env="development"):
    """
    [修改原因]: 读取 org_chart.yaml，将其中的 Project 信息和员工角色(Role)同步到数据库的 projects 和 project_members 表中
    """
    db_path = get_db_path(env)
    db_manager = DatabaseManager(db_path)
    
    org_file = os.path.join(current_dir, '..', 'config', 'org_chart.yaml')
    with open(org_file, 'r', encoding='utf-8') as f:
        org_data = yaml.safe_load(f)
        
    projects = org_data.get('projects', [])
    
    # 收集用户信息
    user_nicknames = {}
    for proj in projects:
        proj_name = proj.get("name")
        proj_desc = proj.get("description", "")
        
        # 添加项目
        db_manager.add_project(proj_name, proj_desc)
        # 更新项目描述（如果项目已存在）
        db_manager.update_project_description(proj_name, proj_desc)
        
        for member in proj.get("members", []):
            nickname = member.get("nickname")
            role = member.get("role", "Member")
            emp_id = member.get("emp_id")
            
            if not emp_id:
                continue
            
            if nickname:
                user_nicknames[emp_id] = nickname
                
            # 确保用户存在
            db_manager.ensure_user_exists(emp_id=emp_id, nickname=nickname)
            
            # 添加项目成员
            db_manager.add_project_member(proj_name, emp_id, role)
            # 更新成员角色（如果已存在）
            db_manager.update_project_member_role(proj_name, emp_id, role)
            
    # 同步到旧的 JSON 字段以保持兼容性
    db_manager.sync_projects_to_users_json()
        
    print(f"\n[{env.upper()} 环境] 组织架构(Projects)及工号信息已成功同步到数据库！\n")

def generate_key_for_user(emp_id: str, env="development"):
    db_path = get_db_path(env)
    db_manager = DatabaseManager(db_path)
    
    # [修改原因]: 生成 sk- 加 32位加密字符串
    random_str = secrets.token_hex(16)
    key = f"sk-{random_str}"
    
    # 查找该用户是否已有项目数据和昵称，避免覆盖
    user_info = db_manager.get_user_info(emp_id)
    projects_json = user_info["projects"] if user_info and "projects" in user_info else "[]"
    nickname = user_info["nickname"] if user_info and "nickname" in user_info else ""
    
    # 将密钥写入数据库并绑定给用户
    db_manager.ensure_user_exists(
        emp_id=emp_id, 
        nickname=nickname,
        projects_json=projects_json, 
        private_key=key
    )
    
    print(f"\n[{env.upper()} 环境] 已为工号 '{emp_id}' 生成并绑定 Private Key:")
    print(f"--> {key}\n")
    print("请将此 Key 分发给该员工或将其配置到 Agent 的环境变量中。")

def create_unique_emp_id(env="development"):
    """
    [新增原因]: 生成一个全新的不重复的随机工号 (TZ + 6位随机字符串)
    并将该工号注册进数据库，供后续分配。
    """
    db_path = get_db_path(env)
    db_manager = DatabaseManager(db_path)
    
    # 获取现有所有用户工号，用于查重
    existing_users = db_manager.get_all_users()
    existing_ids = {u['emp_id'] for u in existing_users}
    
    # 允许的字符集 (大小写字母 + 数字)
    charset = string.ascii_letters + string.digits
    
    while True:
        # 生成 6 位随机字符串
        random_str = ''.join(secrets.choice(charset) for _ in range(6))
        new_emp_id = f"TZ{random_str}"
        
        # 确保不会发生极小概率的碰撞
        if new_emp_id not in existing_ids:
            break
            
    # 将新的工号存入数据库 (初始化空信息)
    db_manager.ensure_user_exists(emp_id=new_emp_id)
    
    print(f"\n[{env.upper()} 环境] 成功生成全局唯一的全新员工编号:")
    print(f"--> {new_emp_id}\n")
    print("您可以将此编号填入系统用于新增员工。")

def toggle_admin_status(emp_id: str, action: str, env="development"):
    """
    [新增原因]: 赋予或撤销某位员工的超管权限
    """
    db_path = get_db_path(env)
    db_manager = DatabaseManager(db_path)
    
    user_info = db_manager.get_user_info(emp_id)
    if not user_info:
        print(f"\n[{env.upper()} 环境] 错误：找不到工号为 {emp_id} 的员工！")
        return
        
    is_admin = True if action == "grant" else False
    success = db_manager.set_user_admin_status(emp_id, is_admin)
    
    if success:
        status_text = "赋予" if is_admin else "撤销"
        print(f"\n[{env.upper()} 环境] 成功{status_text}工号 {emp_id} 的超级管理员权限！\n")
    else:
        print(f"\n[{env.upper()} 环境] 权限变更失败，可能是状态未发生改变。\n")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="TUZHAN 账号与架构管理工具")
    subparsers = parser.add_subparsers(dest="command", help="可用命令: sync, keygen, new_emp_id, admin")
    
    # 同步组织架构命令
    sync_parser = subparsers.add_parser("sync", help="同步 org_chart.yaml 中的项目架构到数据库")
    sync_parser.add_argument("--env", choices=["development", "production"], default=None, help="运行环境 (默认从 .env 读取)")
    
    # 生成密钥命令
    keygen_parser = subparsers.add_parser("keygen", help="为指定工号生成一串独立的 Private Key")
    keygen_parser.add_argument("emp_id", help="需要生成密钥的员工工号 (如: TZ000002)")
    keygen_parser.add_argument("--env", choices=["development", "production"], default=None, help="运行环境 (默认从 .env 读取)")
    
    # [新增原因]: 生成新工号命令
    new_id_parser = subparsers.add_parser("new_emp_id", help="生成一个全局唯一且不会重复的随机员工编号")
    new_id_parser.add_argument("--env", choices=["development", "production"], default=None, help="运行环境 (默认从 .env 读取)")

    # [新增原因]: 管理员权限控制命令
    admin_parser = subparsers.add_parser("admin", help="赋予或撤销员工的超级管理员权限")
    admin_parser.add_argument("action", choices=["grant", "revoke"], help="grant: 赋予权限, revoke: 撤销权限")
    admin_parser.add_argument("emp_id", help="员工工号")
    admin_parser.add_argument("--env", choices=["development", "production"], default=None, help="运行环境 (默认从 .env 读取)")
    
    args = parser.parse_args()

    # 解析环境
    env = get_env(args.env if hasattr(args, 'env') else None)
    
    if args.command == "sync":
        sync_projects_to_db(env)
    elif args.command == "keygen":
        generate_key_for_user(args.emp_id, env)
    elif args.command == "new_emp_id":
        create_unique_emp_id(env)
    elif args.command == "admin":
        toggle_admin_status(args.emp_id, args.action, env)
    else:
        parser.print_help()