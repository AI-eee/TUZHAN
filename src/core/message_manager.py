import os
import yaml
from datetime import datetime
import logging
import uuid
from typing import Optional

# [修改原因]: 引入 SQLite 数据库管理器，替代原本本地写入 Markdown 文件的存储机制。
from core.database import DatabaseManager

logger = logging.getLogger(__name__)

class MessageManager:
    """
    邮件管理器：重构后基于 SQLite 数据库进行存取，彻底抛弃通过写入工作区文件的做法。
    邮件在数据库中依然保留主题、内容等核心信息，支持对外返回前端所需结构。
    遵循原则：解耦合、接口化。
    """
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def send_message(self, sender: str, receivers: list, content: str, require_same_project: bool = False) -> tuple:
        """
        发送邮件：将内容通过 DatabaseManager 入库。
        支持传入多个 receiver (群发)，返回生成的邮件 ID 列表。
        [修改原因]: 增加接收人校验，防止向不存在的用户发送邮件 (BUG-05 修复)
        [修改原因]: 增加 require_same_project 参数，以支持跨项目通信的限制。
        """
        msg_ids = []
        invalid_receivers = []
        
        # 提取发送者的项目列表（如果需要校验同项目）
        sender_proj_names = set()
        if require_same_project:
            sender_info = self.db.get_user_info(sender)
            if sender_info and sender_info.get("projects"):
                import json
                try:
                    sender_projs = json.loads(sender_info["projects"])
                    sender_proj_names = {p.get("project") for p in sender_projs}
                except:
                    pass

        for receiver in receivers:
            receiver = receiver.strip()
            if not receiver:
                continue

            # 校验接收人是否存在于数据库中
            receiver_info = self.db.get_user_info(receiver)
            if not receiver_info:
                invalid_receivers.append(receiver)
                continue

            # 校验是否同项目（如果是发给自己，则免除校验）
            if require_same_project and receiver != sender:
                r_proj_names = set()
                if receiver_info.get("projects"):
                    import json
                    try:
                        r_projs = json.loads(receiver_info["projects"])
                        r_proj_names = {p.get("project") for p in r_projs}
                    except:
                        pass
                
                if not sender_proj_names.intersection(r_proj_names):
                    logger.warning(f"接收人 {receiver} 不在发送者 {sender} 的任何项目组中，已拦截")
                    invalid_receivers.append(receiver)
                    continue

            msg_id = str(uuid.uuid4())
            
            # 将邮件写入 SQLite 数据库的 messages 表
            self.db.save_message(
                msg_id=msg_id,
                sender=sender,
                receiver=receiver,
                content=content
            )
                
            logger.info(f"邮件 [{msg_id}] 已从 {sender} 发送至 {receiver} (存入SQLite数据库)")
            msg_ids.append(msg_id)

        if invalid_receivers:
            logger.warning(f"以下接收人不存在，已跳过: {invalid_receivers}")

        return msg_ids, invalid_receivers

    def get_inbox_messages(self, receiver: str, status: Optional[str] = None) -> list:
        """
        获取指定接收者的收件箱中的所有邮件。
        从数据库中提取。支持按 status 过滤。
        [修改原因]: 根据用户要求，改为拉取时自动将未读邮件标记为已读，提高操作效率。
        """
        rows = self.db.get_messages_for_user(receiver, status)
        
        # 为了兼容之前的 API 结构（带有 metadata 等），我们需要做一次包装
        messages = []
        for row in rows:
            # 自动标记已读并更新返回状态
            msg_status = row["status"]
            if msg_status == "unread":
                self.mark_message_as_read(row["id"], receiver)
                msg_status = "read"

            messages.append({
                "metadata": {
                    "id": row["id"],
                    "sender": row["sender"],
                    "receiver": row["receiver"],
                    "timestamp": row["created_at"],
                    "status": msg_status
                },
                "content": row["content"],
                "filename": f"db_record_{row['id']}.md" # 伪造一个文件名给旧客户端看
            })
            
        return messages

    def mark_message_as_read(self, msg_id: str, receiver: str) -> bool:
        """
        标记邮件为已读（ACK）。
        """
        success = self.db.mark_message_as_read(msg_id, receiver)
        if success:
            logger.info(f"邮件 [{msg_id}] 已被 {receiver} 标记为已读")
        return success

    def delete_message(self, msg_id: str, user: str) -> bool:
        """
        [新增原因]: 支持删除邮件功能
        删除邮件。
        """
        success = self.db.delete_message(msg_id, user)
        if success:
            logger.info(f"邮件 [{msg_id}] 已被 {user} 删除")
        return success

    def get_outbox_messages(self, sender: str) -> list:
        """
        获取指定发送者的发件箱中的所有邮件。
        从数据库中提取。
        """
        rows = self.db.get_sent_messages_for_user(sender)
        
        messages = []
        for row in rows:
            messages.append({
                "metadata": {
                    "id": row["id"],
                    "sender": row["sender"],
                    "receiver": row["receiver"],
                    "timestamp": row["created_at"],
                    "status": row["status"]
                },
                "content": row["content"],
                "filename": f"db_record_{row['id']}.md"
            })
            
        return messages
