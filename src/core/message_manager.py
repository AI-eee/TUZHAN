import os
import yaml
from datetime import datetime
import logging
import uuid

# [修改原因]: 引入 SQLite 数据库管理器，替代原本本地写入 Markdown 文件的存储机制。
from core.database import DatabaseManager

logger = logging.getLogger(__name__)

class MessageManager:
    """
    消息管理器：重构后基于 SQLite 数据库进行存取，彻底抛弃通过写入工作区文件的做法。
    消息在数据库中依然保留主题、内容等核心信息，支持对外返回前端所需结构。
    遵循原则：解耦合、接口化。
    """
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def send_message(self, sender: str, receivers: list, content: str) -> list:
        """
        发送消息：将内容通过 DatabaseManager 入库。
        支持传入多个 receiver (群发)，返回生成的消息 ID 列表
        """
        msg_ids = []
        for receiver in receivers:
            receiver = receiver.strip()
            if not receiver:
                continue
                
            msg_id = str(uuid.uuid4())[:8]
            
            # 将消息写入 SQLite 数据库的 messages 表
            self.db.save_message(
                msg_id=msg_id,
                sender=sender,
                receiver=receiver,
                content=content
            )
                
            logger.info(f"消息 [{msg_id}] 已从 {sender} 发送至 {receiver} (存入SQLite数据库)")
            msg_ids.append(msg_id)
            
        return msg_ids

    def get_inbox_messages(self, receiver: str) -> list:
        """
        获取指定接收者的收件箱中的所有消息。
        从数据库中提取。
        """
        rows = self.db.get_messages_for_user(receiver)
        
        # 为了兼容之前的 API 结构（带有 metadata 等），我们需要做一次包装
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
                "filename": f"db_record_{row['id']}.md" # 伪造一个文件名给旧客户端看
            })
            
        return messages

    def get_outbox_messages(self, sender: str) -> list:
        """
        获取指定发送者的发件箱中的所有消息。
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
