# TUZHAN Agent协作中心 — 已修复 Bug 归档

> 此文档记录所有已修复并验证的 Bug。
> 从 `BUGS.md` 迁移至此归档，以保持主文档仅包含未修复问题。

---

## 严重 (Critical)

### BUG-01: Cookie 伪造导致任意用户身份冒充 & 管理员后台绕过 — ✅ 已修复

**文件**: `src/api/server.py`

**修复方案**: 新增 `_verify_session(emp_id, private_key)` 校验函数，在 `GET /`、`GET /dashboard`、`GET /admin/login`、`GET /admin/dashboard` 中均通过数据库验证 `private_key` 与 `emp_id` 的对应关系，伪造 Cookie 不再能绕过认证。

---

### BUG-02: Private Key 明文存储在 Cookie 中，且未设置安全属性 — ✅ 已修复

**文件**: `src/api/server.py`

**修复方案**: 所有 `set_cookie` 调用统一使用 `COOKIE_OPTS = {"httponly": True, "samesite": "Lax"}`，JavaScript 无法再通过 `document.cookie` 读取凭证，同时防御 CSRF。生产环境上线 HTTPS 后应额外加入 `secure=True`。

---

## 高 (High)

### BUG-03: 管理员权限硬编码，`is_admin` 字段形同虚设 — ✅ 已修复

**文件**: `src/api/server.py`

**修复方案**: 将所有管理员接口中硬编码检查统一改为 `not user_info.get("is_admin")`，使数据库 `is_admin` 字段和 `admin grant/revoke` 命令真正生效。

---

### BUG-04: Message ID 截断导致碰撞风险 — ✅ 已修复

**文件**: `src/core/message_manager.py`

**修复方案**: 将 `str(uuid.uuid4())[:8]` 改为 `str(uuid.uuid4())`，使用完整 36 字符 UUID，彻底消除碰撞风险。

---

### BUG-05: 邮件发送无接收人校验 — ✅ 已修复

**文件**: `src/core/message_manager.py`, `src/api/server.py`

**修复方案**: 在 `MessageManager.send_message()` 中增加 `get_user_info(receiver)` 校验，不存在的接收人将被跳过并记录警告日志。`send_message` 返回值新增 `invalid_receivers` 列表。

---

### BUG-06: `/api/projects` 和 `/api/llm/convert` 使用 Cookie 认证而非 Bearer Token — ✅ 已修复

**文件**: `src/api/server.py`

**修复方案**: 两个端点改为同时支持 `Authorization: Bearer <key>` Header 和 `private_key` Cookie 认证，优先使用 Bearer Token。

---

### BUG-16: 管理员 POST 接口缺失 `private_key` 会话校验 — ✅ 已修复

**文件**: `src/api/server.py:235-404`

**修复方案**: 新增 `_require_admin(emp_id, private_key)` 公共校验函数，所有 9 个管理员 POST/DELETE 接口均已增加双重校验。

---

### BUG-17: 已禁用用户仍可访问 Web 控制台和管理后台 — ✅ 已修复

**文件**: `src/api/server.py:70-80, 128-151, 184-230`

**修复方案**: 在 `_verify_session()` 中将 `get_user_by_key(private_key, active_only=False)` 改为 `active_only=True`，已禁用用户的会话立即失效。

---

## 中 (Medium)

### BUG-07: `WorkspaceManager` 读取 `departments` 但配置文件中使用 `projects` — ✅ 已修复

**文件**: `src/core/workspace_manager.py:44`

**修复方案**: 已将 `departments` 改为 `projects`，读取逻辑与 `org_chart.yaml` 配置一致。

---

### BUG-10: YAML 文件并发读写无锁保护 — ✅ 已修复（不再适用）

**文件**: `src/api/server.py`

**说明**: 项目已将数据全面迁移到 SQLite 数据库，`server.py` 中不再存在对 `org_chart.yaml` 的运行时写入操作。

---

### BUG-11: `init_data.json` 中的管理员与硬编码管理员工号不一致 — ✅ 已修复

**文件**: `config/init_data.json`, `src/api/server.py`

**说明**: BUG-03 修复后，所有管理员权限检查均改为基于 `is_admin` 字段，不再依赖硬编码工号。

---

### BUG-20: 邮件状态永久为 "unread"，缺少已读标记机制 — ✅ 已修复

**文件**: `src/core/database.py`, `src/api/server.py`

**修复方案**: 已采用 ACK 机制，新增独立的 `POST /api/messages/{id}/read` 接口供 AI Agent 在处理完邮件后主动标记已读。

---

## 本次批量修复 (2026-04-05)

### BUG-08: 数据库升级逻辑中 `is_admin` 列可能丢失 — ✅ 已修复

**文件**: `src/core/database.py`

**修复方案**: 在 `users_new` 表定义中加入 `is_admin INTEGER DEFAULT 0`，迁移 INSERT 中包含 `is_admin` 字段，并在表重建后重新执行 `PRAGMA table_info(users)` 刷新列列表。

---

### BUG-09: 裸 `except` 吞掉所有异常 — ✅ 已修复

**文件**: `src/api/server.py`

**修复方案**: 两处裸 `except:` 改为 `except (json.JSONDecodeError, TypeError)`，并在 dashboard 处增加警告日志记录。

---

### BUG-12: LLM 接口报错信息泄露内部细节 — ✅ 已修复

**文件**: `src/api/server.py`

**修复方案**: 返回给客户端的错误信息改为通用提示 `"智能转换失败，请稍后重试"`，详细错误仅记录在服务端日志。

---

### BUG-14: `argparse` 重复导入 — ✅ 已修复

**文件**: `scripts/init_db.py`

**修复方案**: 删除 `__main__` 块中的重复 `import argparse`。

---

### BUG-18: 管理后台「编辑身份设定」弹窗读取不存在的 `data-username` — ✅ 已修复

**文件**: `src/templates/admin_dashboard.html`

**说明**: 代码已使用 `data-nickname` 属性和 `getAttribute('data-nickname')`，此问题已不存在。

---

### BUG-19: `.env` 文件写入未做输入净化 — ✅ 已修复

**文件**: `src/api/server.py`

**修复方案**: 在写入 `.env` 前校验 `llm_api_key` 是否包含 `\n`、`\r` 或 `=`，包含则返回 400 拒绝。

---

### BUG-22: SQLite 外键约束从未启用 — ✅ 已修复

**文件**: `src/core/database.py`

**修复方案**: 在 `get_connection()` 中添加 `conn.execute("PRAGMA foreign_keys = ON")`。

---

### BUG-23: `editMemberRole` 及管理后台 onclick 拼接存在 XSS 漏洞 — ✅ 已修复

**文件**: `src/templates/admin_dashboard.html`

**修复方案**: 所有 Jinja 模板变量从 onclick 字符串拼接改为 `data-*` 属性 + `this.dataset` 读取，用户输入不再直接进入 JavaScript 字符串。

---

### BUG-25: API 端点使用 `active_only=False` 认证 — ✅ 已修复

**文件**: `src/api/server.py`

**修复方案**: 所有 API 端点和 Web 端的 `/dashboard/send`、`/dashboard/profile` 改为 `active_only=True`，移除冗余的手动 disabled 检查。登录端点保留 `active_only=False` 以返回友好的禁用提示。

---

### BUG-33: `update_user_key_by_emp_id` 未处理唯一约束冲突 — ✅ 已修复

**文件**: `src/core/database.py`

**修复方案**: 使用 `try/except sqlite3.IntegrityError` 包裹，冲突时返回 `False` 并记录警告日志。

---

### BUG-34: `save_message` 在邮件 ID 重复时异常 — ✅ 已修复

**文件**: `src/core/database.py`

**修复方案**: 使用 `try/except sqlite3.IntegrityError` 包裹，重复时返回 `False` 并记录警告日志。

---

### BUG-35: `ensure_user_exists` 更新路径中 IntegrityError 未处理 — ✅ 已修复

**文件**: `src/core/database.py`

**修复方案**: 在 `private_key` 更新语句上使用 `try/except sqlite3.IntegrityError` 包裹，冲突时记录警告但不中断其他字段更新。

---

### BUG-37: `update_user_status` 接受任意字符串 — ✅ 已修复

**文件**: `src/core/database.py`

**修复方案**: 添加 `status not in ('active', 'disabled')` 校验，不合法值抛出 `ValueError`。

---

### BUG-43: `send_message` 返回值类型注解与实际不符 — ✅ 已修复

**文件**: `src/core/message_manager.py`

**说明**: 代码中类型注解已为 `-> tuple`，此问题已不存在。

---

### BUG-46: 两个 `DOMContentLoaded` 监听器分别挂载在 `document` 和 `window` 上 — ✅ 已修复

**文件**: `src/templates/dashboard.html`

**修复方案**: 合并为单个 `document.addEventListener('DOMContentLoaded', ...)`，hash 恢复逻辑移入同一处理器。
