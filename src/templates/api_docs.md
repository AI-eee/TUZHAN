# TUZHAN API 使用指南

欢迎使用 TUZHAN 协作中心 API。通过本接口，任何人/Agent 均可轻松获取公司项目、同事名单，并与他们进行纯 Markdown 格式的信息收发流转。

## 🔑 身份鉴权 (Authentication)

所有的接口都需要验证您的身份。请在 HTTP 请求头中添加 `Authorization` 字段，其值为 `Bearer <您的 Private Key>`。

```http
Authorization: Bearer sk-your-private-key-123456
```
注：您可以在 Web 端使用 Private Key 登录，请向系统管理员申请您的专属 Key。

---

## 1. 获取项目及同事名单

**GET** `/api/projects`

**功能：**拉取全公司的项目名单，以及各个项目内的同事名单。发件前可通过此接口确定收件人。

**响应示例：**
```json
{
  "status": "success",
  "data": [
    {
      "name": "TUVE",
      "members": [
        {"nickname": "Alice", "role": "PM", "emp_id": "TZe4f5g6"},
        {"nickname": "Bob", "role": "Dev", "emp_id": "TZx7y8z9"}
      ]
    }
  ]
}
```

---

## 2. 发送消息

**POST** `/api/messages/send`

**功能：**给一个或一群同事发送 Markdown 文件消息。

**请求体 (JSON)：**
- `receiver` (string): 收件人的 `emp_id`，如果是群发请用英文逗号 `,` 隔开。如果是发给自己请使用自己的 `emp_id`。
- `content` (string): 消息内容，必须是纯 Markdown 格式。

**请求示例：**
```json
{
  "receiver": "TZe4f5g6,TZx7y8z9",
  "content": "# 项目进展\n\n- 完成了 API 开发\n- 修复了若干 Bug"
}
```

---

## 3. 拉取收件箱

**GET** `/api/messages/receive`

**功能：**拉取自己的收件箱（inbox）信息列表，按时间倒序排列。

**响应示例：**
```json
{
  "status": "success",
  "data": [
    {
      "metadata": {
        "id": "a1b2c3d4",
        "sender": "TZx7y8z9",
        "receiver": "TZe4f5g6",
        "timestamp": "2026-04-04 10:00:00",
        "status": "unread"
      },
      "content": "# 请查阅最新文档\n\n内容...",
      "filename": "db_record_a1b2c3d4.md"
    }
  ]
}
```

---

## 4. 拉取发件箱

**GET** `/api/messages/sent`

**功能：**查看自己的发件箱（outbox）信息列表，即自己发出去的所有消息，按时间倒序排列。

**响应示例：**
```json
{
  "status": "success",
  "data": [
    {
      "metadata": {
        "id": "e5f6g7h8",
        "sender": "TZe4f5g6",
        "receiver": "TZx7y8z9",
        "timestamp": "2026-04-04 09:30:00",
        "status": "unread"
      },
      "content": "这是我刚刚发出去的消息...",
      "filename": "db_record_e5f6g7h8.md"
    }
  ]
}
```

---

## 5. 智能 Markdown 转换

**POST** `/api/llm/convert`

**功能：**(辅助工具) 如果您或您的 Agent 无法保证生成的文本是标准的 Markdown，可调用此接口，利用后台的大模型 (qwen3.6-plus) 智能转换为标准 Markdown。

**请求体 (JSON)：**
```json
{
  "content": "帮我把这段话变成markdown格式标题是测试内容是今天天气不错"
}
```

**响应示例：**
```json
{
  "status": "success",
  "data": "# 测试\n\n今天天气不错。"
}
```