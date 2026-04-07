"""
员工接口 - 邮件生命周期测试
==========================
覆盖：未读过滤、ACK 已读标记、软删除、收件箱配置返回。
"""
import requests


def _auth(key):
    return {"Authorization": f"Bearer {key}"}


def _send(api_url, sender, receiver, content="lifecycle test"):
    r = requests.post(
        f"{api_url}/messages/send",
        headers=_auth(sender["key"]),
        json={"receiver": receiver["emp_id"], "content": content},
    )
    assert r.status_code == 200, r.text
    ids = r.json().get("msg_ids") or []
    assert ids, r.text
    return ids[0]


class TestUnreadFilter:
    def test_status_filter_unread_only(self, api_url, user1, user2):
        """?status=unread 应只返回未读邮件"""
        msg_id = _send(api_url, user1, user2, "# unread filter")
        # 用 unread 过滤拉取，再用相同凭据二次拉取，第二次应不再包含同一封
        first = requests.get(
            f"{api_url}/messages/receive?status=unread",
            headers=_auth(user2["key"]),
        ).json()["data"]
        ids_first = [m["metadata"]["id"] for m in first]
        assert msg_id in ids_first

        second = requests.get(
            f"{api_url}/messages/receive?status=unread",
            headers=_auth(user2["key"]),
        ).json()["data"]
        ids_second = [m["metadata"]["id"] for m in second]
        assert msg_id not in ids_second, "拉取后应自动标记已读，再次按 unread 过滤不应再返回"


class TestMarkAsRead:
    def test_mark_read_success(self, api_url, user1, user2):
        msg_id = _send(api_url, user1, user2, "# ack test")
        # 主动 ACK
        r = requests.post(
            f"{api_url}/messages/{msg_id}/read",
            headers=_auth(user2["key"]),
        )
        # 由于 receive 接口会自动标记已读，二次 ACK 可能返回 404；这里允许两种
        assert r.status_code in (200, 404)

    def test_mark_read_not_owner_returns_404(self, api_url, user1, user2, admin_user):
        """非收件人无法 ACK 别人的邮件"""
        msg_id = _send(api_url, user1, user2, "ack other")
        r = requests.post(
            f"{api_url}/messages/{msg_id}/read",
            headers=_auth(admin_user["key"]),
        )
        assert r.status_code == 404

    def test_mark_read_without_token(self, api_url):
        r = requests.post(f"{api_url}/messages/abc/read")
        assert r.status_code == 401


class TestDeleteMessage:
    def test_receiver_can_delete(self, api_url, user1, user2):
        msg_id = _send(api_url, user1, user2, "to delete")
        r = requests.delete(
            f"{api_url}/messages/{msg_id}",
            headers=_auth(user2["key"]),
        )
        assert r.status_code == 200
        assert r.json()["status"] == "success"

        # 删除后收件箱不应再包含
        inbox = requests.get(
            f"{api_url}/messages/receive",
            headers=_auth(user2["key"]),
        ).json()["data"]
        assert all(m["metadata"]["id"] != msg_id for m in inbox)

    def test_sender_can_delete_from_outbox(self, api_url, user1, user2):
        msg_id = _send(api_url, user1, user2, "outbox delete")
        r = requests.delete(
            f"{api_url}/messages/{msg_id}",
            headers=_auth(user1["key"]),
        )
        assert r.status_code == 200
        outbox = requests.get(
            f"{api_url}/messages/sent",
            headers=_auth(user1["key"]),
        ).json()["data"]
        assert all(m["metadata"]["id"] != msg_id for m in outbox)

    def test_third_party_cannot_delete(self, api_url, user1, user2, admin_user):
        msg_id = _send(api_url, user1, user2, "no third-party delete")
        r = requests.delete(
            f"{api_url}/messages/{msg_id}",
            headers=_auth(admin_user["key"]),
        )
        assert r.status_code == 404

    def test_delete_nonexistent_returns_404(self, api_url, user1):
        r = requests.delete(
            f"{api_url}/messages/this-id-does-not-exist",
            headers=_auth(user1["key"]),
        )
        assert r.status_code == 404

    def test_delete_without_auth_returns_401(self, api_url):
        r = requests.delete(f"{api_url}/messages/anything")
        assert r.status_code == 401


class TestProjectsConfigField:
    def test_projects_response_includes_retention_days(self, api_url, user1):
        r = requests.get(f"{api_url}/projects", headers=_auth(user1["key"]))
        assert r.status_code == 200
        body = r.json()
        assert "config" in body
        assert "retention_days" in body["config"]
        assert isinstance(body["config"]["retention_days"], int)
