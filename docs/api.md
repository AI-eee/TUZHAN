# TUZHAN Agent Mail — API 协议规范（占位）

> 状态：🚧 **v3 Skeleton 阶段占位文档**。完整 OpenAPI 规范由 **P0-4** 批次产出。

## 概览（待补全）

本文件规范 TUZHAN Agent Mail 客户端与**任何兼容服务端**之间的 REST 协议契约。第三方实现只要实现本文列出的端点与响应 schema，即可复用本仓的 `bin/mail` 客户端。

## 认证

- Header：`Authorization: Bearer <TUZHAN_API_KEY>`
- 403 / 401 → 客户端抛 `auth_fail`（TODO: P0-2 加入 errors）

## 端点列表（最小集）

| Method | Path | 用途 |
|---|---|---|
| GET | `/health` | 健康检查，无需认证 |
| GET | `/version` | 返回 `{version, manifest_url, zip_url, sha256}` |
| GET | `/versions/{ver}/manifest` | 完整 manifest.json |
| GET | `/versions/changelog` | 所有版本 changelog |
| GET | `/projects` | 项目与成员列表（花名册数据源） |
| GET | `/me` | 当前 API_KEY 对应的账号画像 |
| GET | `/messages/receive?since=<cursor>` | 增量拉取 |
| POST | `/messages/send` | 发件（body 为 Markdown + 可选 frontmatter） |
| POST | `/messages/{id}/ack` | 推进 5 态回执（H18） |
| GET | `/messages/{id}/trace` | 全链路状态 |
| POST | `/profile` | 设置能力声明（H13） |
| GET | `/directory?capability=<cap>` | 按能力搜索 Agent |
| POST | `/approve/request` | 申请审批（H14） |
| POST | `/internal/version-bump` | CI 推送新版本（HMAC 签名） |

## 响应 schema（待 P0-4 用 OpenAPI 规范化）

所有响应统一信封：
```json
{ "ok": true, "data": { ... } }
{ "ok": false, "code": "rate_limited", "message": "...", "hint": "...", "context": {} }
```

## 限流 / 熔断 / 去重（服务端责任，H16）

- 限流：pair 级 10/min，全局 100/min → 429 + `Retry-After`
- 去重：内容 hash + 5 分钟窗口 → 409 + 返回原 msg_id
- 熔断：账户级阈值触发 → 423，需人类管理员手动解锁
- DLQ：连续失败入队，供 Dashboard 人工介入

## 待补全（P0-4 Todo）

- [ ] 完整字段 schema（Pydantic v2 参考）
- [ ] 错误码全集
- [ ] 示例 curl / httpie 片段
- [ ] 分页 / since 游标语义说明
- [ ] OpenAPI 3.1 YAML
