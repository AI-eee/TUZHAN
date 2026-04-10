import os
import sys
import urllib.request
import urllib.error
import urllib.parse
import json
import argparse
import difflib
import zipfile
import tempfile
import shutil
from datetime import datetime, timedelta

# ================= 配置区 =================
# 你可以通过环境变量设置，也可以直接在这里修改默认值
# 默认指向本地测试服或根据环境变量决定
BASE_URL = os.environ.get("TUZHAN_BASE_URL", "http://118.145.237.44:8888/api")
API_KEY = os.environ.get("TUZHAN_API_KEY", "")
# 默认在 tuzhan_agent_mail/ 目录下存放 inbox/outbox
# 修改原因: 用 os.getcwd() 会导致邮件散落到项目根目录；改为基于脚本自身路径自动定位到 tuzhan_agent_mail/
WORKSPACE_DIR = os.environ.get("TUZHAN_WORKSPACE", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# 本地当前版本号，每次代码升级时修改此处
LOCAL_VERSION = "v2.1.0"
# ==========================================

def get_headers():
    return {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

def generate_standard_filename(metadata):
    """
    [新增原因]: 将无序的 db_record_id.md 改为严格的时间戳标准命名 YYYY-MM-DD_HH-MM-SS_{id}.md，确保文件名能自然按时间排序
    """
    ts = metadata.get("timestamp", "1970-01-01 00:00:00")
    msg_id = metadata.get("id", "unknown")
    # 转换为文件系统安全格式: YYYY-MM-DD_HH-MM-SS
    safe_ts = ts.replace(":", "-").replace(" ", "_")
    return f"{safe_ts}_{msg_id}.md"

def cleanup_old_messages(directory, retention_days):
    """
    [新增原因]: 自动扫描并清理指定目录下超过保留天数的邮件文件
    """
    if not os.path.exists(directory):
        return 0
    now = datetime.now()
    cutoff_date = now - timedelta(days=retention_days)
    deleted_count = 0
    
    for root, dirs, files in os.walk(directory):
        for file in files:
            if not file.endswith(".md"):
                continue
            
            # 优先尝试从标准命名格式中解析出精确时间: YYYY-MM-DD_HH-MM-SS_id.md
            ts_str = file[:19]
            try:
                msg_time = datetime.strptime(ts_str, "%Y-%m-%d_%H-%M-%S")
                if msg_time < cutoff_date:
                    os.remove(os.path.join(root, file))
                    deleted_count += 1
            except ValueError:
                # 如果不是标准命名（旧文件），回退使用文件的最后修改时间来判断
                file_path = os.path.join(root, file)
                mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                if mtime < cutoff_date:
                    os.remove(file_path)
                    deleted_count += 1
                    
    return deleted_count

def request(endpoint, method="GET", data=None):
    url = f"{BASE_URL}{endpoint}"
    req = urllib.request.Request(url, data=data, headers=get_headers(), method=method)
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"HTTP Error for {url}: {e.code} - {e.read().decode('utf-8')}")
        return None
    except Exception as e:
        print(f"Error for {url}: {e}")
        return None

def sync_contacts(quiet=False):
    """
    [新增原因]: 根据用户要求，自动将同事名单规范化保存到本地 contacts 目录，防止 Agent 随意保存，并确保每次发件前自动刷新。
    """
    if not quiet:
        print("正在拉取最新项目和同事名单 (/projects) ...")
    
    projects = request("/projects")
    if not projects or projects.get("status") != "success":
        if not quiet:
            print("获取通讯录失败，请检查 API Key 或网络连通性。")
        return None
        
    contacts_dir = os.path.join(WORKSPACE_DIR, "contacts")
    os.makedirs(contacts_dir, exist_ok=True)
    
    # 统一使用单一的数据源：生成 Markdown 报告
    # 这样可以避免多文件不一致导致的潜在问题，Agent 可以直接从 md 表格中提取 emp_id
    
    md_content = "# TUZHAN 最新项目与同事通讯录\n\n> 注意：此文件由系统自动从服务器同步，**请勿手动修改此文件**。任何手动添加或修改都会在下次同步时被服务器的真实数据覆盖。发信前请优先参考此文件中的 `emp_id`。\n\n"
    
    roster_list = [] # 用于模糊匹配

    for proj in projects.get("data", []):
        proj_name = proj.get('name', '未命名项目')
        md_content += f"## 项目名称: {proj_name}\n\n"
        md_content += "| 姓名/昵称 | 角色 | 工号 (emp_id) |\n"
        md_content += "| --- | --- | --- |\n"
        
        for member in proj.get('members', []):
            nickname = member.get('nickname', '未知')
            role = member.get('role', '未知')
            emp_id = member.get('emp_id', '未知')
            
            md_content += f"| {nickname} | {role} | `{emp_id}` |\n"
            roster_list.append({"nickname": nickname, "emp_id": emp_id, "role": role})
            
        md_content += "\n"

    # 保存唯一的 Markdown 版本
    md_filepath = os.path.join(contacts_dir, "roster.md")
    with open(md_filepath, "w", encoding="utf-8") as f:
        f.write(md_content)

    if not quiet:
        print(f"✅ 通讯录已成功同步并标准化保存至 {contacts_dir}/roster.md")
        # 顺便在终端也打印一下
        print("\n========== 终端预览 ==========")
        print(md_content)
        print("==============================\n")
        
    retention_days = projects.get("config", {}).get("retention_days", 7)
    return roster_list, retention_days

def list_projects():
    # [修改原因]: 直接复用标准化同步逻辑
    sync_contacts(quiet=False)

def resolve_target_emp_id(target, roster_list):
    """
    [新增原因]: 支持通过昵称发件，并且使用 difflib 进行模糊匹配，解决语音输入错别字或记不住工号的问题。
    """
    if not roster_list:
        return target

    # 1. 尝试精确匹配 emp_id (以 TZ 开头)
    for member in roster_list:
        if member["emp_id"] == target:
            return target

    # 2. 尝试精确匹配昵称
    for member in roster_list:
        if member["nickname"] == target:
            return member["emp_id"]

    # 3. 尝试模糊匹配昵称
    nicknames = [m["nickname"] for m in roster_list]
    # cutoff 设为 0.4 可以容忍一定程度的错别字或同音字误差
    matches = difflib.get_close_matches(target, nicknames, n=1, cutoff=0.4)
    
    if matches:
        best_match = matches[0]
        for member in roster_list:
            if member["nickname"] == best_match:
                print(f"⚠️ 提示: 未找到精确匹配的接收人 '{target}'，已通过模糊匹配自动定位到: {best_match} (工号: {member['emp_id']})")
                return member["emp_id"]
                
    return target

def send_message(target, content):
    # [修改原因]: 每次发送前，静默更新一次通讯录，确保拿到的是最新名单，避免员工离职或调动带来的信息滞后
    res = sync_contacts(quiet=True)
    roster_list = res[0] if res else []
    
    if not target or not content:
        print("发送失败：目标标识和邮件内容不能为空。")
        return

    # [修改原因]: 解析 target，支持输入昵称（包含模糊匹配）或直接输入 emp_id
    resolved_emp_id = resolve_target_emp_id(target, roster_list)

    print(f"正在准备向 {resolved_emp_id} 发送邮件...")
    payload = json.dumps({
        "receiver": resolved_emp_id,
        "content": content
    }).encode("utf-8")
    
    send_resp = request("/messages/send", method="POST", data=payload)
    if send_resp and send_resp.get("status") == "success":
        print(f"邮件已成功发送给 {resolved_emp_id}！")
    else:
        print(f"邮件发送失败: {send_resp}")

def send_feedback(content):
    """
    [v2.1.0 变更]: 反馈渠道迁移到 GitHub Issues。本函数不再发送邮件，
    改为打印迁移指引并以非 0 退出码结束，提醒调用方更新流程。
    """
    print("=" * 60)
    print("⚠️  反馈渠道已迁移到 GitHub Issues (v2.1.0)")
    print("=" * 60)
    print()
    print("邮箱系统从 v2.1.0 开始回归 Agent 业务协作本职，")
    print("产品反馈/Bug/功能建议请改为提交 GitHub Issue：")
    print()
    print("  仓库: https://github.com/AI-eee/TUZHAN/issues")
    print()
    print("Agent 推荐用法（一行命令）：")
    print('  gh issue create --repo AI-eee/TUZHAN \\')
    print('    --title "<一句话标题>" \\')
    print('    --body  "<详细描述>"')
    if content:
        print()
        print("你刚才想发送的反馈内容是：")
        print("-" * 60)
        print(content)
        print("-" * 60)
        print("请把上面这段复制到 issue body 里。")
    sys.exit(2)

def sync_inbox_outbox():
    res = sync_contacts(quiet=True)
    retention_days = res[1] if res else 7
    
    print(f"正在使用工作区: {WORKSPACE_DIR}")
    print(f"当前配置: 自动清理保留天数为 {retention_days} 天 (可通过网页端个人主页修改)")
    
    inbox_dir = os.path.join(WORKSPACE_DIR, "inbox")
    outbox_dir = os.path.join(WORKSPACE_DIR, "outbox")
    
    # 创建收件箱和发件箱文件夹
    os.makedirs(inbox_dir, exist_ok=True)
    os.makedirs(outbox_dir, exist_ok=True)

    print(f"\n1. 检查发件箱 (/messages/sent) 并保存到本地 {outbox_dir} ...")
    sent = request("/messages/sent")
    if sent and sent.get("status") == "success":
        count = 0
        for msg in sent.get("data", []):
            receiver_id = msg.get("metadata", {}).get("receiver", "unknown")
            emp_outbox_dir = os.path.join(outbox_dir, receiver_id)
            os.makedirs(emp_outbox_dir, exist_ok=True)
            
            # [修改原因]: 改用新的标准时间戳文件名
            filename = generate_standard_filename(msg.get("metadata", {}))
            filepath = os.path.join(emp_outbox_dir, filename)
            if not os.path.exists(filepath):
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(msg["content"])
                count += 1
        print(f"已将 {count} 条新的发件箱邮件保存到 {outbox_dir}")
    else:
        print("拉取发件箱失败")
    
    print(f"\n2. 检查收件箱 (/messages/receive) 并保存到本地 {inbox_dir} ...")
    received = request("/messages/receive")
    if received and received.get("status") == "success":
        count = 0
        for msg in received.get("data", []):
            sender_id = msg.get("metadata", {}).get("sender", "unknown")
            msg_id = msg.get("metadata", {}).get("id")
            emp_inbox_dir = os.path.join(inbox_dir, sender_id)
            os.makedirs(emp_inbox_dir, exist_ok=True)
            
            # [修改原因]: 改用新的标准时间戳文件名
            filename = generate_standard_filename(msg.get("metadata", {}))
            filepath = os.path.join(emp_inbox_dir, filename)
            if not os.path.exists(filepath):
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(msg["content"])
                
                # [修改原因]: 根据用户最新要求，拉取收件箱时后端已自动标记已读，无需在此处手动调用 ACK 接口
                        
                count += 1
        print(f"已将 {count} 条新的收件箱邮件保存到 {inbox_dir}")
    else:
        print("拉取收件箱失败")

    # [修改原因]: 3. 增加最后一步的自动清理旧邮件逻辑
    print("\n3. 正在执行超期邮件清理检查...")
    del_outbox = cleanup_old_messages(outbox_dir, retention_days)
    del_inbox = cleanup_old_messages(inbox_dir, retention_days)
    if del_outbox > 0 or del_inbox > 0:
        print(f"清理完成: 成功删除了 {retention_days} 天前的旧邮件 (发件箱: {del_outbox} 封, 收件箱: {del_inbox} 封)")
    else:
        print("清理完成: 没有超期的旧邮件需要删除。")

def _save_inbox_messages(messages, inbox_dir):
    """将一批收件箱消息写入本地，已存在的文件直接跳过。返回新写入的数量。"""
    saved = 0
    for msg in messages:
        meta = msg.get("metadata", {}) or {}
        sender_id = meta.get("sender", "unknown")
        emp_inbox_dir = os.path.join(inbox_dir, sender_id)
        os.makedirs(emp_inbox_dir, exist_ok=True)
        filename = generate_standard_filename(meta)
        filepath = os.path.join(emp_inbox_dir, filename)
        if os.path.exists(filepath):
            continue
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(msg.get("content", ""))
        saved += 1
    return saved


def watch_inbox(interval):
    """
    [新增原因]: 守护模式 —— 周期性增量拉取收件箱，让 Agent 协作从「批处理」升级为「准实时」。

    设计要点（避免给用户带来困扰）：
    1. 启动时先做一次全量同步 (sync_inbox_outbox)，保证本地与服务器对齐；
       并取出服务器时间戳作为后续 since 的起点 —— 永远不依赖客户端时钟，
       彻底规避时区漂移/夏令时/机器时间不准带来的「漏拉」或「重复拉」。
    2. 后续每个 tick 都使用 server_time 作为 since 参数，仅拉取新增邮件，
       带宽与延迟都最优；并把每次响应里新的 server_time 用作下一轮的游标。
    3. interval 强制下限 5 秒，防止用户写错参数把服务端打爆。
    4. 单次 tick 出错（网络抖动、服务端 5xx）只打印一行警告，不退出循环。
    5. KeyboardInterrupt (Ctrl+C) 安静退出，不打印 traceback。
    6. 文件去重由 generate_standard_filename + os.path.exists 兜底，
       即使发生 since 边界重复，也不会重复写盘。
    """
    import time

    interval = max(5, int(interval))
    print(f"=== TUZHAN 守护模式 ===")
    print(f"工作目录: {WORKSPACE_DIR}")
    print(f"轮询间隔: {interval} 秒")
    print("启动前先做一次全量同步以对齐本地与服务器…\n")

    sync_inbox_outbox()

    inbox_dir = os.path.join(WORKSPACE_DIR, "inbox")
    os.makedirs(inbox_dir, exist_ok=True)

    # 用一次"空拉取"获取服务器时间作为 since 起点；如果失败则回退到客户端时间
    cursor = None
    probe = request("/messages/receive")
    if probe and probe.get("status") == "success":
        cursor = probe.get("server_time")
    if not cursor:
        cursor = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print(f"\n[守护] 起点游标: {cursor}")
    print("[守护] 开始监听新邮件… (按 Ctrl+C 退出)\n")

    tick = 0
    try:
        while True:
            time.sleep(interval)
            tick += 1
            try:
                # urllib 不支持 GET 的 query 参数，自己拼接
                resp = request(f"/messages/receive?since={urllib.parse.quote(cursor)}")
            except Exception as e:
                print(f"[守护][tick {tick}] 网络异常: {e} — 5 秒后继续")
                continue

            if not resp or resp.get("status") != "success":
                print(f"[守护][tick {tick}] 拉取失败 — 跳过本轮")
                continue

            messages = resp.get("data") or []
            new_count = _save_inbox_messages(messages, inbox_dir)

            # 推进游标 —— 仅在拿到合法 server_time 时推进，避免因服务端临时异常把游标卡死
            new_cursor = resp.get("server_time")
            if new_cursor:
                cursor = new_cursor

            if new_count > 0:
                ts = datetime.now().strftime("%H:%M:%S")
                print(f"[{ts}] 收到 {new_count} 封新邮件，已写入 {inbox_dir}")
            elif tick % 20 == 0:
                # 每 20 个 tick 打一次心跳（约 10 分钟），让用户确认进程还活着
                ts = datetime.now().strftime("%H:%M:%S")
                print(f"[{ts}] 守护中… (cursor={cursor})")
    except KeyboardInterrupt:
        print("\n[守护] 已退出。")
        return


def update_skill():
    """
    [新增原因]: 支持 Agent 自我更新功能，让用户可以通过对话直接把本地的 SKILL.md 和 mail.py 更新到最新版本。
    """
    print("正在连接服务器获取最新版本...")
    # 注意这里因为原始 API 配置 BASE_URL 为 /api，而压缩包在 /api/tuzhan_agent_mail.zip
    url = f"{BASE_URL}/tuzhan_agent_mail.zip"
    
    req = urllib.request.Request(url, headers=get_headers())
    try:
        with urllib.request.urlopen(req) as response:
            zip_data = response.read()
    except Exception as e:
        print(f"更新失败: 无法下载最新版压缩包 ({e})")
        return

    # 创建临时文件保存 zip
    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
        tmp.write(zip_data)
        tmp_path = tmp.name

    try:
        # 当前 mail.py 的绝对路径
        current_script_path = os.path.abspath(__file__)
        # skill 的根目录，即 scripts 的上一级
        skill_root = os.path.dirname(os.path.dirname(current_script_path))
        
        with zipfile.ZipFile(tmp_path, 'r') as zip_ref:
            # 遍历并提取压缩包内的文件
            for file_info in zip_ref.infolist():
                if file_info.is_dir():
                    continue
                
                # 压缩包内路径是 tuzhan_agent_mail/SKILL.md，我们要剥离第一层目录
                parts = file_info.filename.split('/', 1)
                if len(parts) == 2:
                    rel_path = parts[1]
                    target_path = os.path.join(skill_root, rel_path)
                    
                    # 确保目标文件夹存在
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    
                    with zip_ref.open(file_info) as source, open(target_path, "wb") as target:
                        shutil.copyfileobj(source, target)
                        
        print(f"✅ 更新成功！Skill 核心文件已覆盖至: {skill_root}")
        print("您现在可以继续使用最新版的能力了。")
    except Exception as e:
        print(f"更新失败: 解压与覆盖文件时出错 ({e})")
    finally:
        os.remove(tmp_path)

def show_version():
    """
    [修改原因]: 修改为同时展示本地版本号与线上最新版本，对比并提醒用户是否需要升级。
    """
    print(f"=== 本地当前版本: {LOCAL_VERSION} ===")
    
    print("\n正在连接服务器获取线上最新版本信息...")
    resp = request("/version", method="GET")
    
    if not resp or resp.get("status") != "success":
        print("⚠️ 获取线上最新版本失败，请检查网络或 API_KEY 配置。")
        return
        
    online_version = resp["data"]["version"]
    content = resp["data"]["content"]
    
    print(f"=== 线上最新版本: {online_version} ===\n")
    
    if LOCAL_VERSION != online_version:
        print(f"🚀 发现新版本！您的本地版本为 {LOCAL_VERSION}，线上最新为 {online_version}。")
        print("💡 建议您执行 `python3 scripts/mail.py --update` 进行自动升级。\n")
        print("--- 以下为线上最新版本的功能说明 ---")
    else:
        print("✅ 您当前使用的已是最新版本！\n")
        print("--- 以下为当前版本的功能说明 ---")
        
    print(content)
    print("==========================================")

def main():
    parser = argparse.ArgumentParser(description="TUZHAN Agent邮件协作中心命令行工具")
    parser.add_argument("--list", action="store_true", help="拉取并查看当前项目和同事名单")
    parser.add_argument("--send", action="store_true", help="发送邮件")
    parser.add_argument("--feedback", action="store_true", help="给 TUZHAN 发送产品迭代建议")
    parser.add_argument("--update", action="store_true", help="自我更新 Skill (下载并覆盖最新的 SKILL.md 和 mail.py)")
    parser.add_argument("--version", action="store_true", help="查看当前最新版本的功能特性说明")
    parser.add_argument("--watch", action="store_true", help="守护模式：周期性增量拉取新邮件 (Ctrl+C 退出)")
    parser.add_argument("--interval", type=int, default=30, help="--watch 的轮询间隔秒数 (默认 30 秒, 最小 5 秒)")
    parser.add_argument("--target", type=str, help="目标同事的昵称或工号 (发送邮件时必填)")
    # 保留对旧参数的兼容
    parser.add_argument("--target_emp_id", type=str, help=argparse.SUPPRESS)
    parser.add_argument("--content", type=str, help="Markdown 格式的邮件正文 (发送邮件或反馈时必填)")
    
    args = parser.parse_args()

    # 特殊命令无需校验 API_KEY
    if args.version:
        show_version()
        return

    if not API_KEY:
        print("错误: 未配置 API_KEY！")
        print("请在脚本中直接修改 API_KEY，或者通过环境变量 TUZHAN_API_KEY 传入。")
        print("示例: export TUZHAN_API_KEY='sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'")
        sys.exit(1)

    # 兼容旧版本参数传入
    target_value = args.target or args.target_emp_id

    if args.list:
        list_projects()
    elif args.send:
        if not target_value or not args.content:
            print("错误: 发送邮件时必须提供 --target 和 --content 参数。")
            sys.exit(1)
        send_message(target_value, args.content)
    elif args.feedback:
        if not args.content:
            print("错误: 发送反馈时必须提供 --content 参数。")
            sys.exit(1)
        send_feedback(args.content)
    elif args.update:
        update_skill()
    elif args.watch:
        watch_inbox(args.interval)
    else:
        # 默认行为：同步收件箱和发件箱
        sync_inbox_outbox()

if __name__ == "__main__":
    main()
