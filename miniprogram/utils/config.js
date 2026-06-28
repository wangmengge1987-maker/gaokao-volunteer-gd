/**
 * API 配置
 * 生产环境用 Vercel 代理（已加 request 合法域名白名单）
 */
const ENV = 'prod';  // 'dev' 或 'prod'

const ENV_CONFIG = {
  dev: {
    apiBase: 'https://evaluator-unearned-gutter.ngrok-free.dev',
  },
  prod: {
    // ⚠️ 部署到 Vercel 后替换为你的 Vercel 域名
    apiBase: 'https://你的Vercel域名.vercel.app',
  },
};

module.exports = {
  apiBase: ENV_CONFIG[ENV].apiBase,
  env: ENV,
};
