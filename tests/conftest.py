"""
TUZHAN 测试公共 Fixtures
========================
所有测试共享的 pytest fixtures：测试数据库、TestClient、测试用户和项目。
使用 FastAPI TestClient 进行测试，无需启动服务器。
"""
import os
import sys
import json
import tempfile
import pytest

# 将 src 加入 sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src_dir = os.path.join(project_root, "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# 设置测试环境变量（必须在 import server 之前）
os.environ["TUZHAN_ENV"] = "development"
os.environ["LLM_API_KEY"] = "sk-test-llm-key-for-testing"


@pytest.fixture(scope="session")
def test_db_path():
    """创建一个临时的测试数据库文件"""
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    tmp.close()
    yield tmp.name
    os.unlink(tmp.name)


@pytest.fixture(scope="session")
def db_manager(test_db_path):
    """初始化测试数据库"""
    from core.database import DatabaseManager
    db = DatabaseManager(test_db_path)
    return db


@pytest.fixture(scope="session")
def setup_test_data(db_manager):
    """
    填充测试数据：
    - 普通员工 emp_user1 / emp_user2（属于同一项目，可互相通信）
    - 无项目员工 emp_noproj（不属于任何项目）
    - 被禁用员工 emp_disabled
    - 管理员 emp_admin
    """
    data = {
        "user1_emp_id": "TZtestUser1",
        "user1_key": "sk-testuser1key000000000000000001",
        "user2_emp_id": "TZtestUser2",
        "user2_key": "sk-testuser2key000000000000000002",
        "noproj_emp_id": "TZnoProject",
        "noproj_key": "sk-noprojectkey0000000000000003",
        "disabled_emp_id": "TZdisabled1",
        "disabled_key": "sk-disabledkey00000000000000004",
        "admin_emp_id": "TZtestAdmin",
        "admin_key": "sk-testadminkey0000000000000005",
        "project_name": "TestProject",
    }

    # 创建用户
    db_manager.ensure_user_exists(data["user1_emp_id"], "测试员工1", "[]", data["user1_key"])
    db_manager.ensure_user_exists(data["user2_emp_id"], "测试员工2", "[]", data["user2_key"])
    db_manager.ensure_user_exists(data["noproj_emp_id"], "无项目员工", "[]", data["noproj_key"])
    db_manager.ensure_user_exists(data["disabled_emp_id"], "被禁用员工", "[]", data["disabled_key"])
    db_manager.ensure_user_exists(data["admin_emp_id"], "管理员", "[]", data["admin_key"])

    # 禁用账号
    db_manager.update_user_status(data["disabled_emp_id"], "disabled")

    # 设置管理员
    db_manager.set_user_admin_status(data["admin_emp_id"], True)

    # 创建项目并添加成员
    db_manager.add_project(data["project_name"], "用于自动化测试的项目")
    db_manager.add_project_member(data["project_name"], data["user1_emp_id"], "Engineer")
    db_manager.add_project_member(data["project_name"], data["user2_emp_id"], "Engineer")
    db_manager.add_project_member(data["project_name"], data["admin_emp_id"], "Admin")

    # 同步 projects JSON 到 users 表
    db_manager.sync_projects_to_users_json()

    return data


def _cookie_header(cookies: dict) -> str:
    """将 dict 转为 Cookie header 字符串"""
    return "; ".join(f"{k}={v}" for k, v in cookies.items())


@pytest.fixture(scope="session")
def app(test_db_path, setup_test_data):
    """配置好测试数据库的 FastAPI app 实��"""
    from core.database import DatabaseManager
    from core.message_manager import MessageManager

    test_db = DatabaseManager(test_db_path)
    test_mm = MessageManager(test_db)

    import api.server as server_module
    server_module.db_manager = test_db
    server_module.message_manager = test_mm
    return server_module.app


@pytest.fixture(scope="session")
def client(app):
    """
    创建 FastAPI TestClient，���入测试数据库。
    follow_redirects=False 使得重定向测试可以正常断言。
    """
    from fastapi.testclient import TestClient
    with TestClient(app, follow_redirects=False) as c:
        yield c


# ---- 便捷 fixtures ----

@pytest.fixture(scope="session")
def user1(setup_test_data):
    """普通员工1（有项目）"""
    return {
        "emp_id": setup_test_data["user1_emp_id"],
        "key": setup_test_data["user1_key"],
    }


@pytest.fixture(scope="session")
def user2(setup_test_data):
    """普通员工2（有项目）"""
    return {
        "emp_id": setup_test_data["user2_emp_id"],
        "key": setup_test_data["user2_key"],
    }


@pytest.fixture(scope="session")
def noproj_user(setup_test_data):
    """无项目员工"""
    return {
        "emp_id": setup_test_data["noproj_emp_id"],
        "key": setup_test_data["noproj_key"],
    }


@pytest.fixture(scope="session")
def disabled_user(setup_test_data):
    """被禁用员工"""
    return {
        "emp_id": setup_test_data["disabled_emp_id"],
        "key": setup_test_data["disabled_key"],
    }


@pytest.fixture(scope="session")
def admin_user(setup_test_data):
    """管理员"""
    return {
        "emp_id": setup_test_data["admin_emp_id"],
        "key": setup_test_data["admin_key"],
    }


@pytest.fixture(scope="session")
def project_name(setup_test_data):
    return setup_test_data["project_name"]
