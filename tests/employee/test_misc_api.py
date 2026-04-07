"""
其他公共/辅助接口测试
====================
覆盖：版本接口、反馈接口结构、Skill 包下载、Markdown 内容防 XSS。
"""
import requests


def _auth(key):
    return {"Authorization": f"Bearer {key}"}


class TestHealthEndpoint:
    """[v2.0.0]: 探活接口,部署/监控必备"""

    def test_health_returns_ok(self, base_url):
        r = requests.get(f"{base_url}/api/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["db"] == "ok"
        assert "env" in body


class TestVersionEndpoint:
    def test_version_returns_success(self, api_url):
        r = requests.get(f"{api_url}/version")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "success"
        assert "version" in body["data"]
        assert "content" in body["data"]


class TestFeedbackDeprecated:
    """[v2.1.0]: /api/feedback 已废弃，统一返回 410 Gone 并指引到 GitHub Issues。"""

    def test_feedback_post_returns_410(self, api_url, user1):
        r = requests.post(
            f"{api_url}/feedback",
            headers=_auth(user1["key"]),
            json={"content": "hi"},
        )
        assert r.status_code == 410
        assert "github.com/AI-eee/TUZHAN/issues" in r.json().get("detail", "")

    def test_feedback_post_unauthenticated_also_410(self, api_url):
        # 已废弃的接口无论是否带认证都直接返回 410，避免误导调用方
        r = requests.post(f"{api_url}/feedback", json={"content": "hi"})
        assert r.status_code == 410

    def test_feedback_get_returns_410(self, api_url):
        r = requests.get(f"{api_url}/feedback")
        assert r.status_code == 410


class TestSkillZip:
    def test_skill_zip_download(self, base_url):
        r = requests.get(f"{base_url}/api/tuzhan_agent_mail.zip", allow_redirects=False)
        # 项目可能未生成 zip，404 也是合法状态
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            assert r.headers.get("content-type", "").startswith("application/")
            assert len(r.content) > 0


class TestXSSSafety:
    def test_script_tag_in_message_is_sanitized_in_dashboard(self, base_url, user1, user2):
        """Markdown 中的 <script> 标签在 dashboard 渲染时必须被 bleach 清洗掉"""
        payload = "<script>window.__pwn=1</script>\n\n# safe heading"
        r = requests.post(
            f"{base_url}/api/messages/send",
            headers=_auth(user1["key"]),
            json={"receiver": user2["emp_id"], "content": payload},
        )
        assert r.status_code == 200

        # 用 user2 登录 Web 端拉取 dashboard，断言 script 标签不在响应中
        s = requests.Session()
        s.post(f"{base_url}/login", data={"private_key": user2["key"]}, allow_redirects=False)
        page = s.get(f"{base_url}/dashboard")
        assert page.status_code == 200
        assert "<script>window.__pwn" not in page.text
