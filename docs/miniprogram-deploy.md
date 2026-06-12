# 微信小程序上线指南

## 1. 注册小程序

1. 登录 [微信公众平台](https://mp.weixin.qq.com/)
2. 注册「小程序」主体（个人/企业；涉及教育咨询类建议企业主体）
3. 获取 **AppID**，填入 `miniprogram/project.config.json`

## 2. 后端部署（HTTPS 必须）

小程序 `wx.request` 仅允许 HTTPS 域名（开发工具可临时关闭校验）。

推荐：

- **腾讯云轻量 + Docker** 部署 FastAPI
- 或 **微信云托管**（与小程序同生态，免部分域名配置）

部署后得到例如：`https://api.example.com`

修改 `miniprogram/utils/config.js`：

```js
const DEV_API_BASE = 'https://api.example.com';
```

## 3. 配置合法域名

小程序后台 → 开发 → 开发管理 → 开发设置 → **服务器域名**

- request 合法域名：填入 API 域名（不含路径）

## 4. 隐私合规

需在小程序内提供：

- 《用户隐私保护指引》（微信后台配置）
- 隐私政策页面（说明收集：分数、选科、偏好）
- 用户同意后再调用推荐接口

## 5. 数据与安全

- 生产环境使用 PostgreSQL，定期备份
- API 建议加：微信登录 `code2session`、请求签名、限流
- 勿在小程序端存放 LLM API Key

## 6. 审核注意

- 文案避免「保录取」「100% 上岸」
- 首页显著位置展示免责声明
- 说明数据来源年份

## 7. 本地联调

```bash
# 终端 1：后端
cd server
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
python scripts/init_db.py
uvicorn main:app --reload --port 8000

# 终端 2：微信开发者工具导入 miniprogram/
# 勾选「不校验合法域名、web-view、TLS 版本」
```
