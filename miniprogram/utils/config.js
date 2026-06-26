/**
 * API 配置
 * 开发环境：本地 ngrok 或 localhost
 * 生产环境：微信云托管分配的域名
 */

// ===== 在这里切换环境 =====
const ENV = 'prod';  // 'dev' 或 'prod'
// =========================

const ENV_CONFIG = {
  dev: {
    // 本地开发
    apiBase: 'https://evaluator-unearned-gutter.ngrok-free.dev',
  },
  prod: {
    // 微信云托管
    apiBase: 'https://gaokao-api-274470-6-1443956945.sh.run.tcloudbase.com',
  },
};

module.exports = {
  apiBase: ENV_CONFIG[ENV].apiBase,
  env: ENV,
};
