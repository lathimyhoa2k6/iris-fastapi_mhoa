// Shell of the single-page app: hash router, sidebar, header pill and user menu.
import { modelApi, modelAsset } from "./api.js";
import { clearAuth, getAuth, onAuthChange } from "./auth.js";
import { destroyAll } from "./charts.js";
import { icon } from "./icons.js";
import { cap, esc, SPECIES_KEYS, toast } from "./ui.js";

const ROUTES = {
  "tong-quan": { module: "./pages/overview.js", label: "Tổng quan", icon: "layout-dashboard", group: "main" },
  "so-sanh": { module: "./pages/compare.js", label: "So sánh mô hình", icon: "chart-column", group: "main" },
  "phan-loai": { module: "./pages/classify.js", label: "Phân loại SVM", icon: "scan-eye", group: "main" },
  "lich-su": { module: "./pages/history.js", label: "Lịch sử", icon: "history", group: "main" },
  "phan-tich": { module: "./pages/analysis.js", label: "Phân tích nâng cao", icon: "chart-scatter", group: "highlight" },
  "dang-nhap": { module: "./pages/login.js", label: "Đăng nhập", icon: "log-in", group: "hidden" },
};
const DEFAULT_ROUTE = "tong-quan";
const SPECIES_KEY = "iris-species";

const view = document.getElementById("view");
const state = {
  species: readSpecies(),
  speciesInfo: {},   // from GET /species on the model API
  renderId: 0,
  route: null,
};

function readSpecies() {
  try {
    const s = localStorage.getItem(SPECIES_KEY);
    return SPECIES_KEYS.includes(s) ? s : "setosa";
  } catch (_) {
    return "setosa";
  }
}

function currentRoute() {
  const name = location.hash.replace(/^#\/?/, "").split("?")[0];
  return ROUTES[name] ? name : null;
}

// ------------------------------------------------------------------ sidebar

const LINEART = `
<svg class="lineart" viewBox="0 0 180 90" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" aria-hidden="true">
  <path d="M52 89C52 72 50 58 55 42"/>
  <path d="M55 42C45 33 44 20 53 13C59 21 61 32 55 42Z"/>
  <path d="M55 42C64 31 76 29 80 37C72 43 63 45 55 42Z"/>
  <path d="M55 42C44 40 33 42 31 50C41 53 49 49 55 42Z"/>
  <path d="M55 42C56 49 54 56 50 60"/>
  <path d="M51 72C38 64 27 67 22 76C33 79 44 78 51 72Z"/>
  <path d="M130 89C131 76 127 64 132 52"/>
  <path d="M132 52C124 45 124 35 131 30C136 37 137 45 132 52Z"/>
  <path d="M132 52C140 44 150 43 153 50C146 55 139 56 132 52Z"/>
  <path d="M130 74C141 67 152 69 157 77C147 80 137 79 130 74Z"/>
  <path d="M96 89C97 80 95 72 99 64M99 64C94 58 95 51 100 48C104 53 104 59 99 64Z"/>
</svg>`;

function navItem(name) {
  const r = ROUTES[name];
  const active = state.route === name ? " active" : "";
  return `<a class="nav-item${active}" href="#/${name}">${icon(r.icon, 18)}<span>${esc(r.label)}</span></a>`;
}

function renderSidebar() {
  const species = SPECIES_KEYS.map(key => {
    const info = state.speciesInfo[key];
    const active = state.species === key && state.route === "tong-quan" ? " active" : "";
    const thumb = info
      ? `<img class="thumb" src="${esc(modelAsset(info.image_url))}" alt="" title="Ảnh: ${esc(info.source)} (${esc(info.license)})" loading="lazy">`
      : `<span class="thumb"></span>`;
    return `<button class="nav-item${active}" type="button" data-species="${key}">${thumb}<span>${cap(key)}</span></button>`;
  }).join("");

  document.getElementById("sidebar").innerHTML = `
    <div class="side-group">
      <div class="side-title">Trang</div>
      ${Object.keys(ROUTES).filter(n => ROUTES[n].group === "main").map(navItem).join("")}
    </div>
    <div class="side-group">
      <div class="side-title"><span class="star">${icon("sparkles", 14)}</span>Điểm nổi bật</div>
      ${Object.keys(ROUTES).filter(n => ROUTES[n].group === "highlight").map(navItem).join("")}
    </div>
    <div class="side-group">
      <div class="side-title">Các loài hoa</div>
      ${species}
      <p class="side-credit">Ảnh: Wikimedia Commons — nguồn đầy đủ dưới ảnh lớn và trong CREDITS.md.</p>
    </div>
    <div class="side-foot">
      ${LINEART}
      <p class="quote">Mỗi loài hoa đều có vẻ đẹp riêng của nó ♥</p>
      <div class="student">Sinh viên thực hiện<b>La Thị Mỹ Hoà</b>Lớp 24CKDL · Máy học nâng cao</div>
    </div>`;

  document.querySelectorAll("[data-species]").forEach(btn => {
    btn.addEventListener("click", () => setSpecies(btn.dataset.species));
  });
}

function setSpecies(key) {
  state.species = key;
  try { localStorage.setItem(SPECIES_KEY, key); } catch (_) { /* storage blocked */ }
  renderPill();
  if (state.route === "tong-quan") render();
  else location.hash = "#/tong-quan";
}

function renderPill() {
  document.getElementById("viewingPill").innerHTML =
    `${icon("flower-2", 16)}<span>Loài đang xem: <b>${cap(state.species)}</b></span>`;
}

// ------------------------------------------------------------------ user menu

function renderUserMenu() {
  const auth = getAuth();
  const box = document.getElementById("userMenu");
  if (!auth) {
    box.innerHTML = `<a class="btn ghost small" href="#/dang-nhap">${icon("log-in", 16)}Đăng nhập</a>`;
    return;
  }
  const name = auth.user.username;
  box.innerHTML = `
    <button class="user-btn" type="button" aria-haspopup="true" aria-expanded="false">
      <span class="avatar">${esc(name.charAt(0).toUpperCase())}</span><span>${esc(name)}</span>
    </button>
    <div class="menu" role="menu">
      <div class="meta">Đã đăng nhập bằng JWT</div>
      <a href="#/lich-su" role="menuitem">${icon("history", 16)}Lịch sử của tôi</a>
      <button type="button" data-logout role="menuitem">${icon("log-out", 16)}Đăng xuất</button>
    </div>`;
  const btn = box.querySelector(".user-btn");
  const menu = box.querySelector(".menu");
  btn.addEventListener("click", e => {
    e.stopPropagation();
    const open = menu.classList.toggle("open");
    btn.setAttribute("aria-expanded", String(open));
  });
  box.querySelector("[data-logout]").addEventListener("click", () => {
    clearAuth();
    toast("Đã đăng xuất");
  });
}
document.addEventListener("click", () => document.querySelectorAll(".menu.open").forEach(m => m.classList.remove("open")));

// ------------------------------------------------------------------ routing

async function render() {
  const name = currentRoute() || DEFAULT_ROUTE;
  state.route = name;
  const id = ++state.renderId;
  destroyAll();
  renderSidebar();
  renderPill();

  const route = ROUTES[name];
  let page;
  try {
    page = (await import(route.module)).default;
  } catch (err) {
    view.innerHTML = `<div class="card"><div class="state error">${icon("circle-alert", 34)}<b>Lỗi tải trang</b><p>${esc(err.message)}</p></div></div>`;
    return;
  }
  if (id !== state.renderId) return;

  document.getElementById("pageIcon").innerHTML = icon(page.icon || route.icon, 28);
  document.getElementById("pageTitle").textContent = page.title;
  document.getElementById("pageSub").textContent = page.subtitle;
  document.title = `${page.title} · Iris Analytics`;

  const ctx = {
    species: state.species,
    speciesInfo: state.speciesInfo,
    setSpecies,
    alive: () => id === state.renderId,
  };
  view.innerHTML = "";
  try {
    await page.render(view, ctx);
  } catch (err) {
    if (ctx.alive()) {
      view.innerHTML = `<div class="card"><div class="state error">${icon("circle-alert", 34)}<b>Có lỗi khi hiển thị trang</b><p>${esc(err.message)}</p></div></div>`;
    }
  }
}

async function loadSpecies() {
  try {
    const data = await modelApi("/species");
    data.species.forEach(s => { state.speciesInfo[s.species_key] = s; });
    renderSidebar();
  } catch (_) {
    /* thumbnails stay empty; each page shows its own error state */
  }
}

// Old demo links (/?sl=6.5&sw=3.0&pl=5.5&pw=2.0&auto=1) open the SVM classifier page.
if (!location.hash && /[?&](sl|sw|pl|pw|sepal_length)=/.test(location.search)) {
  history.replaceState(null, "", `${location.pathname}${location.search}#/phan-loai`);
}

window.addEventListener("hashchange", render);
onAuthChange(() => {
  renderUserMenu();
  render();
});
renderUserMenu();
render();
loadSpecies();
