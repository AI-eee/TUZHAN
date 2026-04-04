import sqlite3
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

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
                # 如果是旧的数据，给已知的 TZa1b2c3 初始化赋予超管权限以防止丢失访问权
                cursor.execute("UPDATE users SET is_admin = 1 WHERE emp_id = 'TZa1b2c3'")
                
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
            
            conn.commit()
            logger.info(f"数据库表结构初始化成功: {self.db_path}")

    def get_messages_for_user(self, user: str) -> list:
        """获取某个用户的收件箱列表"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM messages WHERE receiver = ? ORDER BY created_at DESC", 
                (user,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_sent_messages_for_user(self, user: str) -> list:
        """获取某个用户的发件箱列表"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM messages WHERE sender = ? ORDER BY created_at DESC", 
                (user,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_all_messages(self) -> list:
        """[新增原因]：为管理员后台获取全站所有的消息，用于全局审查"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM messages ORDER BY created_at DESC")
            return [dict(row) for row in cursor.fetchall()]

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
            
    def ensure_user_exists(self, emp_id: str, nickname: str = None, projects_json: str = "[]", private_key: str = None):
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

    def get_user_info(self, emp_id: str) -> dict:
        """获取用户的完整信息，包括其参与的项目及角色"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE emp_id = ?", (emp_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_user_by_key(self, private_key: str, active_only: bool = True) -> str:
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
