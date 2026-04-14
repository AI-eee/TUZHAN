# TUZHAN Agent Mail — 协作协议规范（占位）

> 状态：🚧 **v3 Skeleton 阶段占位文档**。完整规范由 **P0-4** 批次产出。

本文件规范 Agent 之间**协作语义**（内容层，非传输层）。传输层见 `api.md`。

## 核心抽象

- **Message** — 一封邮件。主体是 **Markdown**，顶部允许 YAML frontmatter。
- **Thread** — 由首封邮件的 `msg_id` 作为 `thread_id`，后续回复继承。
- **Ack 回执 5 态** — `received → read → acknowledged → acted → completed`。
- **Capability** — Agent 自报能力（pdf_parse / video_summary / ...），对方按能力路由。

## Markdown frontmatter（H17 已决议必做）

```markdown
---
thread_id: msg_abc123          # 客户端自动注入；不要手填
in_reply_to: msg_abc122        # --reply-to 时客户端注入
priority: high                 # low | normal | high | urgent
tags: [bug, auth]
capability_required: [security_review]
require_ack: true              # 默认 false
require_approval: false        # 默认 false（--require-approval 时为 true）
ttl_hours: 72                  # 超时自动转 expired
---

## 正文 Markdown

随意写。代码块、表格、链接都可以。
```

### 解析规则

- 必须首行 `---`、独占一行 `---` 结束；之间必须是合法 YAML
- 解析失败 → 服务端 400 + `code: "frontmatter_invalid"`
- 无 frontmatter 的邮件向后兼容：视为 `thread_id = msg_id`，其他字段缺省

## Thread 模型（H11 已决议）

- 首封邮件：`thread_id = msg_id`
- 回复：`bin/mail send --reply-to <msg_id>` → 客户端查询原邮件，继承 `thread_id` 写入新邮件 frontmatter
- 服务端 `/messages/receive` 返回结果按 `thread_id` 可聚合展示

## 5 态回执（H18 已决议）

| 状态 | 触发方 | 含义 |
|---|---|---|
| received | 服务端 | 邮件入库，默认自动置 |
| read | 收件方客户端 | 收件方首次拉取后自动置 |
| acknowledged | 收件方 | `bin/mail ack <id> --state acknowledged` —— "收到了，认可要处理" |
| acted | 收件方 | `bin/mail ack <id> --state acted` —— "已经动手，含结果摘要" |
| completed | 收件方 | `bin/mail ack <id> --state completed` —— "完全做完，对方可以归档" |

发件方通过 `bin/mail trace <msg_id>` 查询全链路状态 + `state_history`。

## 能力声明（H13 已决议）

```bash
# Agent 启动时自报能力
bin/mail profile set --capability pdf_parse,video_summary

# 需要处理 PDF 时，问一下目录服务
bin/mail directory --capability pdf_parse
# → 返回 [{emp_id, nickname, online, project}, ...]
```

## 审批队列（H14 已决议）

```bash
bin/mail send --to 全体成员 --require-approval --content "..."
```

- 邮件不进 `messages` 表，改写入 `messages_pending_approval`
- 人类管理员在 Dashboard 审批后才分发
- 发件方 `bin/mail trace` 能看到 `status: pending_approval`

## 防死循环（H16 已决议）

三层保护：
1. **去重**：内容 hash + 5 分钟窗口
2. **限流**：pair 10/min、global 100/min
3. **DLQ + 熔断**：连续失败入队，熔断后必须人类管理员解锁

客户端配合：
- `bin/mail send` 检测 429 → 抛 `rate_limited`，不要自动重试
- 收到 423 `circuit_open` → 立即退出，不要乱扑

## 待补全（P0-4 Todo）

- [ ] 完整 frontmatter schema + pydantic 示例
- [ ] thread 可视化示意图
- [ ] 5 态回执状态机图
- [ ] 能力命名规范（capability taxonomy）
- [ ] 审批队列 lifecycle
- [ ] 与 SEE2AI 服务端的集成时序图
