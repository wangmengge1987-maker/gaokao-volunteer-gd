# 微信云托管部署指南

将高考志愿填报后端部署到微信云托管，实现 7×24 小时在线，无需电脑开机。

---

## 一、准备工作

### 1. 注册小程序（获取 AppID）

> 当前你的项目用的还是 `touristappid`（游客模式），需要注册一个小程序才能用云托管。

1. 打开 [微信公众平台](https://mp.weixin.qq.com/)
2. 点击右上角 **「立即注册」** → 选择 **「小程序」**
3. 填写邮箱、密码等信息完成注册
4. 注册完成后，在 **「开发」→「开发管理」→「开发设置」** 中查看 **AppID**

### 2. 开通云托管

1. 登录 [微信云托管控制台](https://console.cloud.tencent.com/cloudbase/run)
2. 关联你刚注册的小程序（使用它的 AppID）
3. 开通服务（有免费额度）

---

## 二、修改小程序配置

### 1. 填入 AppID

打开 `miniprogram/project.config.json`，把 `appid` 改成你的真实 AppID：

```json
{
  "appid": "wx你的真实AppID",
  "projectname": "gaokao-volunteer-gd"
}
```

### 2. 切换 API 地址为生产环境

打开 `miniprogram/utils/config.js`，把 `ENV` 改成 `'prod'`：

```js
const ENV = 'prod';   // ← 改成 prod
```

等云托管部署完成后，把 `apiBase` 换成云托管分配的域名。

---

## 三、部署后端到云托管

### 步骤 1：在微信开发者工具中上传代码

1. 用微信开发者工具打开 `miniprogram/` 目录
2. 填入你的 AppID
3. 点击 **「工具」→「云托管」**
4. 在弹出的窗口中：
   - **环境**：选择你创建的环境
   - **上传方式**：选择 **「上传代码包」**
   - **代码根目录**：选择项目根目录（`gaokao-volunteer-gd`）
   - **Dockerfile 路径**：`server/Dockerfile`
   - **端口**：`80`

### 步骤 2：构建并部署

1. 点击 **「开始上传」**
2. 云托管会自动构建 Docker 镜像并部署
3. 部署完成后会得到一个访问域名，类似：
   ```
   https://xxx-xxx-xxx-xxx.tencentcloudapi.com
   ```

### 步骤 3：验证部署

浏览器访问 `https://你的域名/health`，应该返回：

```json
{"status":"ok","province":"广东","batch":"本科普通批"}
```

---

## 四、更新小程序 API 地址

将 `miniprogram/utils/config.js` 中的 `apiBase` 改为云托管域名：

```js
prod: {
  apiBase: 'https://你的云托管域名.tencentcloudapi.com',
}
```

然后在微信开发者工具中重新上传小程序代码，审核通过后用户就能正常访问了。

---

## 五、小程序后台配置

在 [微信公众平台](https://mp.weixin.qq.com/) → **「开发」→「开发管理」→「开发设置」** 中：

1. 找到 **「服务器域名」**
2. 在 **「request 合法域名」** 中添加你的云托管域名：
   ```
   https://你的云托管域名.tencentcloudapi.com
   ```

---

## 附录：项目文件结构说明

```
gaokao-volunteer-gd/
├── server/                    # 后端代码（上传到云托管）
│   ├── Dockerfile             # Docker 构建文件（已创建）
│   ├── .dockerignore          # Docker 忽略文件（已创建）
│   ├── main.py                # FastAPI 主入口
│   ├── config.py              # 配置，支持 PORT 环境变量
│   ├── requirements.txt       # Python 依赖
│   ├── db/                    # 数据库相关
│   ├── services/              # 业务逻辑
│   └── scripts/               # 数据导入脚本
├── miniprogram/               # 小程序前端
│   └── utils/config.js        # API 地址配置
└── web/                       # Web 前端（可选）
```

---

> **注意**：数据库文件（`gaokao.db`）目前是 SQLite，在云托管容器重启后数据会丢失。
> 如果后续需要持久化数据，建议升级为 PostgreSQL 或 MySQL（云托管支持）。
