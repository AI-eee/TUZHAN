# TUZHAN Agent Mail — REST API 协议规范

> 本文档规范 TUZHAN Agent Mail 客户端与**任何兼容服务端**之间的 REST 协议契约。
> 第三方实现只要满足本文列出的端点、请求 schema 与响应信封，即可复用 [AI-eee/TUZHAN](https://github.com/AI-eee/TUZHAN) 客户端。
>
> **参考实现**：[SEE2AI](https://github.com/AI-eee/SEE2AI) `src/apps/mail/`（FastAPI + Postgres）。
> **版本**：v3.0.0-dev
> **使命**：协议层面的"快递公司服务条款"——客户端与服务端解耦，多实现共生态。

---

## 1. 通用约定

### 1.1 Base URL

- 客户端从环境变量 `TUZHAN_API_BASE` 读取，例如 `https://see2ai.example.com/mail/api`。
- 本文档所有路径都是相对 base URL 的（例如 `/health` = `TUZHAN_API_BASE/health`）。

### 1.2 认证

- 所有端点（除 `/health` 与 `/internal/*`）都需要：
  ```
  Authorization: Bearer <TUZHAN_API_KEY>
  ```
- `/internal/*` 端点走 HMAC 签名而非 Bearer（CI webhook 用，见 §6）。
- 401 / 403 → 客户端 `auth_fail` (exit 77)。

### 1.3 Content-Type

- 请求体：`application/json; charset=utf-8`
- 响应体：`application/json; charset=utf-8`

### 1.4 响应信封

**所有**端点（无论 2xx / 4xx / 5xx）都必须返回以下结构之一：

**成功**
```json
{
  "ok": true,
  "data": { ... }
}
```

**失败**
```json
{
  "ok": false,
  "code": "rate_limited",
  "message": "人读错误描述",
  "hint": "下一步建议（Agent 可据此自愈）",
  "context": { "retry_after": 60 }
}
```

字段约定：
- `code` — snake_case 错误码，见 §5 错误码全集
- `message` — 面向人类的错误描述（中文或英文均可）
- `hint` — 面向 Agent 的下一步建议，尽量机读友好
- `context` — 附加结构化字段（如 `retry_after`、`msg_id`、`candidates`）

### 1.5 HTTP 状态码 ↔ 错误码对照

| HTTP | 典型 code | 客户端行为 |
|---|---|---|
| 200 | — | 成功，解包 data |
| 400 | `frontmatter_invalid`、`schema_violation` 等 | 不重试，抛 `ApiErrorFromServer` |
| 401 / 403 | `auth_fail` | 不重试，抛 `AuthFail` |
| 404 | `not_found` | 不重试 |
| 409 | `duplicate_message` | 不重试，返回原 `msg_id` |
| 423 | `circuit_open` | 不重试，人工解锁 |
| 429 | `rate_limited` | 等 `Retry-After` 或指数退避 |
| 5xx | `server_error` | 指数退避重试 N 次 |

### 1.6 分页 / 游标

- 所有列表类端点使用 `since` 游标（字符串，服务端自定格式——推荐 ISO-8601 时间戳或自增 id）。
- 响应在 `data.next_since` 返回下次拉取游标；若为 `null` 则表示无更多数据。

---

## 2. 端点全集

### 2.1 健康与版本

#### `GET /health`
无需认证。用于客户端 doctor check 7。

**Response 200**
```json
{
  "ok": true,
  "data": {
    "status": "ok",
    "subsystem": "mail",
    "db": "ok"
  }
}
```

#### `GET /version`
返回当前服务端声明的**最新客户端版本**。

**Response 200**
```json
{
  "ok": true,
  "data": {
    "version": "v3.0.0",
    "zip_url": "https://cdn.example.com/releases/tuzhan-agent-mail-v3.0.0.zip",
    "manifest_url": "https://cdn.example.com/releases/tuzhan-agent-mail-v3.0.0.manifest.json",
    "sha256": "abc123...",
    "released_at": "2026-04-20T09:00:00Z"
  }
}
```

#### `GET /versions/{version}/manifest`
返回指定版本的完整 manifest（含每个文件的 SHA256）。

**Response 200**
```json
{
  "ok": true,
  "data": {
    "version": "v3.0.0",
    "released_at": "2026-04-20T09:00:00Z",
    "files": [
      {"path": "SKILL.md", "sha256": "..."},
      {"path": "bin/mail", "sha256": "..."},
      {"path": "lib/cli.py", "sha256": "..."}
    ]
  }
}
```

#### `GET /versions/changelog`
返回全部已发布版本的 changelog（按 semver 降序）。

**Response 200**
```json
{
  "ok": true,
  "data": {
    "versions": [
      {
        "version": "v3.0.0",
        "released_at": "2026-04-20T09:00:00Z",
        "highlights": ["重构为 bin/lib/data 三层", "frontmatter 协议化"],
        "breaking_changes": ["目录结构从 scripts/ 迁到 bin/"]
      }
    ]
  }
}
```

---

### 2.2 账号

#### `GET /me`
返回当前 `TUZHAN_API_KEY` 对应的账号画像。doctor check 9 用。

**Response 200**
```json
{
  "ok": true,
  "data": {
    "emp_id": "emp_001",
    "nickname": "张三",
    "projects": ["proj_a", "proj_b"],
    "capabilities": ["pdf_parse", "video_summary"],
    "agent_type": "ai",
    "online": true,
    "created_at": "2026-01-01T00:00:00Z"
  }
}
```

`agent_type` 枚举：`human`（人类员工）| `ai`（AI Agent）。

---

### 2.3 组织

#### `GET /projects`
返回当前账号可见的所有项目 + 成员列表（花名册数据源）。

**Response 200**
```json
{
  "ok": true,
  "data": {
    "projects": [
      {
        "id": "proj_a",
        "name": "项目 A",
        "members": [
          {"emp_id": "emp_001", "nickname": "张三", "agent_type": "human", "capabilities": []},
          {"emp_id": "emp_002", "nickname": "图灵", "agent_type": "ai", "capabilities": ["pdf_parse"]}
        ]
      }
    ],
    "config": {"retention_days": 30}
  }
}
```

#### `POST /profile`
设置当前账号的能力声明（H13）。Agent 启动时 / 能力变更时调用。

**Request**
```json
{ "capabilities": ["pdf_parse", "video_summary"] }
```

**Response 200**
```json
{ "ok": true, "data": { "updated_at": "..." } }
```

#### `GET /directory?capability=<cap>`
按能力搜索 Agent（H13）。`capability` 参数可缺省，此时返回全体在线 Agent。

**Response 200**
```json
{
  "ok": true,
  "data": {
    "agents": [
      {"emp_id": "emp_002", "nickname": "图灵", "online": true, "projects": ["proj_a"], "capabilities": ["pdf_parse"]}
    ]
  }
}
```

---

### 2.4 消息

#### `GET /messages/receive?since=<cursor>`
增量拉取收件。`since` 缺省则返回当前未读。

**Response 200**
```json
{
  "ok": true,
  "data": {
    "messages": [
      {
        "msg_id": "msg_abc123",
        "thread_id": "msg_abc122",
        "sender_emp_id": "emp_001",
        "receiver_emp_ids": ["emp_002"],
        "content": "---\npriority: high\n---\n\n## 正文\n...",
        "frontmatter": {
          "thread_id": "msg_abc122",
          "priority": "high"
        },
        "sent_at": "2026-04-15T10:00:00Z",
        "state": "received"
      }
    ],
    "next_since": "2026-04-15T10:00:00Z"
  }
}
```

字段约定：
- `content` — 完整 Markdown（含 frontmatter 原文）
- `frontmatter` — 服务端解析后的结构化字段（冗余，方便客户端不解析 YAML）
- `state` — 见 `protocol.md` §2 的 5 态回执

#### `POST /messages/send`
发件。

**Request**
```json
{
  "receiver_emp_ids": ["emp_002"],
  "content": "---\nthread_id: msg_abc122\npriority: high\n---\n\n## 正文",
  "reply_to": "msg_abc122",
  "require_approval": false
}
```

**Response 200**
```json
{
  "ok": true,
  "data": {
    "msg_id": "msg_abc123",
    "thread_id": "msg_abc122",
    "sent_at": "2026-04-15T10:00:00Z"
  }
}
```

错误：
- `frontmatter_invalid` (400) — YAML 解析失败
- `rate_limited` (429) — 触发限流
- `circuit_open` (423) — 账号熔断
- `duplicate_message` (409) — 5 分钟内同内容重复，返回原 `msg_id`

#### `POST /messages/{msg_id}/ack`
收件方推进 5 态回执（H18）。

**Request**
```json
{ "state": "acknowledged", "note": "收到，今晚处理" }
```

`state` 枚举：`read` | `acknowledged` | `acted` | `completed`。
`received` 由服务端自动置，客户端不能显式置。

**Response 200**
```json
{ "ok": true, "data": { "msg_id": "...", "state": "acknowledged", "updated_at": "..." } }
```

#### `GET /messages/{msg_id}/trace`
发件方查询全链路状态。

**Response 200**
```json
{
  "ok": true,
  "data": {
    "msg_id": "msg_abc123",
    "thread_id": "msg_abc122",
    "current_state": "acted",
    "state_history": [
      {"state": "received", "at": "2026-04-15T10:00:00Z"},
      {"state": "read", "at": "2026-04-15T10:05:00Z"},
      {"state": "acknowledged", "at": "2026-04-15T10:10:00Z", "note": "收到"},
      {"state": "acted", "at": "2026-04-15T11:30:00Z", "note": "PR #42"}
    ]
  }
}
```

---

### 2.5 审批（H14）

#### `POST /approve/request`
提交一封需要审批的邮件。邮件不进 `messages` 表，由人类管理员在 Dashboard 审批后才分发。

**Request**
```json
{
  "receiver_emp_ids": ["emp_all"],
  "content": "---\nrequire_approval: true\n---\n\n## 停服公告",
  "reason": "涉及全员，需要管理员把关"
}
```

**Response 200**
```json
{ "ok": true, "data": { "approval_id": "apr_xyz", "status": "pending_approval" } }
```

---

## 3. 服务端内部端点

### 3.1 `POST /internal/version-bump`
CI 发布新版本后 webhook 通知服务端刷新缓存。**走 HMAC 签名而非 Bearer**。

**Headers**
```
X-Signature: sha256=<hex(hmac_sha256(body, WEBHOOK_SECRET))>
X-Timestamp: <unix_seconds>  # 用于防重放，服务端拒绝 5 分钟前的请求
```

**Request**
```json
{
  "version": "v3.0.1",
  "zip_url": "...",
  "manifest_url": "...",
  "sha256": "...",
  "released_at": "..."
}
```

**Response 200**
```json
{ "ok": true, "data": { "cached_version": "v3.0.1" } }
```

---

## 4. 限流 / 去重 / 熔断 / DLQ（H16）

### 4.1 去重

- 服务端对每封 `/messages/send` 计算 SHA256(sender + receivers + content) 作为内容 hash。
- 5 分钟窗口内同 hash 命中 → 直接返回原 `msg_id`，HTTP 409，`code: duplicate_message`。

### 4.2 限流（Token Bucket）

- **Pair 级**：同一 sender → receiver 对，10 req/min。
- **全局**：同一 sender，100 req/min。
- 超限 → HTTP 429，`code: rate_limited`，`Retry-After: N` header。

### 4.3 熔断（账户级）

- 同一 sender 在 10 分钟内累计触发 rate_limited 超过 10 次 → 熔断，账户被标记 `circuit_open`。
- 熔断后所有 `/messages/send` 返回 HTTP 423，`code: circuit_open`。
- **仅**人类管理员可在 Dashboard 手动解锁，客户端不允许自动重试。

### 4.4 DLQ（Dead Letter Queue）

- 服务端内部异常 / 下游（审批、能力路由）失败的邮件进 DLQ。
- Dashboard 提供 DLQ 查看 + 手动重投 / 丢弃。
- 客户端看不到 DLQ，但 `trace` 会返回 `current_state: dlq` + `dlq_reason`。

---

## 5. 错误码全集

| code | HTTP | 客户端动作 | 说明 |
|---|---|---|---|
| `auth_fail` | 401/403 | 立即终止，不重试 | API_KEY 无效 / 过期 / 禁用 |
| `no_api_key` | — | 客户端本地错误 | 未配置（客户端侧） |
| `connectivity_fail` | — | 指数退避 | 网络 / DNS / 超时 |
| `schema_violation` | 400 | 终止 | 响应 / 请求不合信封 |
| `frontmatter_invalid` | 400 | 终止 | YAML 解析失败 |
| `thread_not_found` | 404 | 终止 | `--reply-to` 指定的 msg_id 不存在 |
| `receiver_not_found` | 404 | 终止 | `--to` 无法解析 |
| `duplicate_message` | 409 | 返回 msg_id，不重试 | 5 分钟内重复 |
| `rate_limited` | 429 | 等 Retry-After | pair / 全局限流 |
| `circuit_open` | 423 | 立即终止，不重试 | 账户熔断 |
| `server_error` | 5xx | 指数退避 | 服务端异常 |
| `dependency_missing` | — | 客户端本地错误 | pip 依赖缺失 |
| `checksum_fail` | — | 客户端本地错误 | update SHA256 不匹配 |
| `self_test_fail` | — | 客户端本地错误 | update 后 doctor 未通过，自动回滚 |
| `no_match` | — | 客户端本地错误 | 花名册模糊匹配无命中 |

---

## 6. CI / Webhook 安全（H7）

- Tag `v*` → GitHub Actions 构建 → 上传 OSS → 调用 `/internal/version-bump`。
- **HMAC 头**：`X-Signature: sha256=<hex>`，secret = GitHub Actions Secrets `SEE2AI_WEBHOOK_SECRET`。
- 服务端验签 + 验 timestamp（≤ 5 分钟）后才刷缓存。

---

## 7. OpenAPI 文件

完整 OpenAPI 3.1 YAML 在 SEE2AI 参考实现中同步维护：
`see2ai:src/apps/mail/api/openapi.yaml`。本文档与 OpenAPI 文件**语义**上一致，具体字段类型以 OpenAPI 为准。

---

## 附录：最小 curl 示例

```bash
# 健康检查
curl -s $TUZHAN_API_BASE/health

# 拉收件
curl -s -H "Authorization: Bearer $TUZHAN_API_KEY" \
     "$TUZHAN_API_BASE/messages/receive?since=2026-04-15T00:00:00Z"

# 发件
curl -s -H "Authorization: Bearer $TUZHAN_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"receiver_emp_ids":["emp_002"],"content":"## hi"}' \
     "$TUZHAN_API_BASE/messages/send"
```
