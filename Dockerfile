# 使用 Python 3.11 作为基础镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖（SQLite 等）
RUN apt-get update && apt-get install -y --no-install-recommends \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装
COPY server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制服务端代码
COPY server/ .

# 复制 Web 前端代码
COPY web/ /app/../web/

# 复制数据文件（数据库初始化用）
COPY data/ /data/

# 赋予启动脚本执行权限
RUN chmod +x entrypoint.sh

# 暴露端口（云托管会通过 PORT 环境变量指定）
EXPOSE 80

# 使用启动脚本（自动初始化数据库）
CMD ["./entrypoint.sh"]
