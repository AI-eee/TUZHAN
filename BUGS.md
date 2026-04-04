# TUZHAN 协作中心 — Bug 报告

> 生成时间: 2026-04-05
> 扫描范围: 全部源码 (`src/`, `scripts/`, `config/`)

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

**修复方案**: 将所有管理员接口中 `user_info.get("emp_id") != "TZa1b2c3"` 和 `user_info.get("emp_id") != "TZzhjiac"` 的硬编码检查统一改为 `not user_info.get("is_admin")`，使数据库 `is_admin` 字段和 `admin grant/revoke` 命令真正生效。

---

### BUG-04: Message ID 截断导致碰撞风险 — ✅ 已修复

**文件**: `src/core/message_manager.py`

**修复方案**: 将 `str(uuid.uuid4())[:8]` 改为 `str(uuid.uuid4())`，使用完整 36 字符 UUID，彻底消除碰撞风险。

---

### BUG-05: 消息发送无接收人校验 — ✅ 已修复

**文件**: `src/core/message_manager.py`, `src/api/server.py`

**修复方案**: 在 `MessageManager.send_message()` 中增加 `get_user_info(receiver)` 校验，不存在的接收人将被跳过并记录警告日志。`send_message` 返回值新增 `invalid_receivers` 列表，API 端点 `/api/messages/send` 会将无效接收人信息返回给调用方。

---

### BUG-06: `/api/projects` 和 `/api/llm/convert` 使用 Cookie 认证而非 Bearer Token — ✅ 已修复

**文件**: `src/api/server.py`

**修复方案**: 两个端点改为同时支持 `Authorization: Bearer <key>` Header 和 `private_key` Cookie 认证，优先使用 Bearer Token。API 客户端和 AI Agent 现在可以通过标准 Bearer Token 正常调用这两个接口。

---

## 中 (Medium)

### BUG-07: `WorkspaceManager` 读取 `departments` 但配置文件中使用 `projects`

**文件**: `src/core/workspace_manager.py:44`

```python
departments = org_data.get('departments', [])
```

**描述**: `org_chart.yaml` 的顶层键是 `projects`，但 `WorkspaceManager.sync_workspaces()` 读取的是 `departments`。结果是 `sync_workspaces()` 永远获取空列表，不会创建任何工作区目录。

**影响**: 虽然系统已迁移到 SQLite 存储，该模块可能已不再活跃使用，但代码逻辑与配置不一致。

**修复建议**: 将 `departments` 改为 `projects`，或标注该模块为废弃代码。

---

### BUG-08: 数据库升级逻辑中 `is_admin` 列可能丢失

**文件**: `src/core/database.py:45-56, 80-84`

**描述**: `_upgrade_db()` 中，如果触发了 `username` 迁移：
1. 创建 `users_new` 表时**不包含** `is_admin` 列（第 45-56 行）
2. 删除旧表并重命名新表
3. 然后用**旧表的列列表** `columns` 来判断是否需要添加 `is_admin`（第 81 行）

如果旧表中已有 `is_admin` 列，`'is_admin' not in columns` 为 False，ALTER TABLE 被跳过。但新表根本没有 `is_admin` 列，导致该字段永久丢失。

**修复建议**: 在 `users_new` 表定义中加入 `is_admin INTEGER DEFAULT 0`，并在迁移 INSERT 语句中包含该字段。

---

### BUG-09: 裸 `except` 吞掉所有异常

**文件**: `src/api/server.py:121-122, 187-188`

```python
try:
    projects = json.loads(user_info["projects"])
except:
    pass
```

**描述**: 使用裸 `except:` 会捕获所有异常，包括 `SystemExit`、`KeyboardInterrupt`、`MemoryError` 等不应被静默忽略的异常。且 `pass` 吞掉了错误，当 `projects` JSON 数据损坏时无任何日志记录。

**修复建议**: 改为 `except (json.JSONDecodeError, TypeError):` 并记录警告日志。

---

### BUG-10: YAML 文件并发读写无锁保护

**文件**: `src/api/server.py:293-327, 342-361, 379-417, 431-446, 457-478`

**描述**: 多个管理员接口对 `org_chart.yaml` 进行读-改-写操作，且没有任何文件锁或并发控制。如果两个管理员同时操作（如同时添加项目成员），后写入的会覆盖先写入的变更，导致数据丢失。

**修复建议**: 使用文件锁（如 `fcntl.flock`）或将项目数据也迁入数据库。

---

### BUG-11: `init_data.json` 中的管理员与硬编码管理员工号不一致

**文件**: `config/init_data.json`, `src/api/server.py`

**描述**: `init_data.json` 中配置的管理员为 `TZzhjiac`（`"is_admin": true`），但 `server.py` 中硬编码的管理员工号是 `TZa1b2c3`。使用 `init_db.py` 初始化数据库后，`TZzhjiac` 虽然有 `is_admin=1` 但无法访问管理后台（因为硬编码检查不通过），而 `TZa1b2c3` 并不存在于初始化数据中。

**影响**: 全新部署后，管理员后台无法登录。

---

### BUG-12: LLM 接口报错信息泄露内部细节

**文件**: `src/api/server.py:650`

```python
raise HTTPException(status_code=500, detail=f"智能转换失败: {str(e)}")
```

**描述**: 将完整的异常信息（可能包含 API Key、内部 URL、堆栈细节等）直接返回给客户端。

**修复建议**: 生产环境中返回通用错误信息，将详细错误仅记录到服务端日志。

---

## 低 (Low)

### BUG-13: `api_client.py` 中 `.env` 路径计算错误

**文件**: `src/client/api_client.py:14-15`

```python
current_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(current_dir, '..', '..', '.env'))
```

**描述**: `api_client.py` 位于 `src/client/` 目录下，`..` 两次回到项目根目录是正确的。但如果该模块被从其他位置导入（如被安装为包），`__file__` 的路径会变化导致找不到 `.env` 文件。此为潜在问题，当前直接运行时不会触发。

---

### BUG-14: `argparse` 重复导入

**文件**: `scripts/init_db.py:6, 113`

**描述**: `argparse` 在文件开头（第 6 行）和 `__main__` 块中（第 113 行）被导入了两次。

**修复建议**: 删除第 113 行的重复导入。

---

### BUG-15: `admin.py sync` 不清空项目前的全量同步会覆盖手动设置的 private_key

**文件**: `scripts/admin.py:72-78`

**描述**: `sync_projects_to_db()` 中的 `ensure_user_exists()` 不传 `private_key` 参数。查看 `database.py:182-198`，当用户已存在时，如果 `private_key` 为 None 则不会更新 key，这是安全的。但如果用户不存在（新员工从 org_chart 同步进来），会以 `private_key=None` 创建用户，该用户将无法登录，直到管理员手动 `keygen`。

**影响**: 通过 `admin.py sync` 新增的员工不会自动获得登录凭证，需要额外执行 `keygen`。这更像是一个工作流缺陷而非代码 bug。

---

## 汇总

| 级别 | 数量 | Bug 编号 |
|------|------|----------|
| 严重 (Critical) | 2 | BUG-01, BUG-02 |
| 高 (High) | 4 | BUG-03, BUG-04, BUG-05, BUG-06 |
| 中 (Medium) | 6 | BUG-07, BUG-08, BUG-09, BUG-10, BUG-11, BUG-12 |
| 低 (Low) | 3 | BUG-13, BUG-14, BUG-15 |
| **合计** | **15** | |
