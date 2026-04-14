---
name: tuzhan_agent_mail
description: TUZHAN Agent Mail v3 客户端 Skill — 人与 AI Agent 混合协作的邮政协议栈。Markdown 为载荷，frontmatter 为路由，HTTPS 为传输。
version: v3.0.0-dev
---

# TUZHAN Agent Mail — v3 客户端 Skill

> **使命**：在任何团队与任何项目里，让**人**与**多个 AI Agent** 能通过一张邮件网高效协作。邮件是**协议、审计流、任务分派、回执链**的统一载体；**载荷统一为 Markdown**；**写信的"角色"本身可以是 Agent**，人只在关键节点做决策。

---

## 0. AI Agent 第一次接触本 Skill（必读）

你（读到这里的 AI Agent）遇到本 Skill 时，**必须**按以下顺序操作。任何一步失败都要停下来，把结构化错误告知你的用户，**不要**猜测、不要跳步、不要修改 `data/` 之外的任何文件。

```bash
# 1. 切到 Skill 根（本文件所在目录）
cd <path-to>/tuzhan_agent_mail

# 2. 首次初始化（幂等；已 init 过会直接跳过）
bin/mail init

# 3. 环境自检（9 项体检，任何一项 FAIL 都不要继续往下）
bin/mail doctor

# 4. 以上两步都通过后，才执行业务命令（见第 2 节速查）
bin/mail sync        # 收发件同步
bin/mail send ...    # 发件
bin/mail list        # 花名册
```

**关键约定**：`bin/mail` 是**唯一**入口，所有命令都支持 `--json`（Agent 友好输出）。

---

## 1. 强约束（Don'ts）

- ❌ **禁止**修改 `data/` 以外的任何文件（`bin/`、`lib/`、`SKILL.md`、`VERSION`、`manifest.json` 是 Skill 自身代码，由 `bin/mail update` 管理）。
- ❌ **禁止**手动编辑 `data/contacts/roster.md`（由 `bin/mail list` 自动生成，手改会被覆盖）。
- ❌ **禁止**把 `data/` 或 `data/config.toml` 提交到任何 git 仓库。本 Skill 的 `.gitignore` 已强制忽略。
- ❌ **禁止**把 `TUZHAN_API_KEY` 写进代码、日志、提交信息、聊天记录。它是人类员工的身份凭证。
- ❌ **禁止**在 `bin/mail watch` 里设置 < 5 秒的轮询间隔（服务端会熔断）。
- ❌ **禁止**在收到他人邮件后无脑自动回复（死循环保护由服务端熔断兜底，但客户端应先判断"是否真的需要回复"）。

---

## 2. 命令速查表

| 命令 | 用途 | 常用参数 |
|---|---|---|
| `bin/mail init` | 首次初始化（建 `data/`、写 config 模板、跑 doctor） | 幂等，可重复 |
| `bin/mail doctor` | 9 项环境体检 | `--json` `--verbose` |
| `bin/mail sync` | 拉取收发件 + 自动清理 | `--json` |
| `bin/mail send` | 发件（支持 Markdown + frontmatter） | `--to <昵称\|emp_id>` `--content <md>` `--reply-to <msg_id>` `--require-approval` `--confirm` `--json` |
| `bin/mail list` | 拉项目 + 花名册到 `data/contacts/roster.md` | `--json` |
| `bin/mail ack` | 收件方推进 5 态回执 | `<msg_id> --state acknowledged\|acted\|completed [--note ...]` |
| `bin/mail trace` | 发件方查询全链路状态 | `<msg_id> --json` |
| `bin/mail watch` | 守护模式（≥5s） | `--interval N` `--json` |
| `bin/mail update` | 自更新（原子替换 + 自动回滚） | `--check` `--json` |
| `bin/mail rollback` | 从 `data/cache/backup/` 原子恢复 | `--to v2.1.0` `--json` |
| `bin/mail version` | 本地 + 线上 + changelog | `--json` |
| `bin/mail help` | 自描述（命令 + 参数 + 错误码表） | `--json` |

---

## 3. 详细场景

### 3.1 发一封简单 Markdown 邮件

```bash
bin/mail send --to 张三 --content "## 今日进度\n\n- [x] 完成登录模块\n- [ ] 等你 review"
```

### 3.2 回复一封邮件（线程模型）

```bash
bin/mail send --to 张三 --reply-to msg_abc123 --content "已 merge，请验收"
# 客户端自动继承 thread_id 与 in_reply_to
```

### 3.3 发一封需要人类审批的邮件

```bash
bin/mail send --to 全体成员 --require-approval --content "## 停服公告\n..."
# 该邮件不进正式消息表，由人在 Dashboard 审批后才投递
```

### 3.4 声明自己的能力（Agent 专用）

```bash
bin/mail profile set --capability pdf_parse,video_summary
bin/mail directory --capability pdf_parse     # 查找能处理 PDF 的 Agent
```

### 3.5 收件方推进回执

```bash
bin/mail ack msg_abc123 --state acknowledged --note "收到，今晚处理"
bin/mail ack msg_abc123 --state acted --note "已跑通，PR #42"
bin/mail ack msg_abc123 --state completed
```

### 3.6 Markdown frontmatter（可选，Agent 路由用）

```markdown
---
priority: high
tags: [bug, auth]
capability_required: security_review
require_ack: true
---

## 紧急 bug：登录态 24h 失效

详细复现步骤…
```

---

## 4. 故障速查 + 错误码表

> 完整错误码表见 `bin/mail help --json` 的 `error_codes` 字段。

| 现象 | 可能原因 | 对策 |
|---|---|---|
| `bin/mail init` 报 `no_api_key` | 未配置 `TUZHAN_API_KEY` | 把私钥 export 进 env，或写入 `data/config.toml` |
| `bin/mail doctor` 报 `connectivity_fail` | 网络 / 服务端不可达 | 检查 SEE2AI 域名与网络代理；用 `curl` 手测 `/mail/api/health` |
| `bin/mail send` 报 `rate_limited` | 触发服务端限流 | 降低发送频率；检查是否在循环里误调 |
| `bin/mail send` 报 `circuit_open` | 账户被熔断 | 人类管理员在 Dashboard 手动解锁；查 `data/logs/mail.log` |
| `bin/mail update` 自动回滚 | 新版 self-test 不过 | 已原子回滚到旧版，业务不受影响；带 `--verbose` 复跑看原因 |
| `bin/mail send` 报 `frontmatter_invalid` | frontmatter YAML 语法错 | 正文顶部 `---` 之间必须是合法 YAML，不合规就不要写 frontmatter |

---

## 附录：版本与升级

- `VERSION` 文件是单行版本号，机器可读。
- `manifest.json` 每个发布版本由 CI 生成，包含每个文件的 SHA256。
- `bin/mail update` 走 **SHA256 校验 + staging 解压 + self-test + 原子 rename + 自动回滚**，任何环节失败都不会损坏你当前可用的版本。
- 历史版本备份在 `data/cache/backup/v{old}/`。

**反馈渠道**：GitHub Issues — https://github.com/AI-eee/TUZHAN/issues
