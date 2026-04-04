import sqlite3
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

from typing import Optional, List, Dict, Any

class DatabaseManager:
    """
    轻量级 SQLite 数据库管理器
    解决原先本地 Markdown 存储所带来的权限控制和读写并发问题。
    将原本作为文件的 Markdown 信息入库，但依旧保持 Markdown 内容格式。
    """
    def __init__(self, db_path: str):
        # sqlite:///./data/dev.sqlite -> ./data/dev.sqlite
        self.db_path = db_path.replace("sqlite:///", "")
        self._ensure_db_dir()
        self.init_tables()
        self._upgrade_db()

    def _ensure_db_dir(self):
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _upgrade_db(self):
        """[新增原因]：热更新现有的 SQLite 表结构，并执行全库 emp_id 迁移以废除 username 字段"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(users)")
            columns = [info[1] for info in cursor.fetchall()]
            
            # 如果还存在 username 字段，则说明需要进行全库迁移
            if 'username' in columns:
                # 1. 迁移 messages 表中的 sender 和 receiver (将 username 转为 emp_id)
                cursor.execute("UPDATE messages SET sender = (SELECT emp_id FROM users WHERE users.username = messages.sender) WHERE sender IN (SELECT username FROM users)")
                cursor.execute("UPDATE messages SET receiver = (SELECT emp_id FROM users WHERE users.username = messages.receiver) WHERE receiver IN (SELECT username FROM users)")
                
                # 2. 创建新的 users 表，以 emp_id 为主键，无 username
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS users_new (
                        emp_id TEXT PRIMARY KEY,
                        nickname TEXT,
                        projects TEXT DEFAULT '[]',
                        private_key TEXT UNIQUE,
                        status TEXT DEFAULT 'active',
                        identity_md TEXT,
                        bio TEXT,
                        created_at TEXT NOT NULL
                    )
                ''')
                
                # 3. 将老数据迁移到新表 (原有 username 会被作为初始 nickname)
                # 兼容旧表可能没有 status, identity_md, nickname, bio 的情况
                has_status = 'status' in columns
                has_identity = 'identity_md' in columns
                has_nickname = 'nickname' in columns
                has_bio = 'bio' in columns
                
                sel_status = "status" if has_status else "'active'"
                sel_identity = "identity_md" if has_identity else "NULL"
                sel_nickname = "COALESCE(nickname, username)" if has_nickname else "username"
                sel_bio = "bio" if has_bio else "NULL"
                
                cursor.execute(f'''
                    INSERT INTO users_new (emp_id, nickname, projects, private_key, status, identity_md, bio, created_at)
                    SELECT emp_id, {sel_nickname}, projects, private_key, {sel_status}, {sel_identity}, {sel_bio}, created_at
                    FROM users WHERE emp_id IS NOT NULL
                ''')
                
                # 4. 删除老表，重命名新表
                cursor.execute('DROP TABLE users')
                cursor.execute('ALTER TABLE users_new RENAME TO users')
                
            # [新增原因]：热更新 is_admin 字段，用于标记管理员角色
            if 'is_admin' not in columns:
                cursor.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")
                # 如果是旧的数据，给已知的 TZzhjiac 初始化赋予超管权限以防止丢失访问权
                # [修改原因]: 根据最新要求，超管工号固定为 TZzhjiac
                cursor.execute("UPDATE users SET is_admin = 1 WHERE emp_id = 'TZzhjiac'")
                
            # [新增原因]：热更新 messages 表的软删除字段
            cursor.execute("PRAGMA table_info(messages)")
            msg_columns = [info[1] for info in cursor.fetchall()]
            if 'sender_deleted' not in msg_columns:
                cursor.execute("ALTER TABLE messages ADD COLUMN sender_deleted INTEGER DEFAULT 0")
            if 'receiver_deleted' not in msg_columns:
                cursor.execute("ALTER TABLE messages ADD COLUMN receiver_deleted INTEGER DEFAULT 0")
                
            conn.commit()

    def init_tables(self):
        """初始化表结构：users 和 messages"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # messages 表：记录Markdown消息
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    sender TEXT NOT NULL,
                    receiver TEXT NOT NULL,
                    subject TEXT,
                    content TEXT,
                    status TEXT DEFAULT 'unread',
                    sender_deleted INTEGER DEFAULT 0,
                    receiver_deleted INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL
                )
            ''')
            
            # users 表：[修改原因]：增加 is_admin 字段
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    emp_id TEXT PRIMARY KEY,
                    nickname TEXT,
                    projects TEXT DEFAULT '[]',
                    private_key TEXT UNIQUE,
                    status TEXT DEFAULT 'active',
                    is_admin INTEGER DEFAULT 0,
                    identity_md TEXT,
                    bio TEXT,
                    created_at TEXT NOT NULL
                )
            ''')
            
            # [新增原因]：重构代码，彻底废弃运行时写入 yaml 的做法，将项目和成员关系完全迁移到 SQLite 数据库中。
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    description TEXT,
                    created_at TEXT NOT NULL
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS project_members (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_name TEXT NOT NULL,
                    emp_id TEXT NOT NULL,
                    role TEXT DEFAULT 'Member',
                    created_at TEXT NOT NULL,
                    UNIQUE(project_name, emp_id),
                    FOREIGN KEY (project_name) REFERENCES projects(name) ON DELETE CASCADE,
                    FOREIGN KEY (emp_id) REFERENCES users(emp_id) ON DELETE CASCADE
                )
            ''')
            
            conn.commit()
            logger.info(f"数据库表结构初始化成功: {self.db_path}")

    # -------- [新增部分]：项目和成员管理的数据库方法 --------
    def get_all_projects(self) -> list:
        """获取所有项目及其成员信息"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name, description FROM projects")
            projects = [dict(row) for row in cursor.fetchall()]
            
            for proj in projects:
                cursor.execute('''
                    SELECT pm.emp_id, pm.role, u.nickname 
                    FROM project_members pm
                    JOIN users u ON pm.emp_id = u.emp_id
                    WHERE pm.project_name = ?
                ''', (proj["name"],))
                proj["members"] = [dict(row) for row in cursor.fetchall()]
                
            return projects

    def add_project(self, name: str, description: str) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("INSERT INTO projects (name, description, created_at) VALUES (?, ?, ?)", 
                               (name, description, created_at))
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def update_project_description(self, name: str, description: str) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE projects SET description = ? WHERE name = ?", (description, name))
            conn.commit()
            return cursor.rowcount > 0

    def delete_project(self, name: str) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM projects WHERE name = ?", (name,))
            conn.commit()
            return cursor.rowcount > 0

    def add_project_member(self, project_name: str, emp_id: str, role: str) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("INSERT INTO project_members (project_name, emp_id, role, created_at) VALUES (?, ?, ?, ?)", 
                               (project_name, emp_id, role, created_at))
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def remove_project_member(self, project_name: str, emp_id: str) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM project_members WHERE project_name = ? AND emp_id = ?", (project_name, emp_id))
            conn.commit()
            return cursor.rowcount > 0

    def update_project_member_role(self, project_name: str, emp_id: str, role: str) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE project_members SET role = ? WHERE project_name = ? AND emp_id = ?", (role, project_name, emp_id))
            conn.commit()
            return cursor.rowcount > 0

    def sync_projects_to_users_json(self):
        """保持向后兼容：将 projects 表的数据同步到 users.projects 字段"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT emp_id FROM users")
            users = cursor.fetchall()
            
            for user in users:
                emp_id = user["emp_id"]
                cursor.execute("SELECT project_name as project, role FROM project_members WHERE emp_id = ?", (emp_id,))
                projs = [dict(row) for row in cursor.fetchall()]
                import json
                cursor.execute("UPDATE users SET projects = ? WHERE emp_id = ?", (json.dumps(projs, ensure_ascii=False), emp_id))
            conn.commit()
    # -----------------------------------------------------

    def get_messages_for_user(self, user: str, status: Optional[str] = None) -> list:
        """获取某个用户的收件箱列表"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if status:
                cursor.execute(
                    "SELECT * FROM messages WHERE receiver = ? AND status = ? AND receiver_deleted = 0 ORDER BY created_at DESC", 
                    (user, status)
                )
            else:
                cursor.execute(
                    "SELECT * FROM messages WHERE receiver = ? AND receiver_deleted = 0 ORDER BY created_at DESC", 
                    (user,)
                )
            return [dict(row) for row in cursor.fetchall()]

    def get_sent_messages_for_user(self, user: str) -> list:
        """获取某个用户的发件箱列表"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM messages WHERE sender = ? AND sender_deleted = 0 ORDER BY created_at DESC", 
                (user,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_all_messages(self) -> list:
        """[新增原因]：为管理员后台获取全站所有的消息，用于全局审查"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM messages ORDER BY created_at DESC")
            return [dict(row) for row in cursor.fetchall()]

    def mark_message_as_read(self, msg_id: str, receiver: str) -> bool:
        """[新增原因]：为 AI Agent 增加消息 ACK 确认机制，标记消息为已读"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE messages SET status = 'read' WHERE id = ? AND receiver = ?", 
                (msg_id, receiver)
            )
            conn.commit()
            return cursor.rowcount > 0

    def delete_message(self, msg_id: str, user: str) -> bool:
        """[新增原因]：允许用户软删除自己收发件箱的消息"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE messages 
                SET sender_deleted = CASE WHEN sender = ? THEN 1 ELSE sender_deleted END,
                    receiver_deleted = CASE WHEN receiver = ? THEN 1 ELSE receiver_deleted END
                WHERE id = ? AND (sender = ? OR receiver = ?)
                """, 
                (user, user, msg_id, user, user)
            )
            conn.commit()
            return cursor.rowcount > 0

    def get_all_users(self) -> list:
        """[新增原因]：为管理员后台获取所有的用户信息"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users ORDER BY emp_id ASC")
            return [dict(row) for row in cursor.fetchall()]

    def save_message(self, msg_id: str, sender: str, receiver: str, content: str):
        """保存发送的消息"""
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # subject 在表中虽然存在，但我们不再写入
            cursor.execute(
                "INSERT INTO messages (id, sender, receiver, content, created_at) VALUES (?, ?, ?, ?, ?)",
                (msg_id, sender, receiver, content, created_at)
            )
            conn.commit()
            
    def ensure_user_exists(self, emp_id: str, nickname: Optional[str] = None, projects_json: str = "[]", private_key: Optional[str] = None):
        """确保用户存在，支持传入包含项目和角色的 JSON 字符串及工号"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM users WHERE emp_id = ?", (emp_id,))
            if not cursor.fetchone():
                created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute(
                    "INSERT INTO users (emp_id, nickname, projects, private_key, created_at) VALUES (?, ?, ?, ?, ?)",
                    (emp_id, nickname, projects_json, private_key, created_at)
                )
                conn.commit()
            else:
                # 更新项目信息
                cursor.execute(
                    "UPDATE users SET projects = ? WHERE emp_id = ?",
                    (projects_json, emp_id)
                )
                if nickname:
                    cursor.execute(
                        "UPDATE users SET nickname = ? WHERE emp_id = ?",
                        (nickname, emp_id)
                    )
                if private_key:
                    cursor.execute(
                        "UPDATE users SET private_key = ? WHERE emp_id = ?",
                        (private_key, emp_id)
                    )
                conn.commit()

    def clear_all_user_projects(self):
        """[新增原因]: 清空所有用户的项目信息，用于同步全量项目前的重置"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET projects = '[]'")
            conn.commit()

    def get_user_info(self, emp_id: str) -> Optional[dict]:
        """获取用户的完整信息，包括其参与的项目及角色"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE emp_id = ?", (emp_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_user_by_key(self, private_key: str, active_only: bool = True) -> Optional[str]:
        """[新增原因]：通过 private_key 获取对应的员工 emp_id，用于拦截伪造身份及被禁用的账号"""
        if not private_key:
            return None
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if active_only:
                cursor.execute("SELECT emp_id FROM users WHERE private_key = ? AND status = 'active'", (private_key,))
            else:
                cursor.execute("SELECT emp_id FROM users WHERE private_key = ?", (private_key,))
            row = cursor.fetchone()
            return row["emp_id"] if row else None

    def get_user_by_nickname(self, nickname: str) -> Optional[dict]:
        """[新增原因]：通过 nickname 获取用户，用于校验昵称唯一性（忽略大小写和首尾空格）"""
        if not nickname:
            return None
        nickname = nickname.strip()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE LOWER(nickname) = LOWER(?)", (nickname,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_user_key_by_emp_id(self, emp_id: str, new_key: str) -> bool:
        """[新增原因]：为管理员提供根据工号重新生成 Private Key 的能力"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET private_key = ? WHERE emp_id = ?", (new_key, emp_id))
            conn.commit()
            return cursor.rowcount > 0

    def update_user_status(self, emp_id: str, status: str) -> bool:
        """更新用户的启用/禁用状态"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET status = ? WHERE emp_id = ?", (status, emp_id))
            conn.commit()
            return cursor.rowcount > 0

    def update_user_identity(self, emp_id: str, identity_md: str) -> bool:
        """更新用户的身份设定 (Markdown)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET identity_md = ? WHERE emp_id = ?", (identity_md, emp_id))
            conn.commit()
            return cursor.rowcount > 0

    def update_user_profile(self, emp_id: str, nickname: str, bio: str) -> bool:
        """[新增原因]: 允许用户更新个人主页的昵称和简介"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET nickname = ?, bio = ? WHERE emp_id = ?", (nickname, bio, emp_id))
            conn.commit()
            return cursor.rowcount > 0

    def set_user_admin_status(self, emp_id: str, is_admin: bool) -> bool:
        """[新增原因]: 设置或取消用户的管理员权限"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            val = 1 if is_admin else 0
            cursor.execute("UPDATE users SET is_admin = ? WHERE emp_id = ?", (val, emp_id))
            conn.commit()
            return cursor.rowcount > 0
