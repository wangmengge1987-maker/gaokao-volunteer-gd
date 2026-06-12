# 广东高考志愿填报助手

面向 **广东省 · 本科普通批** 的微信小程序，结合规则引擎（冲/稳/保）与大模型解释，生成可执行的志愿建议草案。

## 架构

```
用户(微信小程序) → API 网关 → FastAPI 后端
                              ├─ 规则引擎（位次/冲稳保/筛选）
                              ├─ SQLite/PostgreSQL（录取与计划数据）
                              └─ Agent 层（LLM 解释与追问，可选）
```

## 目录

| 目录 | 说明 |
|------|------|
| `web/` | **网页版**（推荐，最简单） |
| `miniprogram/` | 微信小程序前端（可选） |
| `server/` | Python FastAPI 后端与推荐引擎 |
| `data/samples/` | 示例 CSV 数据（开发用） |
| `docs/` | 广东政策与部署文档 |
| `agent/prompts/` | LLM 系统提示词 |

## 快速开始

### 网页版（推荐）

```bash
cd server
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
python scripts\init_db.py
uvicorn main:app --reload --port 8000
```

浏览器打开 **http://127.0.0.1:8000** 即可使用。

### 1. 后端（API 文档）

```bash
cd server
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
python scripts/init_db.py
uvicorn main:app --reload --port 8000
```

访问 http://127.0.0.1:8000/docs 查看 API。

### 2. 小程序

1. 安装 [微信开发者工具](https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html)
2. 导入 `miniprogram/` 目录
3. 在 `miniprogram/utils/config.js` 填写后端 API 地址
4. 开发阶段勾选「不校验合法域名」

### 3. 数据导入

将广东省官方一分一段表、招生计划、历年录取数据整理为 CSV，按 `data/samples/` 格式导入：

```bash
python scripts/import_data.py --year 2025
```

## 上线清单

- [ ] 微信小程序注册与 AppID
- [ ] 后端部署（腾讯云/阿里云）+ HTTPS 域名
- [ ] 小程序后台配置 request 合法域名
- [ ] 导入当年官方数据
- [ ] 隐私政策与用户协议（收集分数、选科等个人信息）
- [ ] 免责声明：仅供参考，以广东省教育考试院为准

## 免责声明

本工具仅提供志愿填报参考建议，不构成录取承诺。最终填报请以 [广东省教育考试院](https://eea.gd.gov.cn/) 及院校招生章程为准。
