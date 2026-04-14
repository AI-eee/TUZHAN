# TUZHAN Agent Mail — 协作协议规范

> 本文件规范 Agent 之间**协作语义**（内容层 / 业务层）。传输层（REST）见 [`api.md`](api.md)。
>
> **使命**：让"人 + AI Agent"能在一张邮件网里高效协作——**Markdown 是内容，frontmatter 是路由，邮件 = 协议 + 审计流 + 任务分派 + 回执链**。

---

## 0. 核心抽象

| 概念 | 含义 |
|---|---|
| **Message** | 一封邮件。主体 = **Markdown**，顶部可选 YAML frontmatter |
| **Thread** | 首封邮件的 `msg_id` 作为 `thread_id`；后续回复继承 |
| **Ack 5 态** | `received → read → acknowledged → acted → completed` 一条有向链 |
| **Capability** | Agent 自报能力（如 `pdf_parse` / `video_summary`），对方按能力路由 |
| **Approval** | 高风险邮件（全员公告 / 账务操作）必须经人类管理员审批后再投递 |

---

## 1. Markdown frontmatter（H17 必做）

### 1.1 格式

正文顶部以 `---` 起始、独占一行 `---` 结束，中间是合法 YAML；其后是 Markdown 正文。

```markdown
---
priority: high
tags: [bug, auth]
capability_required: [security_review]
require_ack: true
ttl_hours: 72
---

## 紧急 bug：登录态 24h 失效

详细复现步骤…
```

### 1.2 字段 Schema（pydantic v2）

| 字段 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `thread_id` | `str` | null | 线程 id。**客户端自动注入**，禁止手填 |
| `in_reply_to` | `str` | null | 被回复的 `msg_id`。`--reply-to` 时客户端自动注入 |
| `priority` | `"low"\|"normal"\|"high"\|"urgent"` | `"normal"` | 优先级，Dashboard 排序与通知策略依据 |
| `tags` | `list[str]` | `[]` | 自由 tag。服务端建立索引支持检索 |
| `capability_required` | `list[str]` | `[]` | 期望收件方具备的能力（H13） |
| `require_ack` | `bool` | `false` | 发件方要求收件方显式推进 `acknowledged` |
| `require_approval` | `bool` | `false` | 需要人类管理员审批（H14）。由 `--require-approval` 触发 |
| `ttl_hours` | `int` | null | 超时自动标记 `expired`（实验性） |

### 1.3 解析规则

- **必须**以首行 `---` 开始、独占一行 `---` 结束。
- 中间**必须**是合法 YAML；解析失败 → HTTP 400 `frontmatter_invalid`。
- 正文不以 `---` 开头 → 视为"无 frontmatter"，字段全取默认值（**v2.x 向后兼容**）。
- 未识别字段进 `extras: dict`，不影响解析（**向前兼容**）。
- 所有字段都是可选的；甚至整块 frontmatter 也是可选的。

### 1.4 发送时的客户端注入

客户端 `bin/mail send` 在 POST 前注入：
- 若带 `--reply-to <msg_id>`：查出原邮件的 `thread_id`，写入新邮件的 frontmatter；同时写 `in_reply_to`。
- 若无 `--reply-to`：不注入（服务端落库时用 `msg_id` 作为 `thread_id`）。

---

## 2. Thread 模型（H11）

### 2.1 规则

- **首封**邮件：服务端落库时 `thread_id = msg_id`（若客户端未传）。
- **回复**邮件：继承被回复消息的 `thread_id`；`in_reply_to` 指向直接父消息。

### 2.2 线程可视化

```
msg_001 (thread_id=msg_001)        ← 首封
 ├─ msg_002 (thread=msg_001, reply_to=msg_001)
 │    └─ msg_003 (thread=msg_001, reply_to=msg_002)
 └─ msg_004 (thread=msg_001, reply_to=msg_001)
```

### 2.3 客户端用法

```bash
bin/mail send --to 张三 --reply-to msg_001 --content "回复一下"
# → frontmatter 自动含 thread_id: msg_001 + in_reply_to: msg_001
```

### 2.4 查询

`GET /messages/receive` 返回的每条都带 `thread_id`，客户端可自行按 `thread_id` 聚合展示。

---

## 3. 5 态回执（H18）

### 3.1 状态机

```
received ──(收件方拉取)──▶ read ──(人/Agent 认可)──▶ acknowledged ──▶ acted ──▶ completed
                                            │
                                            └──(超时/ttl)──▶ expired
```

| 状态 | 触发方 | 语义 | 何时置 |
|---|---|---|---|
| `received` | 服务端自动 | 邮件已入库 | `POST /messages/send` 落库时 |
| `read` | 收件方客户端 | 收件方首次拉到该邮件 | `GET /messages/receive` 返回时 |
| `acknowledged` | 收件方显式 | "收到了，认可要处理" | `bin/mail ack <id> --state acknowledged` |
| `acted` | 收件方显式 | "已经动手，含结果摘要" | `bin/mail ack <id> --state acted` |
| `completed` | 收件方显式 | "完全做完，对方可归档" | `bin/mail ack <id> --state completed` |
| `expired` | 服务端自动 | `ttl_hours` 到期且未 completed | 定时任务扫描 |

### 3.2 规则

- 不允许倒退（`acted` 不能回到 `acknowledged`）。
- 发件方**查询**：`bin/mail trace <msg_id>` → 返回 `current_state` + `state_history`。
- 每次状态推进都写入 `state_history`，含 timestamp + note。

### 3.3 客户端场景

```bash
# Agent 收到邮件后，先表态：会处理
bin/mail ack msg_abc123 --state acknowledged --note "收到，预计 1h 内回"

# 完成后：带结果摘要
bin/mail ack msg_abc123 --state acted --note "已修 bug，PR #42 待 review"

# 对方 review 通过，发件方标记 completed（也可由收件方）
bin/mail ack msg_abc123 --state completed
```

---

## 4. 能力声明（H13）

### 4.1 能力 taxonomy（建议，不强制）

| 一级 | 示例能力 |
|---|---|
| 解析 | `pdf_parse` / `excel_parse` / `video_summary` / `audio_transcribe` |
| 代码 | `python_write` / `typescript_write` / `go_write` / `sql_write` |
| 安全 | `security_review` / `secrets_scan` / `penetration_test` |
| 业务 | `requirement_refine` / `ui_design` / `financial_review` |

**命名约定**：全小写 + 下划线；一级类别用单词前缀使同类聚集；新能力应先在团队 wiki 备案再使用。

### 4.2 客户端 API

```bash
# Agent 启动时（或能力变更时）自报能力
bin/mail profile set --capability pdf_parse,video_summary

# 需要 PDF 解析能力时，先查目录
bin/mail directory --capability pdf_parse
# → [{emp_id: "emp_002", nickname: "图灵", online: true, projects: [...]}]

# 然后定向发信
bin/mail send --to emp_002 --content "---\ncapability_required: [pdf_parse]\n---\n\n..."
```

### 4.3 服务端行为

- `POST /profile` 覆写当前账号能力列表（非追加）。
- `GET /directory?capability=X` 返回**所有**声明该能力的账号（含人类和 Agent）。
- `capability_required` 在 frontmatter 里列出时，服务端会在 Dashboard 上给 "能力不匹配" 预警，但**不**阻拦投递（收件人仍有权选择拒绝/转发）。

---

## 5. 审批队列（H14）

### 5.1 触发

客户端带 `--require-approval`：

```bash
bin/mail send --to 全体成员 --require-approval --content "## 停服公告\n..."
```

或 frontmatter 写 `require_approval: true`。

### 5.2 服务端行为

- 邮件**不**进 `messages` 表；改写入 `messages_pending_approval` 表。
- 字段：`id, sender_emp_id, receivers_json, content, frontmatter_json, requested_at, status, approved_at, approved_by, reject_reason`。
- `status`：`pending` → `approved` / `rejected`。

### 5.3 审批后

- `approved`：服务端把邮件从 `messages_pending_approval` 写入 `messages`，分发给收件方。原 `approval_id` 记在新 `msg_id` 的元数据里便于追溯。
- `rejected`：邮件永久驻留 `messages_pending_approval`，状态标 `rejected`，`reject_reason` 必填。发件方 `trace` 可见。

### 5.4 发件方查询

```bash
bin/mail trace <approval_id>
# → { current_state: "pending_approval", ... }
#   审批通过后转为： { current_state: "received", msg_id: "msg_xxx", ... }
```

---

## 6. 限流 / 去重 / 熔断 / DLQ（H16）

协议层规则——服务端**必须**实现，客户端**必须**按码响应。

### 6.1 去重

- 服务端计算 `SHA256(sender_emp_id + ";" + ",".join(sorted(receiver_emp_ids)) + ";" + content)` 作为内容 hash。
- 5 分钟窗口内命中同 hash → HTTP 409 + `code: duplicate_message` + `context: { original_msg_id: "..." }`。
- **客户端行为**：视同成功，返回原 msg_id，**禁止重试**。

### 6.2 限流（Token Bucket）

- **Pair 级**：同一 sender → 同一 receiver，10 req/min（bucket 容量 10，补充 1/6s）。
- **全局**：同一 sender，100 req/min。
- 超限 → HTTP 429 + `code: rate_limited` + `Retry-After: N` header。
- **客户端行为**：最多重试 N 次，每次等 `Retry-After`；超过重试次数后抛 `RateLimited` 给用户。

### 6.3 熔断（账户级）

- 同一 sender 在 10 分钟窗口内累计触发 `rate_limited` > 10 次 → 账户 `circuit_open`。
- 之后所有 `/messages/send` 与 `/approve/request` → HTTP 423 + `code: circuit_open`。
- **只能**人类管理员在 Dashboard 手动解锁。
- **客户端行为**：立即 exit 75，**禁止**自动重试。`bin/mail watch` 接到此错误应立即退出。

### 6.4 DLQ

- 服务端内部异常 / 下游路由失败 / 审批超时 → 邮件进 DLQ。
- Dashboard 提供查看 + 重投 / 丢弃。
- 客户端 `trace` 会看到 `current_state: dlq`、`dlq_reason: "..."`。
- **客户端行为**：只读；不能操作 DLQ 条目。

### 6.5 死循环保护

**三层兜底**：去重（内容层）→ 限流（频次层）→ 熔断（帐户层）。
任何一层都**必须**生效。客户端**自律**：
- 收到邮件**不要**无脑自动回复。
- `bin/mail watch` 的 interval 下限 5 秒。
- 收到 429 / 423 立即停，不要 loop。

---

## 7. 数据保留与合规

- 服务端默认保留全部消息 30 天（可配置 `retention_days`）。
- 客户端 `bin/mail sync` 自动清理 `data/inbox/**` 与 `data/outbox/**` 超期文件。
- 审批队列 `messages_pending_approval` 永久保留（审计用）。
- `state_history` 永久保留（回执审计链）。
- **敏感数据自查**：`TUZHAN_API_KEY` 永远不应出现在日志、邮件正文或 state_history.note 里。

---

## 8. 版本兼容策略

| 场景 | 处理 |
|---|---|
| v2.x 客户端连 v3 服务端 | 向后兼容：无 frontmatter 邮件视为 `thread_id = msg_id`，其他字段缺省 |
| v3 客户端连 v2.x 服务端 | 不保证；`bin/mail doctor` check 8 会警告版本差 |
| v3.0 → v3.x 小版本 | 严格兼容；frontmatter 只允许新增字段，禁止删除 / 改语义 |
| v3 → v4 | 必须走 deprecation 周期 ≥ 2 个小版本 + changelog 显式标记 breaking |

---

## 9. 参考实现

- **客户端**：[AI-eee/TUZHAN](https://github.com/AI-eee/TUZHAN) — 本仓
- **服务端**：[AI-eee/SEE2AI](https://github.com/AI-eee/SEE2AI) `src/apps/mail/` — FastAPI + Postgres + Alembic

---

## 附录：完整场景示例

### A.1 Agent 协作修 bug

```
1. 产品经理(人) → 张三(Agent)：
   "---\npriority: high\nrequire_ack: true\ncapability_required: [security_review]\n---\n\n## 登录态 bug..."

2. 张三 ack msg_001 --state acknowledged --note "开查"
3. 张三 send --to 李四(Agent) --reply-to msg_001 --content "## 能帮我 review 下 auth.py 么"
4. 李四 ack msg_002 --state acked --note "发现 cookie 未设 HttpOnly"
5. 张三 send --to 产品经理 --reply-to msg_001 --content "## 修复方案..."
6. 产品经理 → 张三 msg_005 --state completed
```

全部过程：**4 封邮件，5 个状态转移，1 次跨 Agent 协作**，全链路可 trace 可审计。
