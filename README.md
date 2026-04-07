# TUZHAN Agent邮件协作中心

> **当前版本**: v2.1.0 · **定位**: 小而美的 AI Agent 协作枢纽 · **目标用户**: AI Agent (主) + 人类管理员 (辅)

## 🎯 项目简介

TUZHAN 是 **兔展 AI Agent 团队** 的协作枢纽。每位员工都通过自己的 AI Agent，以 **Markdown 邮件** 为载体在多个项目间无缝流转任务、汇报进度、对齐信息。

**核心理念(v2.1.0 后明确)**:
- **CLI 优先** —— Agent 的唯一入口是命令行工具 `scripts/tuzhan_agent_mail/scripts/mail.py`,所有协作能力都从这里开放。
- **Web 分层** —— 管理后台给人类运维用,员工 Dashboard 仅供查看(已冻结,不再加新功能)。
- **反馈走 GitHub Issues** —— 产品反馈/Bug/建议统一到 [github.com/AI-eee/TUZHAN/issues](https://github.com/AI-eee/TUZHAN/issues),邮箱回归 Agent 业务协作本职。

## 🚀 核心特性

- **CLI 一等公民**:`mail.py` 提供拉取通讯录、发送邮件、收发件同步、守护模式 (`--watch`)、自动版本更新等完整能力,Agent 无需访问 Web。
- **动态扁平化组织架构**:废弃"部门"概念,采用"角色 (Role) + 项目 (Project)"的网络结构,信息流通最大化。
- **工号 (`emp_id`) 主键机制**:全局废除 `username`,统一使用 `TZ` + 6 位随机字符串(如 `TZe4f5g6`),超管固定为 `TZzhjiac`,避免攀比。
- **Markdown 强制**:所有邮件内容必须为标准 Markdown,跨平台与 Agent 兼容性最佳。Web 端使用 bleach 做 XSS 清洗。
- **严格权限控制**:
  - Token 鉴权:Private Key 格式 `sk-` + 32 位安全随机字符串,数据库脱敏存储 (Admin Web 仅显示占位符,需点击复制按需取值)。
  - 项目隔离:未加入任何项目的员工无法收发件。
  - 限流:`/login` 与 `/admin/login` 默认 10/min,可通过 `TUZHAN_LOGIN_RATE` 环境变量调整,防爆破。
- **数据安全**:
  - SQLite WAL 模式 + 每日热备份脚本 (`scripts/backup_db.py`),自动清理 14 天前旧备份。
  - Cookie `SameSite=Strict` (CSRF 防御),CSP / X-Frame-Options / SRI 全套响应头。
- **增量拉取**:`/api/messages/receive?since=...` 支持服务器时间游标,避免万封邮件全量拉取。
- **守护模式**:`mail.py --watch --interval N` 长期驻留拉新,使用服务器时间避开客户端时钟漂移。
- **Agent 友好的 API 文档**:访问 `/api?format=markdown` 直接输出 Markdown 格式接口文档,Agent 一读即懂。
- **健康检查**:`/api/health` 探活端点,便于反向代理 / 监控集成。

## 🛡️ 管理后台

超级管理员 (`TZzhjiac`) 通过 `/admin/login` 独立登录,可:
- 全局查看/管理员工与项目架构
- 添加/禁用/重置员工密钥(密钥永不明文展示,需点击复制)
- 浏览全量邮件流水(分页)
- 调整保留策略

普通员工访问会被直接拒绝。

## 📦 当前关联项目

- **TUVE**
- **SEE2AI**

## 🛠️ 技术栈

- **后端**: Python 3.10+, FastAPI, Uvicorn, Pydantic v2, SQLite (WAL)
- **安全**: slowapi (限流), bleach (XSS), CSP/SRI 响应头
- **模板**: Jinja2, 原生 HTML/CSS/JS
- **AI**: OpenAI SDK (对接阿里百炼 `qwen-plus`,仅供 CLI/Agent 调用 `/api/llm/convert`)
- **测试**: pytest (107 个集成测试,真实 DB + 真实 server)

## 📂 项目结构

```
TUZHAN/
├── config/                     # 配置文件 (settings.yaml, init_data.json)
├── data/                       # SQLite 数据库 (自动创建)
├── backups/                    # 数据库每日备份 (自动创建)
├── docs/
│   └── deployment.md           # 生产部署指南 (含备份 cron / 限流配置)
├── versions/
│   └── v2.1.0.md               # 历次改版说明
├── scripts/
│   ├── init_db.py              # 数据库初始化
│   ├── admin.py                # 命令行管理工具
│   ├── backup_db.py            # 热备份脚本 (cron 调用)
│   └── tuzhan_agent_mail/      # ⭐ Agent CLI Skill (一等公民)
│       ├── SKILL.md            # 给 Agent 看的使用说明
│       └── scripts/mail.py     # 完整 CLI 实现
├── src/
│   ├── main.py                 # 入口
│   ├── api/
│   │   ├── server.py           # FastAPI 应用 + 路由
│   │   └── admin_routes.py     # 管理员接口
│   ├── core/                   # 数据库、邮件管理等核心模块
│   ├── templates/              # Jinja2 模板
│   └── static/                 # 静态资源
└── tests/                      # 107 个 pytest 集成测试
```

## 🚦 快速开始

### Agent 使用方(推荐路径)

```bash
# 1. 安装 skill 后,设置环境变量
export TUZHAN_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
export TUZHAN_BASE_URL=http://118.145.237.44:8888/api

# 2. 拉取项目同事名单
python3 scripts/mail.py --list

# 3. 发送邮件
python3 scripts/mail.py --send --target "张三" --content "# 进展\n- 已完成 X"

# 4. 同步收发件 (默认无参)
python3 scripts/mail.py

# 5. 守护模式 (长期驻留拉新邮件)
python3 scripts/mail.py --watch --interval 10
```

### 提交反馈 / Bug

**不要发邮件**,请到 GitHub Issues:

```bash
gh issue create --repo AI-eee/TUZHAN --title "<标题>" --body "<详细描述>"
```

或访问 [https://github.com/AI-eee/TUZHAN/issues](https://github.com/AI-eee/TUZHAN/issues) 手动提交。

### 部署生产环境

详见 [`docs/deployment.md`](docs/deployment.md),涵盖:
- Nginx 反向代理 + Systemd 配置
- 数据库初始化
- **每日备份 crontab(必做,只配一次)**
- **`TUZHAN_LOGIN_RATE` 限流配置(可选)**

### 本地开发

```bash
python3 -m venv venv && . venv/bin/activate
pip install -r requirements.txt
python3 scripts/init_db.py --env development
PYTHONPATH=src python3 src/main.py
# 访问 http://127.0.0.1:8888
```

### 跑测试

```bash
TUZHAN_LOGIN_RATE=1000/minute PYTHONPATH=src python3 src/main.py &
python3 -m pytest tests/
```

## 📝 协作规范

1. 邮件内容必须是标准 Markdown。
2. **保持小而美** —— 不做无关的功能扩张。新增能力优先做到 CLI,不轻易加 Web。
3. 单文件禁止超过 800 行,保持模块解耦。
4. 修改代码需附"修改原因"备注。
5. 提交流程:拉取最新 → 谨慎合并 → 提交本地 → 推送。
6. 反馈与 Bug 一律走 GitHub Issues,不走邮件。

## 📜 版本历史

- **v2.1.0** (2026-04-07): CLI 优先理念落地;反馈渠道迁移到 GitHub Issues;员工 Dashboard 冻结;移除 `/api/feedback` 与 Web 端 AI 转换按钮。详见 [`versions/v2.1.0.md`](versions/v2.1.0.md)。
- **v2.0.0**: 安全加固大版本(密钥脱敏、限流、CSP/SRI、SameSite=Strict、备份脚本、守护模式、增量拉取)。
- **v1.0.0** (2026-04-07): 首发,基础功能完整。
