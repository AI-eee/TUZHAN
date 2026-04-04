import os
import sys
import yaml
import json
import secrets
import argparse
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
        db_url = settings.get(env, settings["development"]).get("database_url", "sqlite:///./data/prod.sqlite")
        
    db_path = db_url.replace("sqlite:///", "")
    if db_path.startswith("./"):
        db_path = os.path.join(current_dir, "..", db_path[2:])
    return os.path.abspath(db_path)

def init_database(env="production"):
    print(f"========== 开始初始化 {env.upper()} 数据库 ==========")
    db_path = get_db_path(env)
    
    # [修改原因]: 根据用户要求，如果数据库已经存在，则中止初始化操作以防覆盖。
    if os.path.exists(db_path):
        print(f"⚠️  警告: 发现数据库文件已存在于路径 -> {db_path}")
        print("⚠️  为防止覆盖或污染已有数据，初始化脚本已自动中止。")
        print("👉 如需强制重新初始化，请先手动删除该数据库文件后再运行本脚本。")
        sys.exit(0)
        
    print(f"数据库路径: {db_path}")
    
    # 1. 初始化 DatabaseManager (会自动创建表)
    db_manager = DatabaseManager(db_path)
    print("✓ 数据库及表结构初始化完成")

    # 2. 从外部 JSON 文件载入基础架构与员工
    # [修改原因]: 改用 init_data.json 让用户可以自由配置初始化数据
    init_file = os.path.join(current_dir, '..', 'config', 'init_data.json')
    if not os.path.exists(init_file):
        print(f"❌ 找不到初始化数据文件: {init_file}")
        print("👉 请先在 config 目录下创建并配置 init_data.json 文件。")
        sys.exit(1)
        
    with open(init_file, 'r', encoding='utf-8') as f:
        try:
            init_data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"❌ 初始化数据文件格式错误: {e}")
            sys.exit(1)
            
    initial_users = init_data.get('initial_users', [])
    if not initial_users:
        print("! JSON 文件中未配置 initial_users 节点，跳过初始数据导入。")
    else:
        print("\n----- 正在导入初始员工及项目信息 -----")
        credentials = []
        
        for user in initial_users:
            emp_id = user.get("emp_id")
            nickname = user.get("nickname", "")
            projects = user.get("projects", [])
            is_admin = user.get("is_admin", False)
            
            if not emp_id:
                continue
                
            # 随机生成安全的 32位 Private Key
            random_str = secrets.token_hex(16)
            key = f"sk-{random_str}"
            
            # 保证用户存在并更新项目信息
            db_manager.ensure_user_exists(
                emp_id=emp_id, 
                nickname=nickname, 
                projects_json=json.dumps(projects, ensure_ascii=False),
                private_key=key
            )
            
            # 如果配置了管理员权限则赋予
            if is_admin:
                db_manager.set_user_admin_status(emp_id, True)
                
            credentials.append((emp_id, nickname, key, is_admin))
            
        print("✓ 项目架构及人员同步完成")
        
        # 打印生成的凭证
        print("\n[重要] 以下是员工的访问凭证 (Private Key)，请妥善保管和分发：")
        for emp_id, nickname, key, is_admin in credentials:
            admin_mark = "(超级管理员)" if is_admin else ""
            print(f" - {nickname} [{emp_id}] {admin_mark}: {key}")
            
    print(f"\n========== {env.upper()} 数据库初始化完毕 ==========")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="TUZHAN 数据库初始化工具")
    parser.add_argument("--env", choices=["development", "production"], default=None, help="运行环境 (默认从 .env 读取，否则为 development)")
    
    args = parser.parse_args()
    
    # 解析环境
    env = get_env(args.env)
    
    init_database(env)
