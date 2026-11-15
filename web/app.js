/* 合理用药知识审查平台前端(原生 JS,无构建依赖) */
"use strict";

const API = "/api";
const state = {
  doc: { page: 1, size: 12, total: 0 },
  item: { page: 1, size: 15, total: 0 },
  review: { page: 1, size: 12, total: 0 },
};

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));
const esc = (s) => String(s ?? "").replace(/[&<>"']/g,
  (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

async function api(path, opts = {}) {
  const res = await fetch(API + path, {
    headers: { "Content-Type": "application/json" }, ...opts,
  });
  if (!res.ok) {
    const detail = (await res.json().catch(() => ({}))).detail || res.statusText;
    throw new Error(detail);
  }
  return res.json();
}

// ---------- Tab 切换 ----------
$$(".tab").forEach((tab) => tab.addEventListener("click", () => {
  $$(".tab").forEach((t) => t.classList.remove("active"));
  $$(".view").forEach((v) => v.classList.remove("active"));
  tab.classList.add("active");
  $("#view-" + tab.dataset.view).classList.add("active");
  if (tab.dataset.view === "review") loadReview();
  if (tab.dataset.view === "conflicts") loadConflicts();
  if (tab.dataset.view === "graph") loadGraph();
}));

// ---------- 1. 说明书库 ----------
async function loadDocs() {
  const q = $("#doc-search").value.trim();
  const style = $("#doc-style").value;
  const { page, size } = state.doc;
  const data = await api(`/documents?q=${encodeURIComponent(q)}&style=${style}` +
    `&page=${page}&size=${size}`);
  state.doc.total = data.total;
  $("#doc-total").textContent = `共 ${data.total} 份`;
  $("#doc-page").textContent = `第 ${page} / ${Math.max(1, Math.ceil(data.total / size))} 页`;
  $("#doc-tbody").innerHTML = data.items.map((d) => `
    <tr>
      <td>${esc(d.doc_no)}</td>
      <td><b>${esc(d.generic_name)}</b></td>
      <td>${esc(d.manufacturer)}</td>
      <td>${esc(d.file_type).toUpperCase()}</td>
      <td>${esc(styleName(d.style_family))}</td>
      <td>${d.item_count}</td>
      <td><button class="btn" onclick="openDoc('${esc(d.doc_no)}')">查看原文</button></td>
    </tr>`).join("");
}
const styleName = (s) => ({
  gb_bracket: "国标【】式", cn_number: "中文编号式",
  arabic_number: "阿拉伯数字式", plain_alt: "无编号近义式",
}[s] || s);
$("#doc-search-btn").onclick = () => { state.doc.page = 1; loadDocs(); };
$("#doc-search").addEventListener("keydown", (e) => e.key === "Enter" && loadDocs());
$("#doc-style").onchange = () => { state.doc.page = 1; loadDocs(); };
$("#doc-prev").onclick = () => { if (state.doc.page > 1) { state.doc.page--; loadDocs(); } };
$("#doc-next").onclick = () => {
  if (state.doc.page < Math.ceil(state.doc.total / state.doc.size)) { state.doc.page++; loadDocs(); }
};

// ---------- 2. 抽取明细 ----------
async function loadItems() {
  const type = $("#item-type").value;
  const status = $("#item-status").value;
  const docNo = $("#item-doc").value.trim();
  const { page, size } = state.item;
  const data = await api(`/items?type=${type}&status=${status}` +
    `&doc_no=${encodeURIComponent(docNo)}&page=${page}&size=${size}`);
  state.item.total = data.total;
  $("#item-total").textContent = `共 ${data.total} 条`;
  $("#item-page").textContent = `第 ${page} / ${Math.max(1, Math.ceil(data.total / size))} 页`;
  $("#item-list").innerHTML = data.items.map(renderCard).join("");
}
$("#item-query").onclick = () => { state.item.page = 1; loadItems(); };
$("#item-type").onchange = () => { state.item.page = 1; loadItems(); };
$("#item-status").onchange = () => { state.item.page = 1; loadItems(); };
$("#item-prev").onclick = () => { if (state.item.page > 1) { state.item.page--; loadItems(); } };
$("#item-next").onclick = () => {
  if (state.item.page < Math.ceil(state.item.total / state.item.size)) { state.item.page++; loadItems(); }
};

function renderCard(x) {
  const typeLabel = { interaction: "相互作用", dosage: "剂量", contraindication: "禁忌" }[x.item_type];
  const f = x.fact || {};
  let factHtml = "";
  if (x.item_type === "interaction") {
    factHtml = `
      <div class="kv">
        <div><b>药物 A:</b>${esc(f.drug_a)} <span class="muted">(${esc(f.mentioned_a)})</span></div>
        <div><b>药物 B:</b>${esc(f.drug_b)} <span class="muted">(${esc(f.mentioned_b)})</span></div>
        <div><b>作用类型:</b>${esc(f.interaction_type)}</div>
        <div><b>严重程度:</b><span class="tag tag-${esc(f.severity)}">${esc(f.severity)}</span></div>
      </div>`;
  } else if (x.item_type === "dosage") {
    factHtml = `
      <div class="kv">
        <div><b>人群:</b>${esc(f.population_label)}</div>
        <div><b>用量:</b>${esc(f.dose_value)}</div>
        <div><b>频次:</b>${esc(f.frequency_label || f.frequency)}</div>
        <div><b>给药途径:</b>${esc(f.route || "—")}</div>
      </div>`;
  } else {
    factHtml = `<div class="kv"><div><b>禁忌对象:</b>${esc(f.subject)}</div>
      <div><b>分类:</b>${esc(categoryName(f.category))}</div></div>`;
  }
  return `
  <div class="card" data-id="${x.id}">
    <div class="card-head">
      <span class="tag tag-${x.item_type}">${typeLabel}</span>
      <span class="muted">${esc(x.doc_no)}</span>
      <span class="status status-${x.review_status}">${statusName(x.review_status)}</span>
      <span class="muted">置信度 ${(x.confidence * 100).toFixed(0)}%</span>
    </div>
    <div class="card-body">${factHtml}
      <div class="quote" onclick='openSource(${JSON.stringify({
        docNo: x.doc_no, start: x.source_start, end: x.source_end,
      })})'>📄 点击查看原文出处并高亮:${esc(x.source_text)}</div>
    </div>
    <div class="card-actions">
      <button class="btn btn-primary" onclick="review(${x.id},'approved')">通过</button>
      <button class="btn btn-danger" onclick="review(${x.id},'rejected')">驳回</button>
    </div>
  </div>`;
}
const statusName = (s) => ({ pending: "待审核", approved: "已通过", rejected: "已驳回" }[s] || s);
const categoryName = (c) => ({ population: "人群", disease: "疾病", drug: "药物", other: "其他" }[c] || c);

async function review(id, status) {
  await api(`/items/${id}/review`, {
    method: "POST",
    body: JSON.stringify({ status, reviewer: "值班药师" }),
  });
  loadItems(); loadReviewStats();
}
window.review = review;
window.openDoc = openDoc;
window.openSource = openSource;

// ---------- 原文抽屉 + 高亮 ----------
async function openDoc(docNo) {
  const data = await api(`/documents/${encodeURIComponent(docNo)}`);
  $("#drawer-title").textContent = `${data.generic_name}说明书(${data.doc_no})`;
  $("#drawer-meta").textContent =
    `${data.manufacturer} | ${data.file_type.toUpperCase()} | 共 ${data.sections.length} 个标准章节`;
  $("#drawer-body").innerHTML = data.sections.map((s) =>
    `<div><b style="color:#1d4ed8">${esc(s.raw_heading)}</b>\n${esc(s.text)}</div>`
  ).join("\n\n");
  showDrawer();
}

async function openSource({ docNo, start, end }) {
  const data = await api(`/documents/${encodeURIComponent(docNo)}`);
  const text = data.full_text;
  const before = esc(text.slice(0, start));
  const hit = esc(text.slice(start, end));
  const after = esc(text.slice(end));
  $("#drawer-title").textContent = `原文出处 · ${docNo}`;
  $("#drawer-meta").textContent = `字符偏移 [${start}, ${end}) · 黄色为抽取原句`;
  $("#drawer-body").innerHTML = `${before}<mark class="hl">${hit}</mark>${after}`;
  showDrawer();
  // 滚动到高亮
  setTimeout(() => {
    const mark = $("#drawer-body .hl");
    if (mark) mark.scrollIntoView({ block: "center", behavior: "smooth" });
  }, 60);
}
function showDrawer() {
  $("#drawer").classList.remove("hidden");
  $("#drawer-mask").classList.remove("hidden");
}
$("#drawer-close").onclick = $("#drawer-mask").onclick = () => {
  $("#drawer").classList.add("hidden");
  $("#drawer-mask").classList.add("hidden");
};

// ---------- 3. 知识图谱(SVG 力导向) ----------
let simTimer = null;
async function loadGraph() {
  const sev = $("#graph-severity").value;
  const data = await api(`/graph?severity=${encodeURIComponent(sev)}`);
  $("#graph-stats").textContent = `${data.nodes.length} 个药物节点 · ${data.edges.length} 条相互作用边`;
  const svg = $("#graph-svg");
  const W = svg.clientWidth || 1100, H = 620;
  // 初始化节点位置(环形 + 随机扰动)
  const nodes = data.nodes.map((n, i) => ({
    ...n,
    x: W / 2 + Math.cos(i * 2.4) * (180 + (i % 7) * 22) + Math.random() * 30,
    y: H / 2 + Math.sin(i * 2.4) * (140 + (i % 5) * 26) + Math.random() * 30,
    vx: 0, vy: 0,
  }));
  const idx = Object.fromEntries(nodes.map((n) => [n.id, n]));
  const edges = data.edges
    .filter((e) => idx[e.source] && idx[e.target])
    .map((e) => ({ ...e, s: idx[e.source], t: idx[e.target] }));

  function tick() {
    // 斥力
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const a = nodes[i], b = nodes[j];
        let dx = a.x - b.x, dy = a.y - b.y;
        let d2 = dx * dx + dy * dy || 1;
        const f = 2600 / d2;
        const d = Math.sqrt(d2);
        dx /= d; dy /= d;
        a.vx += dx * f; a.vy += dy * f;
        b.vx -= dx * f; b.vy -= dy * f;
      }
    }
    // 弹簧
    for (const e of edges) {
      let dx = e.t.x - e.s.x, dy = e.t.y - e.s.y;
      const d = Math.hypot(dx, dy) || 1;
      const f = (d - 150) * 0.012;
      dx /= d; dy /= d;
      e.s.vx += dx * f; e.s.vy += dy * f;
      e.t.vx -= dx * f; e.t.vy -= dy * f;
    }
    // 回中 + 阻尼 + 边界
    for (const n of nodes) {
      n.vx += (W / 2 - n.x) * 0.002;
      n.vy += (H / 2 - n.y) * 0.002;
      n.vx *= 0.82; n.vy *= 0.82;
      n.x = Math.max(30, Math.min(W - 30, n.x + n.vx));
      n.y = Math.max(24, Math.min(H - 24, n.y + n.vy));
    }
    draw();
  }
  function draw() {
    const edgeSvg = edges.map((e) =>
      `<line class="edge ${esc(e.severity)}" x1="${e.s.x.toFixed(1)}" y1="${e.s.y.toFixed(1)}"
        x2="${e.t.x.toFixed(1)}" y2="${e.t.y.toFixed(1)}">
        <title>${esc(e.source)} — ${esc(e.target)}｜${esc(e.severity)}｜${esc(e.interaction_type)}</title>
       </line>`).join("");
    const nodeSvg = nodes.map((n) => {
      const r = Math.min(26, 7 + Math.sqrt(n.degree) * 2.4);
      const worst = edges
        .filter((e) => e.source === n.id || e.target === n.id)
        .map((e) => e.severity);
      const color = worst.includes("禁忌") ? "禁忌" : worst.includes("高") ? "高"
        : worst.includes("中") ? "中" : "低";
      return `<g>
        <circle class="node-circle ${color}" cx="${n.x.toFixed(1)}" cy="${n.y.toFixed(1)}" r="${r.toFixed(1)}">
          <title>${esc(n.label)}｜关联 ${n.degree} 条相互作用</title>
        </circle>
        <text class="node-label" x="${n.x.toFixed(1)}" y="${(n.y + r + 12).toFixed(1)}"
          text-anchor="middle">${esc(n.label)}</text></g>`;
    }).join("");
    svg.innerHTML = edgeSvg + nodeSvg;
  }
  clearInterval(simTimer);
  let ticks = 0;
  simTimer = setInterval(() => { tick(); if (++ticks > 240) clearInterval(simTimer); }, 32);
  draw();
}
$("#graph-severity").onchange = loadGraph;

// ---------- 4. 审核台 ----------
async function loadReviewStats() {
  const data = await api("/review/stats");
  const labels = { interaction: "相互作用", dosage: "剂量", contraindication: "禁忌" };
  const sl = { pending: "待审核", approved: "已通过", rejected: "已驳回" };
  $("#review-stats-box").innerHTML = Object.entries(data.stats).map(([type, m]) => `
    <div class="stat-box">
      <h4>${labels[type] || type}</h4>
      <div class="num">${(m.approved || 0) + (m.pending || 0) + (m.rejected || 0)}</div>
      <div class="sub">待 ${m.pending || 0} · 过 ${m.approved || 0} · 驳 ${m.rejected || 0}</div>
    </div>`).join("");
  $("#review-summary").textContent = Object.entries(data.stats)
    .map(([t, m]) => `${labels[t] || t}:待${m.pending || 0}`).join("  ");
}
async function loadReview() {
  const { page, size } = state.review;
  const data = await api(`/items?status=pending&page=${page}&size=${size}`);
  state.review.total = data.total;
  $("#review-page").textContent = `第 ${page} / ${Math.max(1, Math.ceil(data.total / size))} 页`;
  $("#review-list").innerHTML = data.items.length
    ? data.items.map(renderCard).join("")
    : `<div class="card muted">没有待审核条目,可前往「抽取明细」查看全部。</div>`;
  loadReviewStats();
}
$("#review-prev").onclick = () => { if (state.review.page > 1) { state.review.page--; loadReview(); } };
$("#review-next").onclick = () => {
  if (state.review.page < Math.ceil(state.review.total / state.review.size)) { state.review.page++; loadReview(); }
};
$("#approve-page").onclick = async () => {
  const ids = $$("#review-list .card").map((c) => Number(c.dataset.id));
  if (!ids.length) return alert("本页没有待审核条目");
  await api("/review/batch", {
    method: "POST",
    body: JSON.stringify({ ids, status: "approved", reviewer: "值班药师" }),
  });
  loadReview();
};
$("#export-btn").onclick = async () => {
  try {
    const r = await api("/export", { method: "POST" });
    $("#export-result").classList.remove("hidden");
    $("#export-result").textContent =
      `导出成功:${r.path}\n校验和:${r.checksum}\n条目:相互作用 ${r.interactions} / 剂量 ${r.dosages} / 禁忌 ${r.contraindications}`;
  } catch (e) {
    alert("导出失败:" + e.message);
  }
};

// ---------- 5. 冲突检查 ----------
async function loadConflicts() {
  const hideResolved = $("#conflict-hide-resolved").checked;
  const qs = hideResolved ? "?resolved=false" : "";
  const data = await api(`/conflicts${qs}`);
  const typeName = {
    contra_vs_non: "禁忌对立", severity_mismatch: "严重程度矛盾",
    effect_mismatch: "作用方向矛盾",
  };
  const open = data.items.filter((c) => !c.resolved).length;
  const badge = $("#conflict-badge");
  badge.textContent = open;
  badge.classList.toggle("hidden", open === 0);
  $("#conflict-tbody").innerHTML = data.items.map((c) => `
    <tr>
      <td><b>${esc(c.drug_a)}</b> ⇄ <b>${esc(c.drug_b)}</b></td>
      <td><span class="tag tag-interaction">${typeName[c.conflict_type] || c.conflict_type}</span></td>
      <td>${esc(c.doc_no_1)}</td>
      <td>${esc(c.doc_no_2)}</td>
      <td class="muted">${esc(c.detail)}</td>
      <td>${c.resolved ? '<span class="status status-approved">已处理</span>'
        : '<span class="status status-pending">待处理</span>'}</td>
      <td>${c.resolved ? "—" :
        `<button class="btn" onclick="resolveConflict(${c.id})">标记处理</button>`}</td>
    </tr>`).join("") || `<tr><td colspan="7" class="muted">未发现矛盾说法</td></tr>`;
}
window.resolveConflict = async (id) => {
  await api(`/conflicts/${id}/resolve`, { method: "POST" });
  loadConflicts();
};
$("#conflict-hide-resolved").onchange = loadConflicts;

// ---------- 初始化 ----------
loadDocs();
loadItems();
loadReviewStats();
loadConflicts();
