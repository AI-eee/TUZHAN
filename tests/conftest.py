"""
TUZHAN 测试公共 Fixtures
========================
所有测试共享的 pytest fixtures：读取当前环境配置，连接真实数据库，打真实服务器。
运行前请确保对应环境的服务器已启动（如 python -m src.main）。

用法：
    # 测试员工接口
    python3 -m pytest tests/employee/ -v

    # 测试管理员接口
    python3 -m pytest tests/admin/ -v

    # 全部测试
    python3 -m pytest tests/employee/ tests/admin/ -v
"""
import os
import sys
import json
import pytest
import yaml
import requests
from dotenv import load_dotenv

# 将 src 加入 sys.path（用于直接 import database 模块来准备测试数据）
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src_dir = os.path.join(project_root, "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# 加载 .env
load_dotenv(os.path.join(project_root, ".env"))


def _load_base_url():
    """从 settings.yaml 读取当前环境的 client_base_url"""
    env = os.getenv("TUZHAN_ENV", "development")
    settings_path = os.path.join(project_root, "config", "settings.yaml")
    with open(settings_path, "r", encoding="utf-8") as f:
        settings = yaml.safe_load(f)
    return settings.get(env, settings["development"]).get("client_base_url", "http://127.0.0.1:8888")


def _load_db_path():
    """从 settings.yaml 读取当前环境的数据库路径"""
    env = os.getenv("TUZHAN_ENV", "development")
    settings_path = os.path.join(project_root, "config", "settings.yaml")
    with open(settings_path, "r", encoding="utf-8") as f:
        settings = yaml.safe_load(f)
    db_url = settings.get(env, settings["development"]).get("database_url", "sqlite:///./data/dev.sqlite")
    db_path = db_url.replace("sqlite:///", "")
    if db_path.startswith("./"):
        db_path = os.path.join(project_root, db_path[2:])
    return os.path.abspath(db_path)


# ---------- Fixtures ----------

@pytest.fixture(scope="session")
def base_url():
    """当前环境的服务器地址，如 http://127.0.0.1:8888"""
    url = _load_base_url()
    # 启动前先确认服务器可达
    try:
        requests.get(url, timeout=3)
    except requests.ConnectionError:
        pytest.exit(
            f"\n\n❌ 无法连接到服务器 {url}\n"
            f"   请先启动服务器: python -m src.main\n",
            returncode=1,
        )
    return url


@pytest.fixture(scope="session")
def api_url(base_url):
    """API 前缀地址，如 http://127.0.0.1:8888/api"""
    return f"{base_url}/api"


@pytest.fixture(scope="session")
def db_manager():
    """连接当前环境的真实数据库"""
    from core.database import DatabaseManager
    return DatabaseManager(_load_db_path())


@pytest.fixture(scope="session")
def setup_test_data(db_manager):
    """
    在真实数据库中准备测试数据。
    测试结束后自动清理。

    创建的测试用户：
    - user1 / user2: 普通员工，属于 _TestProject，可互相通信
    - noproj: 无项目员工
    - disabled: 被禁用员工
    - admin: 管理员，属于 _TestProject
    """
    data = {
        "user1_emp_id": "TZ_test_u1",
        "user1_key": "sk-testu1key00000000000000000001",
        "user2_emp_id": "TZ_test_u2",
        "user2_key": "sk-testu2key00000000000000000002",
        "noproj_emp_id": "TZ_test_np",
        "noproj_key": "sk-testnpkey00000000000000000003",
        "disabled_emp_id": "TZ_test_ds",
        "disabled_key": "sk-testdskey00000000000000000004",
        "admin_emp_id": "TZ_test_ad",
        "admin_key": "sk-testadkey00000000000000000005",
        "user3_emp_id": "TZ_test_u3",
        "user3_key": "sk-testu3key00000000000000000006",
        "project_name": "_TestProject",
        "project2_name": "_TestProject2",
    }

    # 创建用户
    db_manager.ensure_user_exists(data["user1_emp_id"], "测试员工1", "[]", data["user1_key"])
    db_manager.ensure_user_exists(data["user2_emp_id"], "测试员工2", "[]", data["user2_key"])
    db_manager.ensure_user_exists(data["noproj_emp_id"], "无项目员工", "[]", data["noproj_key"])
    db_manager.ensure_user_exists(data["disabled_emp_id"], "被禁用员工", "[]", data["disabled_key"])
    db_manager.ensure_user_exists(data["admin_emp_id"], "测试管理员", "[]", data["admin_key"])
    db_manager.ensure_user_exists(data["user3_emp_id"], "测试员工3", "[]", data["user3_key"])

    # 设置状态
    db_manager.update_user_status(data["user1_emp_id"], "active")
    db_manager.update_user_status(data["user2_emp_id"], "active")
    db_manager.update_user_status(data["noproj_emp_id"], "active")
    db_manager.update_user_status(data["disabled_emp_id"], "disabled")
    db_manager.update_user_status(data["admin_emp_id"], "active")
    db_manager.update_user_status(data["user3_emp_id"], "active")
    db_manager.set_user_admin_status(data["admin_emp_id"], True)

    # 创建测试项目并添加成员
    db_manager.add_project(data["project_name"], "自动化测试专用项目（可安全删除）")
    db_manager.add_project_member(data["project_name"], data["user1_emp_id"], "Engineer")
    db_manager.add_project_member(data["project_name"], data["user2_emp_id"], "Engineer")
    db_manager.add_project_member(data["project_name"], data["admin_emp_id"], "Admin")

    db_manager.add_project(data["project2_name"], "自动化测试专用项目2（可安全删除）")
    db_manager.add_project_member(data["project2_name"], data["user3_emp_id"], "Engineer")

    db_manager.sync_projects_to_users_json()

    yield data

    # ---- 清理测试数据 ----
    _cleanup_test_data(db_manager, data)


def _cleanup_test_data(db, data):
    """清理所有以 TZ_test_ 开头的测试用户、_Test 和 ProjectToDelete 开头的项目、以及相关邮件"""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        # 清理邮件
        cursor.execute("DELETE FROM messages WHERE sender LIKE 'TZ_test_%' OR receiver LIKE 'TZ_test_%'")
        # 清理项目成员
        cursor.execute("DELETE FROM project_members WHERE project_name LIKE '_Test%' OR project_name LIKE 'ProjectToDelete%'")
        # 清理项目
        cursor.execute("DELETE FROM projects WHERE name LIKE '_Test%' OR name LIKE 'ProjectToDelete%'")
        # 清理用户
        cursor.execute("DELETE FROM users WHERE emp_id LIKE 'TZ_test_%' OR emp_id = 'TZtmpDisable' OR nickname = 'TestNewUser'")
        conn.commit()


# ---- 便捷 fixtures ----

@pytest.fixture(scope="session")
def user1(setup_test_data):
    """普通员工1（有项目）"""
    return {"emp_id": setup_test_data["user1_emp_id"], "key": setup_test_data["user1_key"]}


@pytest.fixture(scope="session")
def user2(setup_test_data):
    """普通员工2（有项目）"""
    return {"emp_id": setup_test_data["user2_emp_id"], "key": setup_test_data["user2_key"]}


@pytest.fixture(scope="session")
def user3(setup_test_data):
    """普通员工3（有项目，属于 _TestProject2）"""
    return {"emp_id": setup_test_data["user3_emp_id"], "key": setup_test_data["user3_key"]}

@pytest.fixture(scope="session")
def noproj_user(setup_test_data):
    """无项目员工"""
    return {"emp_id": setup_test_data["noproj_emp_id"], "key": setup_test_data["noproj_key"]}


@pytest.fixture(scope="session")
def disabled_user(setup_test_data):
    """被禁用员工"""
    return {"emp_id": setup_test_data["disabled_emp_id"], "key": setup_test_data["disabled_key"]}


@pytest.fixture(scope="session")
def admin_user(setup_test_data):
    """管理员"""
    return {"emp_id": setup_test_data["admin_emp_id"], "key": setup_test_data["admin_key"]}


@pytest.fixture(scope="session")
def project_name(setup_test_data):
    return setup_test_data["project_name"]


@pytest.fixture(scope="session")
def admin_session(base_url, admin_user):
    """已登录的管理员 requests.Session（带 Cookie）"""
    s = requests.Session()
    s.post(f"{base_url}/admin/login", data={"private_key": admin_user["key"]}, allow_redirects=False)
    return s
