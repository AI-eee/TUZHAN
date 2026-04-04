# TUZHAN 协作中心 — Bug 报告

> 生成时间: 2026-04-05
> 扫描范围: 全部源码 (`src/`, `scripts/`, `config/`, `templates/`)

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

### BUG-16: 管理员 POST 接口缺失 `private_key` 会话校验，仅凭 `emp_id` Cookie 即可操作 — ✅ 已修复

**文件**: `src/api/server.py:235-404`

**描述**: 以下所有管理员 POST 接口仅从 Cookie 中读取 `emp_id` 并查询其 `is_admin` 状态，**未校验 `private_key`**：
- `POST /admin/users/{id}/regenerate-key` (第 235 行)
- `POST /admin/users/{id}/identity` (第 264 行)
- `POST /admin/users/{id}/status` (第 283 行)
- `POST /admin/projects` (第 310 行)
- `POST /admin/projects/{name}/members` (第 329 行)
- `POST /admin/projects/{name}/description` (第 355 行)
- `DELETE /admin/projects/{name}/members/{id}` (第 371 行)
- `POST /admin/projects/{name}/members/{id}/role` (第 390 行)

与 `GET /admin/dashboard` 的双重校验（`_verify_session` + `is_admin`）不同，这些接口只检查了 `emp_id` Cookie 的 `is_admin` 字段。攻击者只需将浏览器 Cookie 中的 `emp_id` 手动改为一个已知的管理员工号（如 `TZzhjiac`），即可绕过认证执行全部管理操作（重生成密钥、禁用账号、编辑项目等），**无需知道管理员的 Private Key**。

**影响**: 任何已知管理员工号的攻击者都可以在无密钥的情况下执行所有管理员操作，等同于管理员后台完全暴露。

**修复方案**: 新增 `_require_admin(emp_id, private_key)` 公共校验函数，内部同时调用 `_verify_session` 验证会话有效性和 `is_admin` 管理员权限。所有 9 个管理员 POST/DELETE 接口均已增加 `private_key: str = Cookie(None)` 参数，并在入口处统一调用 `_require_admin()` 进行双重校验。

---

### BUG-17: 已禁用用户仍可访问 Web 控制台和管理后台 — ✅ 已修复

**文件**: `src/api/server.py:70-80, 128-151, 184-230`

**描述**: `_verify_session()` 内部调用 `get_user_by_key(private_key, active_only=False)`，即**不过滤已禁用账号**。以下页面路由在 `_verify_session` 通过后**未检查用户 `status` 是否为 `disabled`**：

- `GET /` (第 88 行)：已禁用用户被重定向到 `/dashboard` 而非登录页
- `GET /dashboard` (第 128-151 行)：已禁用用户可正常查看控制台、收发件箱、项目信息
- `GET /admin/login` (第 153-158 行)：已禁用的管理员仍可跳转至管理后台
- `GET /admin/dashboard` (第 184-230 行)：已禁用的管理员仍可查看全站数据

相比之下，API 端（`/api/messages/send`、`/api/messages/receive` 等）正确地在 `_verify_session` 之后单独检查了 `status == "disabled"`，但 Web 端遗漏了。

**影响**: 管理员通过后台禁用某账号后，该用户只要浏览器中仍保留有效 Cookie，就可以继续使用 Web 控制台的全部功能，禁用操作形同虚设。

**修复方案**: 在 `_verify_session()` 中将 `get_user_by_key(private_key, active_only=False)` 改为 `active_only=True`。所有依赖 `_verify_session` 的 Web 路由（`GET /`、`GET /dashboard`、`GET /admin/login`、`GET /admin/dashboard`）以及 `_require_admin()` 均自动受益，已禁用用户的会话立即失效。登录和 API 端点不受影响，因为它们各自独立调用 `get_user_by_key(active_only=False)` 并手动检查 disabled 状态以返回友好的错误提示。

---

## 中 (Medium)

### BUG-07: `WorkspaceManager` 读取 `departments` 但配置文件中使用 `projects` — ✅ 已修复

**文件**: `src/core/workspace_manager.py:44`

**修复方案**: 已将 `departments` 改为 `projects`，读取逻辑与 `org_chart.yaml` 配置一致。

---

### BUG-08: 数据库升级逻辑中 `is_admin` 列可能丢失

**文件**: `src/core/database.py:45-56, 82-84`

**描述**: `_upgrade_db()` 中，如果触发了 `username` 迁移：
1. 创建 `users_new` 表时**不包含** `is_admin` 列（第 47-57 行）
2. 删除旧表并重命名新表
3. 然后用**旧表的列列表** `columns` 来判断是否需要添加 `is_admin`（第 83 行）

如果旧表中已有 `is_admin` 列，`'is_admin' not in columns` 为 False，ALTER TABLE 被跳过。但新表根本没有 `is_admin` 列，导致该字段永久丢失。

**修复建议**: 在 `users_new` 表定义中加入 `is_admin INTEGER DEFAULT 0`，并在迁移 INSERT 语句中包含该字段。

---

### BUG-09: 裸 `except` 吞掉所有异常

**文件**: `src/api/server.py:139, 205`

```python
try:
    projects = json.loads(user_info["projects"])
except:
    pass
```

**描述**: 使用裸 `except:` 会捕获所有异常，包括 `SystemExit`、`KeyboardInterrupt`、`MemoryError` 等不应被静默忽略的异常。且 `pass` 吞掉了错误，当 `projects` JSON 数据损坏时无任何日志记录。此问题在两处出现：第 139 行（用户控制台）和第 205 行（管理员后台）。

**修复建议**: 改为 `except (json.JSONDecodeError, TypeError):` 并记录警告日志。

---

### BUG-10: YAML 文件并发读写无锁保护 — ✅ 已修复（不再适用）

**文件**: `src/api/server.py`

**说明**: 项目已将数据全面迁移到 SQLite 数据库，`server.py` 中不再存在对 `org_chart.yaml` 的运行时写入操作。SQLite 自身提供了文件锁机制，此问题不再适用。

---

### BUG-11: `init_data.json` 中的管理员与硬编码管理员工号不一致 — ✅ 已修复

**文件**: `config/init_data.json`, `src/api/server.py`

**说明**: BUG-03 修复后，所有管理员权限检查均改为基于 `is_admin` 字段，不再依赖硬编码工号。`init_data.json` 中 `TZzhjiac` 配置的 `"is_admin": true` 现在可以正确生效。

---

### BUG-12: LLM 接口报错信息泄露内部细节

**文件**: `src/api/server.py:586`

```python
raise HTTPException(status_code=500, detail=f"智能转换失败: {str(e)}")
```

**描述**: 将完整的异常信息（可能包含 API Key、内部 URL、堆栈细节等）直接返回给客户端。

**修复建议**: 生产环境中返回通用错误信息，将详细错误仅记录到服务端日志。

---

### BUG-18: 管理后台「编辑身份设定」弹窗读取不存在的 `data-username` 属性导致显示 "null"

**文件**: `src/templates/admin_dashboard.html:794`

```javascript
const username = btnElement.getAttribute('data-username');
```

**描述**: `openIdentityModal()` 函数从按钮元素读取 `data-username` 属性，但按钮上实际定义的属性是 `data-nickname`（第 476 行）：
```html
<button ... data-emp="{{ u.emp_id }}" data-nickname="{{ u.nickname }}" data-identity="{{ u.identity_md or '' }}" ...>
```

由于 `data-username` 不存在，`getAttribute('data-username')` 返回 `null`，导致：
1. 弹窗标题显示为 `编辑身份设定: null (TZxxx)`
2. 默认模板中姓名显示为 `null`

**影响**: 管理员首次为员工编辑身份设定时，弹窗中的员工姓名显示为 "null"，需要手动修正模板中的名称。

**修复建议**: 将 `btnElement.getAttribute('data-username')` 改为 `btnElement.getAttribute('data-nickname')`。

---

### BUG-19: `.env` 文件写入未做输入净化，可注入任意环境变量

**文件**: `src/api/server.py:418-437`

```python
with open(env_file, 'w', encoding='utf-8') as f:
    for line in lines:
        if line.startswith("LLM_API_KEY="):
            f.write(f"LLM_API_KEY={req.llm_api_key}\n")
            ...
```

**描述**: 管理员通过 `POST /admin/config/llm-key` 提交的 `llm_api_key` 值未经过任何验证和净化，直接拼接写入 `.env` 文件。如果提交的值包含换行符（如 `fake-key\nSECRET_TOKEN=hacked`），则可向 `.env` 中注入任意环境变量。下次服务重启时，注入的变量会被 `load_dotenv()` 加载到进程环境中。

**影响**: 拥有管理员权限的用户可覆盖系统任意环境变量（如 `TUZHAN_ENV`），影响系统行为。结合 BUG-16（管理员接口缺乏 session 校验），此风险进一步放大。

**修复建议**: 对 `llm_api_key` 进行验证——拒绝包含换行符 `\n`、`\r` 或等号 `=` 的输入。

---

### BUG-20: 消息状态永久为 "unread"，缺少已读标记机制

**文件**: `src/core/database.py`, `src/api/server.py`

**描述**: `messages` 表中 `status` 字段默认值为 `'unread'`，管理后台也渲染了 "已读/未读" 的 UI（`admin_dashboard.html:572-576`）。但整个系统中不存在任何将消息标记为 `'read'` 的接口或逻辑：
- `DatabaseManager` 类中没有 `mark_as_read` 方法
- 没有 API 端点支持更新消息状态
- 用户在 Web 端查看收件箱后不会触发状态变更

**影响**: 管理员后台的 "已读/未读" 状态永远显示为 "未读"，该功能形同虚设，且可能误导管理员认为所有消息均未被查阅。

**修复建议**: 在 `DatabaseManager` 中新增 `mark_messages_as_read(receiver)` 方法，并在 `GET /dashboard` 和 `GET /api/messages/receive` 中调用，或提供独立的 `POST /api/messages/read` 接口。

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

**文件**: `scripts/init_db.py:6, 112`

**描述**: `argparse` 在文件开头（第 6 行）和 `__main__` 块中（第 112 行）被导入了两次。

**修复建议**: 删除第 112 行的重复导入。

---

### BUG-15: `admin.py sync` 新增员工不会自动获得登录凭证

**文件**: `scripts/admin.py:72-78`

**描述**: `sync_projects_to_db()` 中的 `ensure_user_exists()` 不传 `private_key` 参数。当用户不存在（新员工从 org_chart 同步进来），会以 `private_key=None` 创建用户，该用户将无法登录，直到管理员手动 `keygen`。

**影响**: 通过 `admin.py sync` 新增的员工不会自动获得登录凭证，需要额外执行 `keygen`。这更像是一个工作流缺陷而非代码 bug。

---

### BUG-21: 登录和 API 接口无速率限制，可被暴力破解

**文件**: `src/api/server.py:94-116, 160-182, 588-626`

**描述**: 以下端点接受 Private Key 作为身份凭证，但均未实施任何速率限制（Rate Limiting）或账户锁定机制：
- `POST /login`（用户登录）
- `POST /admin/login`（管理员登录）
- `POST /api/messages/send`（API Bearer Token 认证）
- `GET /api/messages/receive`（API Bearer Token 认证）

攻击者可以对这些端点进行高速暴力枚举 `sk-` 开头的密钥。虽然密钥空间为 `16^32`（128 bit），理论上暴力破解不现实，但缺少速率限制仍属于安全最佳实践的缺失，且可能导致服务器资源被大量恶意请求消耗（DoS 效果）。

**修复建议**: 使用 FastAPI 中间件或 `slowapi` 等库为登录和 API 端点添加速率限制（如每 IP 每分钟 10 次登录尝试），并在多次失败后返回 `429 Too Many Requests`。

---

## 汇总

| 级别 | 数量 | Bug 编号 |
|------|------|----------|
| 严重 (Critical) | 2 | BUG-01 ✅, BUG-02 ✅ |
| 高 (High) | 6 | BUG-03 ✅, BUG-04 ✅, BUG-05 ✅, BUG-06 ✅, BUG-16 ✅, BUG-17 ✅ |
| 中 (Medium) | 6 | BUG-07 ✅, BUG-08, BUG-09, BUG-10 ✅, BUG-11 ✅, BUG-12, BUG-18, BUG-19, BUG-20 |
| 低 (Low) | 3 | BUG-13, BUG-14, BUG-15, BUG-21 |
| **合计** | **21** | 已修复: 10 / 未修复: 11 |
