# TUZHAN Agent邮件协作中心 — Bug 跟踪

> 最后更新: 2026-04-05
> 扫描范围: 全部源码 (`src/`, `scripts/`, `config/`, `templates/`, `static/`)
> 已修复的 Bug 请查看 [`BUGS_ARCHIVED.md`](BUGS_ARCHIVED.md)

---

# 一、必须修改

> 本次扫描中标记为「必须修改」的 Bug 已全部修复，详见归档文档。

*暂无未修复项*

---

# 二、需要确认

> 这些问题取决于项目的部署环境、使用场景或产品决策，需要你来判断是否需要修复。

---

### BUG-24: 所有 POST 表单和 AJAX 请求缺乏 CSRF 防护

**严重级别**: 高
**文件**: 所有模板文件及 `fetch()` 调用

**描述**: 整个系统中没有 CSRF Token 机制。虽然 `SameSite=Lax` 可缓解部分跨站 POST 攻击，但不能阻止所有攻击向量。

**需要确认**: 如果系统仅在内网使用且用户可信，CSRF 风险较低。如果面向公网，建议使用 `starlette-csrf` 或双提交 Cookie 模式。

---

### BUG-26: Markdown 邮件允许 `<img>` 标签导致追踪像素攻击

**严重级别**: 中
**文件**: `src/api/server.py:47, 52`

**描述**: bleach 白名单允许 `<img>` 标签及任意 `src` 属性，用户可发送包含外部图片 URL 的邮件进行追踪像素攻击。

**需要确认**: 是否需要支持外部图片？如不需要，直接从白名单中移除 `img` 标签。如需要，添加 URL 方案白名单。

---

### BUG-27: `<span style>` 允许任意 CSS 注入

**严重级别**: 中
**文件**: `src/api/server.py:55`

**描述**: bleach 白名单允许 `<span>` 携带任意 `style` 属性，恶意用户可用 CSS 覆盖整个页面。

**需要确认**: 是否需要支持自定义样式？如不需要，从 `span` 允许属性中移除 `style`。

---

### BUG-28: 邮件内容和身份设定无长度限制

**严重级别**: 中
**文件**: `src/api/server.py:301, 503-506, 449`

**描述**: `content` 和 `identity_md` 无 `max_length` 约束，用户可提交任意大载荷。LLM 转换接口将无界输入传给 OpenAI API，可能产生高额费用。

**需要确认**: 合理的最大长度是多少？建议邮件内容 50000 字符，身份设定 10000 字符。

---

### BUG-31: 开发环境绑定 `0.0.0.0`，生产环境绑定 `127.0.0.1`

**严重级别**: 中
**文件**: `config/settings.yaml`

**描述**: 开发环境绑定 `0.0.0.0`（对外暴露），生产环境绑定 `127.0.0.1`（仅本地）。如果生产环境中 Nginx 运行在不同容器，将无法连接。

**需要确认**: 生产环境的部署架构是什么？是否需要交换绑定地址？

---

### BUG-32: `org_chart.yaml` 与 `init_data.json` 不一致

**严重级别**: 中
**文件**: `config/org_chart.yaml`, `config/init_data.json`

**描述**: `init_data.json` 定义了三个项目和三个用户，但 `org_chart.yaml` 仅包含 TUZHAN 项目和一个成员。`sync` 命令会导致不完整数据，且覆盖正确的昵称。

**需要确认**: 哪个文件是权威数据源？是否需要统一两个配置文件的内容？

---

### BUG-29: 管理后台以明文显示所有用户 Private Key

**严重级别**: 中
**文件**: `src/templates/admin_dashboard.html:315`

**描述**: 所有员工的 Private Key 以明文渲染在 HTML 中，会被浏览器历史记录、浏览器插件和代理服务器记录。

**需要确认**: 管理员是否需要直接看到完整密钥？建议默认显示遮罩版本（如 `sk-****abcd`），提供切换按钮。

---

### BUG-30: LLM API Key 以明文渲染在管理后台页面

**严重级别**: 中
**文件**: `src/templates/admin_dashboard.html:474`

**描述**: LLM API Key 在页面初始加载时以明文渲染在 DOM 中。

**需要确认**: 是否可以改为服务端遮罩处理，仅发送遮罩版本到前端？

---

### BUG-42: API 文档页面无需认证即可访问

**严重级别**: 低
**文件**: `src/api/server.py:700-732`

**描述**: `GET /api?format=markdown` 返回完整 API 文档，无认证检查，暴露内部 API 结构。

**需要确认**: API 文档是否需要公开？如果仅供内部使用，建议添加认证检查。

---

### BUG-41: 管理员可重生成自己的密钥导致会话失效

**严重级别**: 低
**文件**: `src/api/server.py:279-298`

**描述**: 管理员对自己执行密钥重生成后，Cookie 中仍为旧密钥，会被"锁在门外"。

**需要确认**: 是否禁止管理员重生成自己的密钥，或者在响应中同步更新 Cookie？

---

### BUG-21: 登录和 API 接口无速率限制

**严重级别**: 低
**文件**: `src/api/server.py:94-116, 160-182, 588-626`

**描述**: 登录和 API 端点均无速率限制，可被暴力枚举或用于资源耗尽攻击。

**需要确认**: 是否需要引入速率限制？如果面向公网，强烈建议使用 `slowapi` 等库添加限制。

---

### BUG-50: CDN 依赖缺少 Subresource Integrity (SRI) 校验

**严重级别**: 中
**文件**: `src/templates/dashboard.html:8-12`

**描述**: highlight.js 和 EasyMDE 从 CDN 加载时未设置 `integrity` 属性，如果 CDN 被入侵，恶意脚本将在用户浏览器中执行。

**需要确认**: 是否将 CDN 资源改为本地托管，或添加 SRI hash？

---

### BUG-51: `data-identity` 属性中的 Markdown 内容可导致属性注入

**严重级别**: 中
**文件**: `src/templates/admin_dashboard.html:337`

**描述**: 大量 Markdown 内容直接渲染到 `data-identity` 属性中。Jinja2 的 `autoescape=True` 应该会对双引号转义，但建议验证确认。

**需要确认**: Jinja2 模板引擎是否对属性中的双引号进行了转义？

---

# 三、体验提升

> 这些改动不影响安全性和正确性，但可以提升代码质量、用户体验和可维护性。

---

### BUG-36: 数据库迁移静默丢弃无法匹配的邮件

**严重级别**: 中
**文件**: `src/core/database.py:43-44`

**描述**: `username → emp_id` 迁移中，无法匹配的邮件永久孤立且无日志记录。

**改进建议**: 为无法迁移的邮件记录警告日志。

---

### BUG-38: 发送邮件表单的接收人字段依赖 JS 填充，JS 失败时可提交空接收人

**严重级别**: 中
**文件**: `src/templates/dashboard.html:419, 798`

**改进建议**: 在服务端 `/dashboard/send` 中添加空接收人校验。

---

### BUG-39: 自定义 confirm 对话框无键盘支持和无障碍属性

**严重级别**: 中
**文件**: `src/static/js/ui.js:43-62`

**改进建议**: 添加键盘事件（Escape 取消、Enter 确认）、`role="dialog"`、`aria-modal="true"`、焦点陷阱。

---

### BUG-40: `GET /logout` 应为 POST 以防止 CSRF 注销攻击

**严重级别**: 低
**文件**: `src/api/server.py:146-152`

**改进建议**: 改为 `@app.post("/logout")`，使用表单提交。

---

### BUG-44: `switchTab` 函数从 URL hash 读取未净化的 tabId

**严重级别**: 低
**文件**: `src/templates/admin_dashboard.html:913`, `src/templates/dashboard.html:631`

**改进建议**: 使用已知 tab ID 白名单进行校验。

---

### BUG-45: `api_client.py` 的 `--env` 参数在 subparsers 之后添加

**严重级别**: 低
**文件**: `src/client/api_client.py:83, 96-98`

**改进建议**: 将 `--env` 参数移到 `add_subparsers` 之前定义。

---

### BUG-47: 密钥重生成后 Toast 通知以明文显示完整新密钥

**严重级别**: 低
**文件**: `src/templates/admin_dashboard.html:611`

**改进建议**: Toast 中仅显示遮罩版本。

---

### BUG-48: 登录表单使用 `autocomplete="off"` 阻碍密码管理器

**严重级别**: 低
**文件**: `src/templates/login.html:132`, `src/templates/admin_login.html:155`

**改进建议**: 改为 `autocomplete="current-password"`。

---

### BUG-49: 每次数据库操作都新建连接，无连接复用

**严重级别**: 低
**文件**: `src/core/database.py:28-31`

**改进建议**: 使用单实例连接或连接池，设置 WAL 模式。

---

### BUG-13: `api_client.py` 中 `.env` 路径计算方式不够健壮

**严重级别**: 低
**文件**: `src/client/api_client.py:14-15`

---

### BUG-15: `admin.py sync` 新增员工不会自动获得登录凭证

**严重级别**: 低
**文件**: `scripts/admin.py:72-78`

**改进建议**: 在 `sync` 时自动为新员工生成密钥。

---

### BUG-52: `get_env()` 和 `get_db_path()` 在多个文件中重复定义

**严重级别**: 低
**文件**: `scripts/admin.py`, `scripts/init_db.py`, `src/client/api_client.py`

**改进建议**: 提取到共享模块中统一维护。

---

### BUG-53: `.env` 文件中包含测试 API Key 且未在 `.gitignore` 中排除

**严重级别**: 低
**文件**: `.env`

**改进建议**: 将 `.env` 添加到 `.gitignore`，使用 `.env.example` 作为模板。

---

# 汇总

| 分类 | 数量 | Bug 编号 |
|------|------|----------|
| **必须修改** | 0 | *已全部修复* |
| **需要确认** | 12 | BUG-21, 24, 26, 27, 28, 29, 30, 31, 32, 41, 42, 50, 51 |
| **体验提升** | 12 | BUG-13, 15, 36, 38, 39, 40, 44, 45, 47, 48, 49, 52, 53 |
| **已修复（归档）** | 27 | BUG-01~12, 14, 16~20, 22, 23, 25, 33~35, 37, 43, 46 |
| **合计** | **51** | |
