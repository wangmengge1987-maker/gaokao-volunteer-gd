const API = "";

// ── City Segmentation ──

let CITY_SET = null; // lazy-loaded from API
const EXTRA_CITIES = ["北京", "上海", "天津", "重庆"]; // 数据库中可能是区名，补上市级名

async function ensureCitySet() {
  if (CITY_SET) return;
  try {
    const res = await fetch(`${API}/api/v1/cities`);
    const data = await res.json();
    const all = [...data.cities, ...EXTRA_CITIES];
    CITY_SET = new Set(all.map(s => s.trim()));
  } catch {
    // fallback：常见城市兜底
    CITY_SET = new Set([
      "北京","上海","天津","重庆",
      "广州","深圳","珠海","东莞","佛山","中山","惠州","汕头","湛江","肇庆","江门","茂名","韶关","梅州","汕尾","阳江","清远","潮州","揭阳","云浮","河源",
      "武汉","南京","成都","杭州","长沙","西安","昆明","贵阳","南宁","海口","三亚",
      "石家庄","太原","呼和浩特","沈阳","大连","长春","哈尔滨","苏州","无锡","常州",
      "宁波","温州","嘉兴","合肥","福州","厦门","泉州","南昌","济南","青岛","烟台",
      "郑州","洛阳","开封","长沙","株洲","湘潭","衡阳","南宁","桂林","北海",
      "兰州","西宁","银川","乌鲁木齐","拉萨","秦皇岛","邯郸","扬州","镇江","南通",
      "绍兴","阜阳","芜湖","蚌埠","漳州","赣州","九江","宜春","上饶","吉安","抚州",
      "临沂","济宁","泰安","德州","淄博","潍坊","菏泽","枣庄","日照","威海",
      "荆州","宜昌","襄阳","黄冈","十堰","荆门","孝感","黄石","咸宁","恩施",
      "绵阳","德阳","宜宾","南充","泸州","自贡","乐山","眉山","达州","内江",
      "柳州","桂林","梧州","北海","防城港","钦州","贵港","玉林","百色","贺州","河池","来宾","崇左",
      "遵义","六盘水","铜仁","毕节","安顺","黔西南","黔东南","黔南",
      "曲靖","玉溪","保山","昭通","普洱","丽江","临沧","大理","楚雄","红河","文山","西双版纳",
      "咸阳","宝鸡","渭南","延安","汉中","榆林","安康","商洛",
      "酒泉","天水","庆阳","定西","白银","陇南","平凉","张掖",
    ]);
  }
}

function greedySegmentCities(text) {
  if (!text || text.length < 2) return [];
  const result = [];
  let i = 0;
  const maxLen = Math.min(6, text.length);
  while (i < text.length) {
    let found = false;
    // 从最长开始匹配（最长城市名不超过6字）
    for (let len = maxLen; len >= 2; len--) {
      if (i + len > text.length) continue;
      const candidate = text.substring(i, i + len);
      if (CITY_SET && CITY_SET.has(candidate)) {
        result.push(candidate);
        i += len;
        found = true;
        break;
      }
    }
    if (!found) {
      i++; // 跳过无法识别的字符
    }
  }
  return result;
}

function parseCities(input) {
  if (!input || !input.trim()) return [];
  const raw = input.trim();

  // 1) 先用标点/空格分割
  const segments = raw.split(/[,，、/;；\s]+/).map(s => s.trim()).filter(Boolean);
  if (segments.length === 0) return [];

  // 2) 对每个片段，如果长度 >= 3 则尝试城市名分割
  const result = [];
  for (const seg of segments) {
    if (seg.length >= 3) {
      const sub = greedySegmentCities(seg);
      if (sub.length > 0) {
        result.push(...sub);
        continue;
      }
    }
    result.push(seg);
  }

  // 3) 去重（保持顺序）
  return [...new Set(result)];
}

// ── Helpers ──

async function api(path, body) {
  const res = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const msg = data.detail || data.message || `请求失败 (${res.status})`;
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return data;
}

function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

function schoolBadge(level) {
  if (!level) return "";
  const cls = level.replace(/[^a-zA-Z一-鿿]/g, "");
  return `<span class="school-badge ${cls}">${escapeHtml(level)}</span>`;
}

function tierProbColor(tier) {
  if (tier === "冲") return "chong";
  if (tier === "稳") return "wen";
  if (tier === "保") return "bao";
  return "";
}

// Rough probability estimate based on student rank vs reference rank
function estimateProb(studentRank, refRank) {
  if (!refRank || refRank <= 0) return null;
  const ratio = (refRank - studentRank) / refRank;
  if (ratio < -0.3) return 20;
  if (ratio < -0.2) return 30;
  if (ratio < -0.1) return 40;
  if (ratio < 0) return 50;
  if (ratio < 0.1) return 65;
  if (ratio < 0.2) return 75;
  if (ratio < 0.35) return 85;
  return 95;
}

// ── Form Data ──

function getFormData() {
  const track = document.querySelector('input[name="track"]:checked')?.value;
  const rechoices = [...document.querySelectorAll('input[name="rechoice"]:checked')].map((el) => el.value);
  const score = parseInt(document.getElementById("score").value, 10);
  const rank = parseInt(document.getElementById("rank").value, 10);
  const cities = document.getElementById("cities").value.trim();
  const majors = document.getElementById("majors").value.trim();

  if (!track) throw new Error("请选择首选科目");
  if (rechoices.length !== 2) throw new Error("再选科目须恰好选 2 门");
  if (!score || score < 0 || score > 750) throw new Error("请输入有效的高考总分");

  // 2026年广东省本科录取最低分数线校验
  const BACHELOR_LINES = { '物理': 425, '历史': 440 };
  const line = BACHELOR_LINES[track];
  if (score < line) {
    throw new Error(`该分数（${score}分）低于广东省本科普通类（${track}）录取最低分数线（${line}分），系统仅支持本科普通批志愿建议。`);
  }

  const preferences = {};

  const cityFilterEl = document.querySelector('input[name="city_filter"]:checked');
  const cityFilter = cityFilterEl ? cityFilterEl.value : "prefer";

  if (cities) {
    const cityList = parseCities(cities);
    if (cityFilter === "strict" && cityList.length > 5) {
      throw new Error("「仅限这些城市」模式下，城市不能超过 5 个");
    }
    preferences.cities = cityList;
  }
  if (majors) preferences.majors = majors.split(/[,，、/;；\s]+/).map((s) => s.trim()).filter(Boolean);

  const payload = { subject_track: track, rechoices, score, preferences, city_filter: cityFilter };
  if (rank && !isNaN(rank)) payload.rank = rank;
  return payload;
}

// ── Results Rendering ──

function renderResults(data) {
  const section = document.getElementById("results");
  const emptyState = document.getElementById("empty-state");
  const list = document.getElementById("vol-list");
  const disclaimer = document.getElementById("result-disclaimer");
  const badge = document.getElementById("result-badge");

  // Hide empty state, show results
  if (emptyState) emptyState.style.display = "none";
  section.style.display = "block";

  // Badge
  const track = document.querySelector('input[name="track"]:checked')?.value || "";
  badge.textContent = track + "类";

  // Dashboard stats
  document.getElementById("stat-rank").textContent = data.student_rank.toLocaleString();
  document.getElementById("stat-count").textContent = data.volunteers.length;

  // Total plan count
  const totalPlan = data.volunteers.reduce((s, v) => s + (v.plan_count || 0), 0);
  document.getElementById("stat-total-plan").textContent = totalPlan.toLocaleString();

  // Tier counts
  const tiers = { 冲: 0, 稳: 0, 保: 0 };
  data.volunteers.forEach((v) => { if (tiers[v.tier] !== undefined) tiers[v.tier]++; });
  const total = tiers.冲 + tiers.稳 + tiers.保 || 1;

  document.getElementById("legend-chong").textContent = tiers.冲;
  document.getElementById("legend-wen").textContent = tiers.稳;
  document.getElementById("legend-bao").textContent = tiers.保;

  // Tier bar
  document.getElementById("bar-chong").style.width = (tiers.冲 / total * 100) + "%";
  document.getElementById("bar-chong").textContent = tiers.冲 > 0 ? `冲 ${tiers.冲}` : "";
  document.getElementById("bar-wen").style.width = (tiers.稳 / total * 100) + "%";
  document.getElementById("bar-wen").textContent = tiers.稳 > 0 ? `稳 ${tiers.稳}` : "";
  document.getElementById("bar-bao").style.width = (tiers.保 / total * 100) + "%";
  document.getElementById("bar-bao").textContent = tiers.保 > 0 ? `保 ${tiers.保}` : "";

  // Volunteer list
  list.innerHTML = data.volunteers.map((v, i) => {
    const prob = estimateProb(data.student_rank, v.ref_min_rank);
    const probColor = tierProbColor(v.tier);
    return `
    <article class="vol-item">
      <div class="vol-order">${v.order}</div>
      <div class="vol-body">
        <h3>
          ${escapeHtml(v.school_name)}
          ${schoolBadge(v.school_level)}
        </h3>
        <div class="vol-meta">
          <span>${escapeHtml(v.group_name || "")}</span>
          ${v.city ? `<span>📍 ${escapeHtml(v.city)}</span>` : ""}
          <span>👥 计划 ${v.plan_count} 人</span>
          <span>📊 参考位次 ${v.ref_min_rank?.toLocaleString() ?? "暂无"}</span>
          ${v.subject_requirement ? `<span>📌 ${escapeHtml(v.subject_requirement)}</span>` : ""}
        </div>
      </div>
      <div class="vol-tier">
        <span class="tier-tag ${tierProbColor(v.tier)}">${v.tier}</span>
        ${prob !== null ? `
        <div class="prob-bar">
          <div class="prob-fill ${probColor}" style="width:${prob}%"></div>
        </div>` : ""}
        <button type="button" class="btn-sm explain-btn" data-index="${i}">解析</button>
      </div>
    </article>`;
  }).join("");

  disclaimer.textContent = data.disclaimer;

  // Explain buttons
  list.querySelectorAll(".explain-btn").forEach((btn) => {
    btn.addEventListener("click", () => openExplain(data.volunteers[Number(btn.dataset.index)]));
  });

  // Scroll to results
  section.scrollIntoView({ behavior: "smooth", block: "start" });
}

// ── Explain Modal ──

let lastVolunteers = [];

async function openExplain(volunteer) {
  const modal = document.getElementById("modal");
  const title = document.getElementById("modal-title");
  const body = document.getElementById("modal-body");
  title.textContent = `${volunteer.school_name} · ${volunteer.group_name || ""}`;
  body.textContent = "正在生成解读…";
  modal.classList.add("show");

  try {
    const data = await api("/api/v1/explain", { volunteer, question: null });
    body.textContent = data.explanation;
  } catch (e) {
    body.textContent = `解读失败：${e.message}`;
  }
}

function closeModal() {
  document.getElementById("modal").classList.remove("show");
}

// ── Event Listeners ──

document.getElementById("form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const errEl = document.getElementById("form-error");
  const btn = document.getElementById("submit-btn");
  errEl.textContent = "";
  btn.disabled = true;
  btn.textContent = "⏳ 生成中…";

  try {
    const payload = getFormData();
    const data = await api("/api/v1/recommend", payload);
    lastVolunteers = data.volunteers;
    renderResults(data);
  } catch (err) {
    errEl.textContent = err.message;
  } finally {
    btn.disabled = false;
    btn.textContent = "🎯 生成志愿建议";
  }
});

document.getElementById("modal-close").addEventListener("click", closeModal);
document.getElementById("modal").addEventListener("click", (e) => {
  if (e.target.id === "modal") closeModal();
});

// 再选科目最多 2 门
document.querySelectorAll('input[name="rechoice"]').forEach((el) => {
  el.addEventListener("change", () => {
    const checked = document.querySelectorAll('input[name="rechoice"]:checked');
    if (checked.length > 2) el.checked = false;
  });
});

// 城市过滤模式切换时更新提示
function updateCityHint() {
  const hint = document.getElementById("city-hint");
  const filterMode = document.querySelector('input[name="city_filter"]:checked')?.value;
  const cities = document.getElementById("cities").value.trim();
  const cityList = cities ? parseCities(cities) : [];

  if (filterMode === "strict") {
    hint.textContent = cityList.length > 5
      ? `⚠️ 当前 ${cityList.length} 个城市，「仅限这些城市」不能超过 5 个`
      : `💡 已选 ${cityList.length} 个城市，最多 5 个`;
    hint.className = "field-hint" + (cityList.length > 5 ? " warn" : "");
  } else {
    hint.textContent = `💡 选择「仅限这些城市」时最多填 5 个`;
    hint.className = "field-hint";
  }
}

document.querySelectorAll('input[name="city_filter"]').forEach(el => {
  el.addEventListener("change", updateCityHint);
});
document.getElementById("cities").addEventListener("input", updateCityHint);

// 页面加载后预加载城市名单
ensureCitySet();
