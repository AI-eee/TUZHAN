"""
员工接口 - 消息收发测试
========================
测试 Agent/员工通过 API 发送和接收 Markdown 消息的完整流程：
- 发送消息
- 接收消息（收件箱）
- 查看已发送消息（发件箱）
- 群发消息
- 错误场景（无效收件人、无项目、被禁用等）
"""
import pytest


class TestSendMessage:
    """POST /api/messages/send"""

    def test_send_message_success(self, client, user1, user2):
        """员工应能成功发送消息给同项目成员"""
        resp = client.post(
            "/api/messages/send",
            headers={"Authorization": f"Bearer {user1['key']}"},
            json={
                "receiver": user2["emp_id"],
                "content": "# 测试消息\n\n这是一条自动化测试发送的 Markdown 消息。",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert len(data["msg_ids"]) == 1

    def test_send_to_multiple_receivers(self, client, user1, user2, admin_user):
        """支持逗号分隔的多接收人群发"""
        receivers = f"{user2['emp_id']},{admin_user['emp_id']}"
        resp = client.post(
            "/api/messages/send",
            headers={"Authorization": f"Bearer {user1['key']}"},
            json={
                "receiver": receivers,
                "content": "# 群发测试\n\n这条消息群发给两个人。",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert len(data["msg_ids"]) == 2

    def test_send_to_invalid_receiver(self, client, user1):
        """发送给不存在的用户应返回 invalid_receivers"""
        resp = client.post(
            "/api/messages/send",
            headers={"Authorization": f"Bearer {user1['key']}"},
            json={
                "receiver": "TZ_NOT_EXIST_USER",
                "content": "这条消息发不出去",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "invalid_receivers" in data
        assert "TZ_NOT_EXIST_USER" in data["invalid_receivers"]

    def test_send_mixed_valid_and_invalid_receivers(self, client, user1, user2):
        """混合有效和无效收件人时，有效的应成功，无效的应被标记"""
        resp = client.post(
            "/api/messages/send",
            headers={"Authorization": f"Bearer {user1['key']}"},
            json={
                "receiver": f"{user2['emp_id']},TZ_GHOST_USER",
                "content": "部分有效的群发测试",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["msg_ids"]) == 1
        assert "TZ_GHOST_USER" in data["invalid_receivers"]

    def test_send_without_token_returns_401(self, client, user2):
        """未携带 Token 发送消息应返回 401"""
        resp = client.post(
            "/api/messages/send",
            json={"receiver": user2["emp_id"], "content": "no auth"},
        )
        assert resp.status_code == 401

    def test_noproj_user_cannot_send(self, client, noproj_user, user1):
        """不属于任何项目的员工不能发送消息"""
        resp = client.post(
            "/api/messages/send",
            headers={"Authorization": f"Bearer {noproj_user['key']}"},
            json={"receiver": user1["emp_id"], "content": "我没有项目"},
        )
        assert resp.status_code == 403

    def test_disabled_user_cannot_send(self, client, disabled_user, user1):
        """被禁用的员工不能发送消息"""
        resp = client.post(
            "/api/messages/send",
            headers={"Authorization": f"Bearer {disabled_user['key']}"},
            json={"receiver": user1["emp_id"], "content": "我被禁用了"},
        )
        assert resp.status_code == 403

    def test_send_markdown_content_preserved(self, client, user1, user2):
        """发送的 Markdown 内容应完整保留"""
        md_content = "## 标题\n\n- 列表项1\n- 列表项2\n\n```python\nprint('hello')\n```"
        resp = client.post(
            "/api/messages/send",
            headers={"Authorization": f"Bearer {user1['key']}"},
            json={"receiver": user2["emp_id"], "content": md_content},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"


class TestReceiveMessage:
    """GET /api/messages/receive"""

    def test_receive_inbox(self, client, user2):
        """员工应能获取自己的收件箱"""
        resp = client.get(
            "/api/messages/receive",
            headers={"Authorization": f"Bearer {user2['key']}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert isinstance(data["data"], list)
        assert len(data["data"]) > 0

    def test_inbox_message_structure(self, client, user2):
        """收件箱消息应包含正确的 metadata 和 content 结构"""
        resp = client.get(
            "/api/messages/receive",
            headers={"Authorization": f"Bearer {user2['key']}"},
        )
        msg = resp.json()["data"][0]
        assert "metadata" in msg
        assert "content" in msg
        assert "filename" in msg

        metadata = msg["metadata"]
        assert "id" in metadata
        assert "sender" in metadata
        assert "receiver" in metadata
        assert "timestamp" in metadata
        assert "status" in metadata

    def test_receive_without_token_returns_401(self, client):
        """未携带 Token 获取收件箱应返回 401"""
        resp = client.get("/api/messages/receive")
        assert resp.status_code == 401

    def test_noproj_user_cannot_receive(self, client, noproj_user):
        """不属于任何项目的员工不能拉取收件箱"""
        resp = client.get(
            "/api/messages/receive",
            headers={"Authorization": f"Bearer {noproj_user['key']}"},
        )
        assert resp.status_code == 403

    def test_disabled_user_cannot_receive(self, client, disabled_user):
        """被禁用的员工不能拉取收件箱"""
        resp = client.get(
            "/api/messages/receive",
            headers={"Authorization": f"Bearer {disabled_user['key']}"},
        )
        assert resp.status_code == 403


class TestSentMessages:
    """GET /api/messages/sent"""

    def test_get_sent_messages(self, client, user1):
        """员工应能获取自己的发件箱"""
        resp = client.get(
            "/api/messages/sent",
            headers={"Authorization": f"Bearer {user1['key']}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert isinstance(data["data"], list)
        assert len(data["data"]) > 0

    def test_sent_message_shows_correct_sender(self, client, user1):
        """发件箱中的消息 sender 应为自己"""
        resp = client.get(
            "/api/messages/sent",
            headers={"Authorization": f"Bearer {user1['key']}"},
        )
        for msg in resp.json()["data"]:
            assert msg["metadata"]["sender"] == user1["emp_id"]

    def test_sent_without_token_returns_401(self, client):
        """未携带 Token 获取发件箱应返回 401"""
        resp = client.get("/api/messages/sent")
        assert resp.status_code == 401

    def test_noproj_user_cannot_get_sent(self, client, noproj_user):
        """不属于任何项目的员工不能拉取发件箱"""
        resp = client.get(
            "/api/messages/sent",
            headers={"Authorization": f"Bearer {noproj_user['key']}"},
        )
        assert resp.status_code == 403
