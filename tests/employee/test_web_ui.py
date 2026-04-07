"""
Web UI 流程测试
==============
覆盖：登录、登出、Dashboard 发件、个人资料更新、未登录重定向。
"""
import requests


class TestRootAndDeprecation:
    """根路径行为 + v2.1.0 员工 Dashboard 冻结标记"""

    def test_root_unauthenticated_returns_login_page(self, base_url):
        r = requests.get(f"{base_url}/", allow_redirects=False)
        assert r.status_code == 200
        assert "private_key" in r.text or "登录" in r.text

    def test_root_authenticated_redirects_to_dashboard(self, base_url, user1):
        s = requests.Session()
        s.post(f"{base_url}/login", data={"private_key": user1["key"]}, allow_redirects=False)
        r = s.get(f"{base_url}/", allow_redirects=False)
        assert r.status_code == 303
        assert r.headers.get("location") == "/dashboard"

    def test_dashboard_shows_v210_deprecated_banner(self, base_url, user1):
        """[v2.1.0]: 员工 Dashboard 必须显示冻结横幅 + GitHub Issues 链接"""
        s = requests.Session()
        s.post(f"{base_url}/login", data={"private_key": user1["key"]}, allow_redirects=False)
        r = s.get(f"{base_url}/dashboard")
        assert r.status_code == 200
        assert "v2.1.0" in r.text
        assert "github.com/AI-eee/TUZHAN/issues" in r.text
        assert "冻结" in r.text

    def test_dashboard_no_longer_has_ai_convert_button(self, base_url, user1):
        """[v2.1.0]: AI 智能转换为 Markdown 按钮已撤掉"""
        s = requests.Session()
        s.post(f"{base_url}/login", data={"private_key": user1["key"]}, allow_redirects=False)
        r = s.get(f"{base_url}/dashboard")
        assert r.status_code == 200
        assert "AI 智能转换为 Markdown" not in r.text
        assert "/api/llm/convert" not in r.text


class TestLoginFlow:
    def test_login_success_sets_cookie_and_redirects(self, base_url, user1):
        s = requests.Session()
        r = s.post(
            f"{base_url}/login",
            data={"private_key": user1["key"]},
            allow_redirects=False,
        )
        assert r.status_code == 303
        assert r.headers.get("location") == "/dashboard"
        assert s.cookies.get("emp_id") == user1["emp_id"]
        assert s.cookies.get("private_key") == user1["key"]

    def test_login_invalid_key_returns_form(self, base_url):
        r = requests.post(f"{base_url}/login", data={"private_key": "sk-bogus"})
        assert r.status_code == 200
        assert "无效" in r.text

    def test_login_disabled_user_blocked(self, base_url, disabled_user):
        r = requests.post(f"{base_url}/login", data={"private_key": disabled_user["key"]})
        assert r.status_code == 200
        assert "禁用" in r.text

    def test_logout_clears_cookies(self, base_url, user1):
        s = requests.Session()
        s.post(f"{base_url}/login", data={"private_key": user1["key"]}, allow_redirects=False)
        r = s.get(f"{base_url}/logout", allow_redirects=False)
        assert r.status_code == 303
        # 再次访问 dashboard 应被踢回登录页
        r2 = s.get(f"{base_url}/dashboard", allow_redirects=False)
        assert r2.status_code == 303
        assert r2.headers.get("location") == "/"

    def test_dashboard_requires_login(self, base_url):
        r = requests.get(f"{base_url}/dashboard", allow_redirects=False)
        assert r.status_code == 303
        assert r.headers.get("location") == "/"

    def test_index_logged_in_redirects_to_dashboard(self, base_url, user1):
        s = requests.Session()
        s.post(f"{base_url}/login", data={"private_key": user1["key"]}, allow_redirects=False)
        r = s.get(f"{base_url}/", allow_redirects=False)
        assert r.status_code == 303
        assert r.headers.get("location") == "/dashboard"


class TestDashboardSend:
    def test_dashboard_send_success(self, base_url, api_url, user1, user2):
        s = requests.Session()
        s.post(f"{base_url}/login", data={"private_key": user1["key"]}, allow_redirects=False)
        r = s.post(
            f"{base_url}/dashboard/send",
            data={"receiver": user2["emp_id"], "content": "# web 表单发件"},
            allow_redirects=False,
        )
        assert r.status_code == 303
        # 确认收件箱多了一封
        inbox = requests.get(
            f"{api_url}/messages/receive",
            headers={"Authorization": f"Bearer {user2['key']}"},
        ).json()["data"]
        assert any("web 表单发件" in m["content"] for m in inbox)

    def test_dashboard_send_without_login_redirected(self, base_url, user2):
        r = requests.post(
            f"{base_url}/dashboard/send",
            data={"receiver": user2["emp_id"], "content": "no auth"},
            allow_redirects=False,
        )
        assert r.status_code == 303


class TestDashboardProfile:
    def test_update_profile_success(self, base_url, user1):
        s = requests.Session()
        s.post(f"{base_url}/login", data={"private_key": user1["key"]}, allow_redirects=False)
        r = s.post(
            f"{base_url}/dashboard/profile",
            data={"nickname": "测试员工1", "bio": "automated test bio", "retention_days": 14},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "success"

    def test_update_profile_negative_retention_normalized(self, base_url, user1):
        s = requests.Session()
        s.post(f"{base_url}/login", data={"private_key": user1["key"]}, allow_redirects=False)
        r = s.post(
            f"{base_url}/dashboard/profile",
            data={"nickname": "测试员工1", "bio": "x", "retention_days": -5},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "success"

    def test_update_profile_without_auth(self, base_url, user1):
        r = requests.post(
            f"{base_url}/dashboard/profile",
            data={"nickname": "x", "bio": "x", "retention_days": 7},
        )
        assert r.json()["status"] == "error"
