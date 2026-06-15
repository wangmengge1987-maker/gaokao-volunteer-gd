const API = "";

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
  const cities = document.getElementById("cities").value.trim();
  const majors = document.getElementById("majors").value.trim();

  if (!track) throw new Error("请选择首选科目");
  if (rechoices.length !== 2) throw new Error("再选科目须恰好选 2 门");
  if (!score || score < 0 || score > 750) throw new Error("请输入有效的高考总分");

  const preferences = {};

  const cityFilterEl = document.querySelector('input[name="city_filter"]:checked');
  const cityFilter = cityFilterEl ? cityFilterEl.value : "prefer";

  if (cities) {
    const cityList = cities.split(/[,，\s]+/).map((s) => s.trim()).filter(Boolean);
    if (cityFilter === "strict" && cityList.length > 5) {
      throw new Error("「仅限这些城市」模式下，城市不能超过 5 个");
    }
    preferences.cities = cityList;
  }
  if (majors) preferences.majors = majors.split(/[,，]/).map((s) => s.trim()).filter(Boolean);

  return { subject_track: track, rechoices, score, preferences, city_filter: cityFilter };
}

async function lookupRank() {
  const banner = document.getElementById("rank-banner");
  const score = parseInt(document.getElementById("score").value, 10);
  const track = document.querySelector('input[name="track"]:checked')?.value;
  if (!score || !track) {
    banner.classList.remove("show");
    return;
  }
  try {
    const data = await api("/api/v1/rank/lookup", { subject_track: track, score });
    banner.textContent = `参考位次：${data.rank.toLocaleString()}（${data.year} 年 ${data.subject_track}类）`;
    banner.classList.add("show");
  } catch {
    banner.classList.remove("show");
  }
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

document.getElementById("score").addEventListener("blur", lookupRank);
document.querySelectorAll('input[name="track"]').forEach((el) => {
  el.addEventListener("change", lookupRank);
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
  const cityList = cities ? cities.split(/[,，\s]+/).map(s => s.trim()).filter(Boolean) : [];

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
