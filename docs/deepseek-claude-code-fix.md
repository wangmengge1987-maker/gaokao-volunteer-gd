# Claude Code + DeepSeek 完整修复（含本地代理）

## 问题原因

Claude Code 2.1+ 会把 `role: "system"` 放进 `messages` 数组；DeepSeek 的 Anthropic 接口 **不允许**，只接受顶层 `system` + `messages` 里仅有 `user`/`assistant`。

因此出现：

```
messages[1].role: unknown variant `system`, expected `user` or `assistant`
```

## 解决方式：本地代理（推荐）

### 1. 启动代理（单独开一个 PowerShell 窗口）

```powershell
cd C:\Users\wangm\.claude\deepseek-proxy
.\start.ps1
```

看到 `Listening on http://127.0.0.1:16889` 即成功。可访问 http://127.0.0.1:16889/health 检查。

### 2. 确认 `~/.claude/settings.json`

已配置为：

- `ANTHROPIC_BASE_URL`: `http://127.0.0.1:16889`（走本地代理）
- 仅保留 `ANTHROPIC_AUTH_TOKEN`（不要同时设置 `ANTHROPIC_API_KEY`，否则会 Auth conflict）

### 3. 新开终端运行 Claude Code

```powershell
cd C:\Users\wangm\Projects\gaokao-volunteer-gd
claude
```

在 Claude Code 里：`/model` → 选 **deepseek-v4-flash**（不要选 `[1m]`）。

### 4. 仍异常时

- `/clear` 后重试
- 确认代理窗口未关闭
- 到 https://platform.deepseek.com 检查 API Key 与余额

## 代理做了什么

对 `POST /v1/messages` 请求：

1. 把 `messages` 里所有 `role: system` 合并到顶层 `system`
2. 将 `thinking.type=adaptive` 规范为 `disabled`（DeepSeek 兼容）
3. 工具调用场景补空 `thinking` 块（避免后续 400）

其余请求原样转发到 `https://api.deepseek.com/anthropic`。
