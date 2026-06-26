# 广东高考志愿助手 - 项目笔记

## 线上地址（极空间 Z2Pro + Cloudflare Tunnel）
- **Cloudflare Tunnel 网址**: https://ontario-released-explorer-qld.trycloudflare.com/
- **后端**: FastAPI (Python 3.11), uvicorn
- **端口映射**: 容器内 80 → 宿主机 18000
- **架构**: ARM64 (Z2Pro 处理器)
- **镜像**: ghcr.io/wangmengge1987-maker/gaokao-volunteer-gd:latest

## 更新容器步骤
1. 极空间 Docker → 停止 + 删除容器
2. 删除旧镜像
3. 镜像仓库拉取 ghcr.io/...:latest
4. 重新创建容器（端口 80→18000）
5. 浏览器用无痕模式打开验证

## 关键 API
- `GET /health` — 健康检查
- `GET /api/v1/cities` — 城市列表
- `POST /api/v1/rank/lookup` — 分数换算位次
- `POST /api/v1/recommend` — 志愿推荐
- `POST /api/v1/explain` — AI 解读
