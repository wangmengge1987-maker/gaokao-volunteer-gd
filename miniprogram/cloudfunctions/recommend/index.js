// 云函数入口：代理调后端推荐API
const API_BASE = 'https://gaokao-api-274470-6-1443956945.sh.run.tcloudbase.com';

// 内置 https 模块发请求（兼容 Node.js 12+）
const https = require('https');
const http = require('http');

function httpRequest(url, method = 'POST', data = null) {
  return new Promise((resolve, reject) => {
    const urlObj = new URL(url);
    const isHttps = urlObj.protocol === 'https:';
    const mod = isHttps ? https : http;
    const body = data ? JSON.stringify(data) : '';
    const options = {
      hostname: urlObj.hostname,
      port: urlObj.port || (isHttps ? 443 : 80),
      path: urlObj.pathname + urlObj.search,
      method,
      headers: { 'Content-Type': 'application/json' },
      timeout: 30000
    };
    if (body) options.headers['Content-Length'] = Buffer.byteLength(body);
    const req = mod.request(options, (res) => {
      let chunks = [];
      res.on('data', chunk => chunks.push(chunk));
      res.on('end', () => {
        const str = Buffer.concat(chunks).toString();
        try { resolve(JSON.parse(str)); }
        catch(e) { reject(new Error('响应解析失败: ' + str.slice(0, 200))); }
      });
    });
    req.on('error', reject);
    req.on('timeout', () => { req.destroy(); reject(new Error('请求超时')); });
    if (body) req.write(body);
    req.end();
  });
}

// 城市智能分割（同网页版逻辑）
const EXTRA_CITIES = ["北京", "上海", "天津", "重庆"];
const FALLBACK_CITIES = [
  "北京","上海","天津","重庆",
  "广州","深圳","珠海","东莞","佛山","中山","惠州","汕头","湛江","肇庆","江门","茂名","韶关","梅州","汕尾","阳江","清远","潮州","揭阳","云浮","河源",
  "武汉","南京","成都","杭州","长沙","西安","昆明","贵阳","南宁","海口","三亚",
  "石家庄","太原","呼和浩特","沈阳","大连","长春","哈尔滨","苏州","无锡","常州",
  "宁波","温州","嘉兴","合肥","福州","厦门","泉州","南昌","济南","青岛","烟台",
  "郑州","洛阳","开封","兰州","西宁","银川","乌鲁木齐","拉萨",
  "秦皇岛","邯郸","扬州","镇江","南通","绍兴","阜阳","芜湖","蚌埠","漳州","赣州",
  "九江","宜春","上饶","吉安","抚州","临沂","济宁","泰安","德州","淄博","潍坊",
  "菏泽","枣庄","日照","威海","荆州","宜昌","襄阳","黄冈","十堰","荆门","孝感","黄石","咸宁","恩施",
  "绵阳","德阳","宜宾","南充","泸州","自贡","乐山","眉山","达州","内江",
  "柳州","桂林","梧州","北海","防城港","钦州","贵港","玉林","百色","贺州","河池","来宾","崇左",
  "遵义","六盘水","铜仁","毕节","安顺","黔西南","黔东南","黔南",
  "曲靖","玉溪","保山","昭通","普洱","丽江","临沧","大理","楚雄","红河","文山","西双版纳",
  "咸阳","宝鸡","渭南","延安","汉中","榆林","安康","商洛",
  "酒泉","天水","庆阳","定西","白银","陇南","平凉","张掖"
];

// 从服务器获取城市列表，失败则用FALLBACK
async function fetchCitySet() {
  try {
    const data = await httpRequest(API_BASE + '/api/v1/cities', 'GET');
    const all = [...(data.cities || []), ...EXTRA_CITIES];
    return new Set(all.map(s => s.trim()));
  } catch {
    return new Set(FALLBACK_CITIES);
  }
}

function greedySegmentCities(text, citySet) {
  if (!text || text.length < 2) return [];
  const result = [];
  let i = 0;
  const maxLen = Math.min(6, text.length);
  while (i < text.length) {
    let found = false;
    for (let len = maxLen; len >= 2; len--) {
      if (i + len > text.length) continue;
      const candidate = text.substring(i, i + len);
      if (citySet.has(candidate)) {
        result.push(candidate);
        i += len;
        found = true;
        break;
      }
    }
    if (!found) i++;
  }
  return result;
}

function parseCities(input, citySet) {
  if (!input || !input.trim()) return [];
  const raw = input.trim();
  // 按标点/空格分割
  const segments = raw.split(/[,，、/;；\s]+/).map(s => s.trim()).filter(Boolean);
  if (segments.length === 0) return [];
  const result = [];
  for (const seg of segments) {
    if (seg.length >= 3) {
      const sub = greedySegmentCities(seg, citySet);
      if (sub.length > 0) {
        result.push(...sub);
        continue;
      }
    }
    result.push(seg);
  }
  return [...new Set(result)];
}

// 云函数入口
exports.main = async (event, context) => {
  const { action, ...params } = event;

  try {
    // 城市智能解析（如果是推荐请求，直接用本地列表省时间）
    if (action === 'recommend' && params.preferences?.cities_raw) {
      const citySet = new Set(FALLBACK_CITIES);
      params.preferences.cities = parseCities(params.preferences.cities_raw, citySet);
      delete params.preferences.cities_raw;
    }

    let url = API_BASE;
    switch (action) {
      case 'recommend':
        url += '/api/v1/recommend';
        break;
      case 'rank_lookup':
        url += '/api/v1/rank/lookup';
        break;
      case 'explain':
        url += '/api/v1/explain';
        break;
      case 'health':
        url += '/health';
        break;
      default:
        return { code: -1, message: '未知 action: ' + action };
    }

    const data = await httpRequest(url, 'POST', params);
    return { code: 0, data };
  } catch (err) {
    return { code: -1, message: err.message };
  }
};
