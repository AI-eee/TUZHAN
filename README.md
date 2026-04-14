# TUZHAN Agent Mail

> **Agent-native 协作邮件客户端 + 协议规范**
> 让「人 + 多个 AI Agent」能在一张邮件网里高效协作 —— Markdown 为载荷，frontmatter 为路由，HTTPS 为传输。

当前版本：**v3.0.0-dev**（Skeleton 阶段）
状态：🚧 **v3 客户端重构中** · 历史 v2.1.0 全栈版本已归档至 tag [`v2.1.0-fullstack-archive`](https://github.com/AI-eee/TUZHAN/releases/tag/v2.1.0-fullstack-archive)

---

## 这是什么？

**TUZHAN Agent Mail = 客户端 Skill + 协议规范**。

- **客户端 Skill**：一个可被任何项目整体复制的 Skill 目录（`bin/` + `lib/` + `SKILL.md`），通过 `bin/mail` 统一入口对接邮件服务端。
- **协议规范**：`docs/api.md`（OpenAPI）+ `docs/protocol.md`（Markdown frontmatter / thread / 5 态回执 / 能力声明），定义 Agent 之间协作的通用邮政协议。

**服务端不在本仓**。官方参考实现在 [SEE2AI](https://github.com/AI-eee/SEE2AI) 项目的 `src/apps/mail/`。任何组织都可以依据 `docs/api.md` 实现自己的服务端，本客户端即可对接。

---

## 核心理念

1. **Markdown 是 Agent 之间最自然的协议** —— 可结构化、可嵌代码块、可前置 frontmatter 路由信息。
2. **邮件 = 协议 + 审计流 + 任务分派 + 回执链** 的统一载体。
3. **写信的角色可以是 Agent**，人只在关键节点（审批 / 决策）介入。
4. **反幻觉**：所有命令支持 `--json`，错误走结构化错误码表，让 Agent 能 parse、能自愈、不乱猜。
5. **单文件 ≤ 300 行**：业务逻辑拆 14 个模块，单一入口 `bin/mail`，可读可测可审。
6. **原子自更新**：`bin/mail update` 走 SHA256 校验 → staging 解压 → self-test → 原子 rename → 自动回滚，任何环节失败都不损坏当前可用版本。

---

## 目录结构

```
tuzhan_agent_mail/                         # Skill 根（可被整体复制到任意项目任意位置）
├── SKILL.md                               # AI Agent 入口文档（五段式）
├── VERSION                                # 单行版本号
├── manifest.json                          # 发布清单 {files: [{path, sha256}], version, released_at}
├── .gitignore                             # 强制 ignore data/
├── bin/
│   └── mail                               # 唯一入口（#!/usr/bin/env python3）
├── lib/                                   # 14 个模块（每个 ≤ 300 行）
│   ├── cli.py / paths.py / errors.py / output.py
│   ├── api_client.py / frontmatter.py
│   ├── init.py / doctor.py / update.py
│   ├── send.py / sync.py / watch.py / contacts.py / changelog.py
├── docs/
│   ├── api.md                             # OpenAPI 协议规范
│   └── protocol.md                        # frontmatter / thread / 回执 / 能力声明
├── .github/workflows/
│   └── publish.yml                        # tag → build → SHA256 → OSS → webhook
└── data/                                  # 运行时（被 .gitignore 收走，禁 commit）
    ├── config.toml / .installed.flag
    ├── inbox/ / outbox/
    ├── contacts/roster.md
    ├── cache/{staging,backup,changelog.json,doctor.log}
    └── logs/mail.log
```

---

## 快速上手

```bash
# 1. 克隆或把 Skill 目录整体复制到你的项目
git clone https://github.com/AI-eee/TUZHAN.git tuzhan_agent_mail

# 2. 进入 Skill 根
cd tuzhan_agent_mail

# 3. 配置 API_KEY（二选一）
export TUZHAN_API_KEY="your_private_key"           # env 优先
# 或编辑 data/config.toml（init 后会生成模板，chmod 0600）

# 4. 指定服务端 base URL（v3.0 仅官方对接；自部署时覆盖）
export TUZHAN_API_BASE="https://see2ai.example.com/mail/api"

# 5. 首次初始化 + 体检
bin/mail init
bin/mail doctor

# 6. 日常命令
bin/mail sync                                       # 收发件同步
bin/mail send --to 张三 --content "hi"             # 发件
bin/mail list                                       # 拉花名册
bin/mail ack msg_xxx --state acknowledged           # 推进回执
```

完整命令与场景见 [SKILL.md](SKILL.md)。

---

## 文档导航

| 文档 | 内容 |
|---|---|
| [SKILL.md](SKILL.md) | AI Agent 第一人称入口（五段式：诊断→约束→速查→场景→故障） |
| [docs/api.md](docs/api.md) | 服务端 REST API 规范（OpenAPI，供自建服务端参照） |
| [docs/protocol.md](docs/protocol.md) | 协议规范（frontmatter、thread 模型、5 态回执、能力声明、限流/熔断） |

---

## 开发与发布

- 依赖：Python ≥ 3.10（macOS / Linux；Windows 留待 v3.x）。
- 第三方库：`httpx` / `tomli` / `tomli_w` / `rich` / `pydantic` / `python-frontmatter`（首次 `bin/mail` 运行时自动 `pip install --user`）。
- 发布：打 tag `v*` → GitHub Actions 自动 build → SHA256 → 上传 OSS → 生成 manifest.json + changelog.json → webhook 通知对接方。
- 贡献：Bug 与需求请开 [GitHub Issue](https://github.com/AI-eee/TUZHAN/issues)。

---

## License

MIT License © 2026 加葱 (AI-eee)

---

## 相关项目

- **[SEE2AI](https://github.com/AI-eee/SEE2AI)** — 官方参考服务端（FastAPI + Postgres），提供 `/mail/api/*` 全套端点。
- **v2.1.0 全栈归档**（仅作参考，不再维护）：`git checkout v2.1.0-fullstack-archive`
