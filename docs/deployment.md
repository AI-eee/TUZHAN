# TUZHAN 生产环境部署指南

## 📋 环境要求

- **Python**: 3.10+
- **Nginx**: 1.18+
- **Systemd**: 用于进程管理
- **Git**: SSH key 方式拉取代码

## 🚀 部署步骤

### 1. 拉取代码

```bash
# 配置 SSH Key（一次性）
ssh-keygen -t ed25519 -f ~/.ssh/tuzhan_github -C "tuzhan@see2ai.com"
# 将 ~/.ssh/tuzhan_github.pub 添加到 GitHub SSH Keys

mkdir -p /path/to/TUZHAN && cd /path/to/TUZHAN
git clone git@github.com:AI-eee/TUZHAN.git .
```

### 2. 安装依赖

```bash
cd /path/to/TUZHAN
python3 -m venv venv
. venv/bin/activate
pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
# 创建 .env 文件
echo "TUZHAN_ENV=production" > /path/to/TUZHAN/.env

# 可选：登录接口限流速率（默认 10/minute，防爆破）
# 如需调整可追加，例如放宽到 30/minute：
# echo "TUZHAN_LOGIN_RATE=30/minute" >> /path/to/TUZHAN/.env
```

> ⚙️ `TUZHAN_LOGIN_RATE` 同时作用于 `/login` 与 `/admin/login`。生产环境留空使用默认值即可,只有在确认需要放宽时才调整。改完需要 `sudo systemctl restart tuzhan` 生效。同时记得在 `tuzhan.service` 的 `[Service]` 段加 `EnvironmentFile=/path/to/TUZHAN/.env`,否则 systemd 不会读 `.env`。

### 4. 初始化数据库

```bash
# Production 环境（仅首次运行）
. venv/bin/activate
python3 scripts/init_db.py --env production
```

> ⚠️ 数据库文件位于 `data/prod.sqlite`，已存在时脚本会自动中止以防覆盖。

### 5. Nginx 反向代理配置（标准部署方式）

**架构原则：Nginx 监听 8888 端口 → 反向代理到 FastAPI 应用（127.0.0.1:8889）**

FastAPI 应用绑定 `127.0.0.1:8889`，不直接对外暴露。所有外部请求必须通过 Nginx 8888 端口进入。

**Nginx 配置**（如 `/etc/nginx/conf.d/tuzhan.conf`）：

```nginx
server {
    listen 8888;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:8889;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE 支持（AI 智能转换功能可能需要流式响应）
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_cache off;
        proxy_buffering off;
        proxy_set_header X-Accel-Buffering no;

        # 超时设置
        proxy_connect_timeout 60s;
        proxy_send_timeout 120s;
        proxy_read_timeout 120s;
    }
}
```

**对应的 settings.yaml 配置（production）：**

```yaml
production:
  server_bind_host: "127.0.0.1"    # 只监听本地，不直接对外
  server_bind_port: 8889            # 应用端口
  client_base_url: "http://<公网IP>:8888"  # 客户端通过 Nginx 访问
  database_url: "sqlite:///./data/prod.sqlite"
```

> 📌 **注意**：`config/settings.yaml` 中的 production 配置已按此标准设定。如果 8888 端口被 Nginx 其他站点占用，需要先调整对应站点的配置。

### 6. 配置 Systemd 服务

```bash
sudo tee /etc/systemd/system/tuzhan.service > /dev/null << 'EOF'
[Unit]
Description=TUZHAN Collaboration Center
After=network.target

[Service]
Type=simple
WorkingDirectory=/path/to/TUZHAN
Environment=PATH=/path/to/TUZHAN/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ExecStart=/path/to/TUZHAN/venv/bin/python3 src/main.py
Restart=on-failure
RestartSec=5
StandardOutput=append:/var/log/tuzhan.log
StandardError=append:/var/log/tuzhan.log

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable tuzhan
sudo systemctl start tuzhan
```

### 7. 验证

```bash
# 检查应用
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8889/    # 应返回 200

# 检查 Nginx 代理
curl -s -o /dev/null -w "%{http_code}" http://<公网IP>:8888/     # 应返回 200

# 检查管理后台
curl -s -o /dev/null -w "%{http_code}" http://<公网IP>:8888/admin/login  # 应返回 200
```

### 8. 配置每日数据库备份(必做,只配一次)

> ⚠️ **部署同事注意**:此步骤是**首次部署必做项**。如果服务器上的 crontab 已经有 `backup_db.py` 这一行,说明之前部署过,跳过即可;如果没有,必须加上,否则数据库不会有备份。

项目自带热备份脚本 `scripts/backup_db.py`,使用 SQLite `.backup()` API 做事务一致性备份,原子重命名,自动清理 14 天前的旧备份。备份文件落在 `/path/to/TUZHAN/backups/` 下,与应用同机。

**安装 cron 任务:**

```bash
# 1. 先确认是否已配置过(如果有输出,说明已存在,跳过下面的安装步骤)
crontab -l 2>/dev/null | grep backup_db.py

# 2. 没有则追加(每天凌晨 3:30 执行一次)
( crontab -l 2>/dev/null; echo "30 3 * * * cd /path/to/TUZHAN && /path/to/TUZHAN/venv/bin/python3 scripts/backup_db.py --env production >> /var/log/tuzhan-backup.log 2>&1" ) | crontab -

# 3. 验证已写入
crontab -l | grep backup_db.py
```

**手动跑一次确认脚本可用:**

```bash
cd /path/to/TUZHAN && . venv/bin/activate && python3 scripts/backup_db.py --env production
ls -lh backups/
```

应该能看到形如 `prod_2026-04-07.sqlite` 的文件。

## 🔄 更新代码

```bash
cd /path/to/TUZHAN
git pull origin main
. venv/bin/activate
pip install -r requirements.txt  # 检查依赖变更
sudo systemctl restart tuzhan
```

## 📁 目录结构

```
TUZHAN/
├── config/                  # 配置文件
│   ├── settings.yaml        # 环境配置（dev/prod）
│   ├── init_data.json       # 初始化员工数据
│   └── org_chart.yaml       # 组织架构图
├── data/                    # SQLite 数据库（自动创建）
│   ├── dev.sqlite
│   └── prod.sqlite
├── docs/                    # 文档
│   └── deployment.md        # 本文件
├── scripts/                 # 脚本工具
│   ├── init_db.py           # 数据库初始化
│   └── admin.py             # 管理工具
├── src/                     # 源代码
│   ├── main.py              # 入口
│   ├── api/server.py        # FastAPI 应用
│   ├── core/                # 核心模块
│   ├── client/              # 客户端 SDK
│   ├── templates/           # HTML 模板
│   └── static/              # 静态资源
├── venv/                    # Python 虚拟环境
├── .env                     # 环境变量
└── .gitignore
```

## 🛡️ 安全注意事项

1. **Private Key 保密**：员工凭证（`sk-xxx`）请通过安全渠道分发，不要明文存储在代码仓库中
2. **数据库备份**：定期备份 `data/prod.sqlite`
3. **Nginx 隔离**：FastAPI 只绑定 127.0.0.1，不直接暴露到公网
4. **HTTPS**：生产环境建议配置 HTTPS（Let's Encrypt 等）
