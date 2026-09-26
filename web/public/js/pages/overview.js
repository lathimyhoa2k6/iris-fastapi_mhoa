// Overview page. Top: the SVM predictor (four sliders -> POST /predict, test accuracy
// from GET /metrics). Below: per-species statistics laid out like docs/ui-reference.png.
// Every number comes from the API (Iris.csv, metrics.json, the SVM itself).
import { modelApi, modelAsset } from "../api.js";
import { chart } from "../charts.js";
import { icon } from "../icons.js";
import {
  cap, errorState, esc, FEATURE_COLORS, FEATURE_SHORT, FEATURES, num, onClick, skeleton, SPECIES_COLORS,
} from "../ui.js";

const DEFAULT_INPUT = { sepal_length: 5.8, sepal_width: 2.7, petal_length: 3.7, petal_width: 1.2 };
const FEATURE_VI = {
  sepal_length: "Chiều dài đài hoa",
  sepal_width: "Chiều rộng đài hoa",
  petal_length: "Chiều dài cánh hoa",
  petal_width: "Chiều rộng cánh hoa",
};
const FEATURE_EN = { sepal_length: "Sepal Length", sepal_width: "Sepal Width", petal_length: "Petal Length", petal_width: "Petal Width" };
const FEATURE_ICON = { sepal_length: "ruler", sepal_width: "move-horizontal", petal_length: "leaf", petal_width: "move-vertical" };

// How to recognise each species; the measured ranges are appended from /dataset/summary.
const IDENTIFY = {
  setosa: [
    "Cánh hoa (petal) rất ngắn và hẹp — nhỏ hơn hẳn hai loài còn lại.",
    "Đài hoa (sepal) ngắn nhưng rộng nhất trong ba loài, dáng hoa bầu và gọn.",
    "Loài dễ nhận ra nhất: chỉ riêng kích thước cánh hoa đã đủ tách Setosa khỏi Versicolor và Virginica.",
  ],
  versicolor: [
    "Kích thước trung gian: cánh hoa dài và rộng vừa phải, lớn hơn Setosa nhưng nhỏ hơn Virginica.",
    "Đài hoa hẹp nhất trong ba loài so với chiều dài của nó.",
    "Dễ nhầm với Virginica ở vùng kích thước giáp ranh — cần xem cùng lúc chiều dài và chiều rộng cánh hoa.",
  ],
  virginica: [
    "Hoa lớn nhất: cánh hoa dài và rộng nhất trong ba loài.",
    "Đài hoa dài nhất trong ba loài.",
    "Những bông nhỏ có kích thước chồng lấn với Versicolor — đây là nơi mô hình dễ nhầm nhất.",
  ],
};

// Kept across re-renders (clicking a species in the sidebar redraws the page) so the sliders keep their values.
let current = null;

const round1 = v => Math.round(v * 10) / 10;
const clamp = (v, r) => Math.min(r.max, Math.max(r.min, v));

function caption(info) {
  return `<p class="caption">Nguồn: ${esc(info.source.replace(/^Wikimedia Commons\s*[-—]\s*/, ""))}, ${esc(info.license)},
    <a href="${esc(info.source_url)}" target="_blank" rel="noopener">${esc(info.source_url.replace("https://", ""))}</a></p>`;
}

function featureControl(f, range, value) {
  return `
    <div class="feature-ctl">
      <div class="feature-head">
        <label for="num-${f}">${esc(FEATURE_VI[f])}<span>${FEATURE_EN[f]} · cm</span></label>
        <input class="input num-input" id="num-${f}" data-feature="${f}" type="number" inputmode="decimal"
          min="${range.min}" max="${range.max}" step="0.1" value="${value.toFixed(1)}">
      </div>
      <div class="range-row">
        <span>${num(range.min, 1)}</span>
        <input type="range" id="rng-${f}" data-feature="${f}" min="${range.min}" max="${range.max}" step="0.1" value="${value}"
          aria-label="${esc(FEATURE_VI[f])} (cm)">
        <span>${num(range.max, 1)}</span>
      </div>
    </div>`;
}

function predictorSkeleton() {
  return `
    <div class="grid predict-layout">
      <div class="card"><div class="predict-left"><div>${skeleton({ block: true, lines: 1 })}</div><div>${skeleton({ lines: 8 })}</div></div></div>
      <div class="card">${skeleton({ lines: 9 })}</div>
    </div>`;
}

function predictorHtml(ranges) {
  return `
    <div class="grid predict-layout">
      <section class="card">
        <div class="predict-left">
          <figure class="predict-figure" id="predFigure">${skeleton({ block: true, lines: 1 })}</figure>
          <div>
            <h2>Điều chỉnh đặc trưng</h2>
            <p class="sub">Kéo các thanh trượt để thay đổi giá trị và xem dự đoán</p>
            <div class="feature-list">${FEATURES.map(f => featureControl(f, ranges[f], current[f])).join("")}</div>
            <button class="btn block" id="predictBtn" type="button">${icon("scan-eye", 16)}Dự đoán</button>
            <p class="caption">Giới hạn thanh trượt = giá trị nhỏ nhất / lớn nhất của từng đặc trưng trong 150 mẫu Iris.</p>
          </div>
        </div>
      </section>
      <section class="card" id="predResult" aria-live="polite">${skeleton({ lines: 9 })}</section>
    </div>`;
}

function figureHtml(data) {
  const author = data.source.replace(/^Wikimedia Commons\s*[-—]\s*/, "");
  return `
    <img class="photo" src="${esc(modelAsset(data.image_url))}" alt="${esc(data.alt_text)}">
    <figcaption class="predict-label"><span>Loài dự đoán</span><b>${esc(data.display_name)}</b><span>${esc(data.vietnamese_name)}</span></figcaption>
    <p class="caption">Nguồn: ${esc(author)}, ${esc(data.license)}${data.source_url
      ? `, <a href="${esc(data.source_url)}" target="_blank" rel="noopener">${esc(data.source_url.replace("https://", ""))}</a>` : ""}</p>`;
}

function resultHtml(data, payload, metrics, summary) {
  const perf = metrics && metrics.performance;
  const accuracy = perf ? `${num(perf.accuracy_test * 100, 2)}%` : "—";
  const accHint = perf ? `accuracy trên ${metrics.data.test_size} mẫu test` : "chưa tải được /metrics";
  const stats = summary.species.find(x => x.species === data.species_key);
  const range = f => `${num(stats.stats[f].min, 1)}–${num(stats.stats[f].max, 1)} cm`;
  const details = FEATURES.map(f => `
    <div class="kv-row">${icon(FEATURE_ICON[f], 22)}<div><div class="kv-label">${esc(FEATURE_VI[f])} (${FEATURE_EN[f]})</div>
      <div class="kv-value">${num(payload[f], 1)} cm</div></div></div>`).join("");
  return `
    <div class="band-title">Kết quả dự đoán SVM</div>
    <div class="notice info" id="staleNote" hidden style="margin-bottom:12px">${icon("info", 18)}Giá trị đã thay đổi — bấm “Dự đoán” để cập nhật kết quả.</div>
    <div class="predict-hero">
      <div>
        <div class="kv-label">Loài dự đoán</div>
        <div class="predict-name"><span class="dot" style="background:${SPECIES_COLORS[data.species_key]}"></span>${esc(data.display_name)}</div>
        <div class="sub">${esc(data.vietnamese_name)} · độ tin cậy ${num(data.confidence * 100, 1)}%</div>
      </div>
      <div class="acc">
        <div class="kv-label">Độ chính xác mô hình</div>
        <div class="acc-value">${accuracy}</div>
        <div class="sub">${esc(accHint)}</div>
      </div>
    </div>
    <div class="result-section">
      <h3>Thông tin chi tiết</h3>
      <div class="kv">${details}</div>
    </div>
    <div class="result-section">
      <h3>Đặc điểm nhận dạng · ${esc(cap(data.species_key))}</h3>
      <ul class="bullets">${IDENTIFY[data.species_key].map(t => `<li>${esc(t)}</li>`).join("")}</ul>
      <p class="caption">Trong dữ liệu (${stats.count} mẫu ${esc(cap(data.species_key))}): cánh hoa dài ${range("petal_length")}, rộng ${range("petal_width")};
        đài hoa dài ${range("sepal_length")}, rộng ${range("sepal_width")}.</p>
    </div>`;
}

function mountPredictor(view, ctx, summary, metrics) {
  const btn = view.querySelector("#predictBtn");
  const box = view.querySelector("#predResult");
  const figure = view.querySelector("#predFigure");
  let shown = null;   // payload of the prediction on screen
  let seq = 0;

  const markStale = () => {
    const note = box.querySelector("#staleNote");
    if (note) note.hidden = !shown || FEATURES.every(f => shown[f] === current[f]);
  };

  view.querySelectorAll('.feature-ctl input[type="range"]').forEach(el => {
    el.addEventListener("input", () => {
      const f = el.dataset.feature;
      current[f] = round1(parseFloat(el.value));
      view.querySelector(`#num-${f}`).value = current[f].toFixed(1);
      markStale();
    });
  });
  view.querySelectorAll(".feature-ctl .num-input").forEach(el => {
    const f = el.dataset.feature;
    const range = { min: parseFloat(el.min), max: parseFloat(el.max) };
    // While typing, move the slider but leave the text alone; clamp and tidy it on change/blur.
    el.addEventListener("input", () => {
      const v = parseFloat(el.value);
      if (!Number.isFinite(v)) return;
      current[f] = round1(clamp(v, range));
      view.querySelector(`#rng-${f}`).value = current[f];
      markStale();
    });
    el.addEventListener("change", () => { el.value = current[f].toFixed(1); });
  });

  const predict = async () => {
    const my = ++seq;
    const payload = { ...current };
    btn.disabled = true;
    try {
      const data = await modelApi("/predict", { method: "POST", body: payload });
      if (my !== seq || !ctx.alive()) return;
      shown = payload;
      figure.innerHTML = figureHtml(data);
      box.innerHTML = resultHtml(data, payload, metrics, summary);
      markStale();
    } catch (err) {
      if (my !== seq || !ctx.alive()) return;
      box.innerHTML = `<div class="band-title">Kết quả dự đoán SVM</div>${errorState(err.message, "retryPredict")}`;
      onClick(box, "#retryPredict", predict);
      if (!shown) figure.innerHTML = "";
    } finally {
      if (my === seq) btn.disabled = false;
    }
  };
  btn.addEventListener("click", predict);
  predict();
}

function arrow(direction) {
  return `<div class="arrow-${direction}" aria-hidden="true"><span class="head a"></span><span class="shaft"></span><span class="head b"></span></div>`;
}

function loading(view) {
  view.innerHTML = `
    <div class="stack">
      ${predictorSkeleton()}
      <div class="grid overview">
        <div class="card area-photo">${skeleton({ block: true, lines: 1 })}</div>
        <div class="card area-parts">${skeleton({ lines: 6 })}</div>
        <div class="card area-donut">${skeleton({ block: true, lines: 0 })}</div>
        <div class="area-side"><div class="card">${skeleton({ lines: 6 })}</div><div class="card">${skeleton({ lines: 4 })}</div></div>
      </div>
    </div>`;
}

export default {
  title: "Phân tích dữ liệu hoa Iris",
  subtitle: "Dự đoán loài bằng SVM, khám phá đặc điểm và so sánh các loài hoa trong bộ dữ liệu Iris",
  icon: "flower-2",

  async render(view, ctx) {
    loading(view);
    let summary, speciesList, metrics;
    try {
      [summary, speciesList, metrics] = await Promise.all([
        modelApi("/dataset/summary"),
        modelApi("/species"),
        modelApi("/metrics").catch(() => null),   // the predictor still works without the accuracy figure
      ]);
    } catch (err) {
      if (!ctx.alive()) return;
      view.innerHTML = `<div class="card">${errorState(err.message, "retry")}</div>`;
      onClick(view, "#retry", () => this.render(view, ctx));
      return;
    }
    if (!ctx.alive()) return;

    // Slider bounds = the real min/max of each measurement over all 150 samples.
    const ranges = Object.fromEntries(FEATURES.map(f => [f, {
      min: Math.min(...summary.species.map(x => x.stats[f].min)),
      max: Math.max(...summary.species.map(x => x.stats[f].max)),
    }]));
    if (!current) current = Object.fromEntries(FEATURES.map(f => [f, round1(clamp(DEFAULT_INPUT[f], ranges[f]))]));

    const s = summary.species.find(x => x.species === ctx.species);
    const info = speciesList.species.find(x => x.species_key === ctx.species);
    const name = cap(s.species);
    const st = s.stats;

    const bars = FEATURES.map(f => `
      <div>
        <div class="bar-label"><span>${esc(FEATURE_SHORT[f])}</span><span>${num(st[f].mean)} cm · ${num(s.mean_shares[f], 1)}%</span></div>
        <div class="track" role="img" aria-label="${esc(FEATURE_SHORT[f])} ${num(s.mean_shares[f], 1)}%">
          <div class="fill" style="width:${s.mean_shares[f]}%;background:${FEATURE_COLORS[f]}"></div>
        </div>
      </div>`).join("");

    const legend = FEATURES.map(f => `
      <li><span class="dot" style="background:${FEATURE_COLORS[f]}"></span><span>${esc(FEATURE_SHORT[f])}</span><b>${num(s.mean_shares[f], 1)}%</b></li>`).join("");

    const statsRows = FEATURES.map(f => `
      <tr><td><span class="swatch" style="background:${FEATURE_COLORS[f]}"></span>${esc(FEATURE_SHORT[f])}</td>
        <td class="num">${num(st[f].mean, 3)}</td><td class="num">${num(st[f].std, 3)}</td>
        <td class="num">${num(st[f].min, 1)}</td><td class="num">${num(st[f].max, 1)}</td></tr>`).join("");

    view.innerHTML = `
      <div class="stack">
      ${predictorHtml(ranges)}
      <div>
      <h2 class="section-title">Thống kê theo loài · ${esc(name)} <span>(chọn loài ở thanh bên)</span></h2>
      <div class="grid overview">
        <section class="card area-photo">
          <div class="card-head"><h2>Hoa Iris ${esc(name)}</h2></div>
          <div class="photo-wrap">
            <div class="dim-v">
              <div class="label">Dài đài hoa trung bình<b>${num(st.sepal_length.mean)} cm</b></div>
              ${arrow("v")}
            </div>
            <img class="photo" src="${esc(modelAsset(info.image_url))}" alt="${esc(info.alt_text)}">
            <div class="dim-h">${arrow("h")}Rộng đài hoa trung bình<b>${num(st.sepal_width.mean)} cm</b></div>
          </div>
          ${caption(info)}
        </section>

        <section class="card area-parts">
          <div class="card-head"><div><h2>Tỷ lệ các bộ phận</h2>
            <p class="sub">Phần của mỗi kích thước trong tổng 4 kích thước trung bình (${num(Object.values(st).reduce((a, v) => a + v.mean, 0))} cm)</p></div></div>
          <div class="bars">${bars}</div>
        </section>

        <section class="card area-donut">
          <div class="band-title">Biểu đồ tỉ lệ các bộ phận của hoa (${esc(name)})</div>
          <div class="donut-wrap">
            <div class="donut-box">
              <canvas id="donut" role="img" aria-label="Biểu đồ tròn tỉ lệ 4 kích thước của ${esc(name)}"></canvas>
              <div class="donut-center"><div><b>${esc(name)}</b><span>${s.count} mẫu</span></div></div>
            </div>
            <ul class="legend">${legend}</ul>
          </div>
          <div class="table-wrap" style="margin-top:16px">
            <table class="data">
              <caption class="sr-only">Thống kê mô tả của ${esc(name)}</caption>
              <thead><tr><th>Đặc trưng (cm)</th><th class="num">Trung bình</th><th class="num">Độ lệch chuẩn</th><th class="num">Nhỏ nhất</th><th class="num">Lớn nhất</th></tr></thead>
              <tbody>${statsRows}</tbody>
            </table>
          </div>
        </section>

        <aside class="area-side">
          <section class="card">
            <div class="band-title">Kết quả phân tích</div>
            <div class="kv">
              <div class="kv-row">${icon("flower-2", 24)}<div><div class="kv-label">Loài hoa</div><div class="kv-value">${esc(name)}</div></div></div>
              <div class="kv-row">${icon("ruler", 24)}<div><div class="kv-label">Chiều dài đài hoa trung bình</div><div class="kv-value">${num(st.sepal_length.mean)} cm</div></div></div>
              <div class="kv-row">${icon("move-horizontal", 24)}<div><div class="kv-label">Chiều rộng đài hoa trung bình</div><div class="kv-value">${num(st.sepal_width.mean)} cm</div></div></div>
              <div class="kv-row">${icon("leaf", 24)}<div><div class="kv-label">Cánh hoa trung bình (dài × rộng)</div><div class="kv-value">${num(st.petal_length.mean)} × ${num(st.petal_width.mean)} cm</div></div></div>
              <div class="kv-row">${icon("chart-pie", 24)}<div><div class="kv-label">Tỷ lệ trong dữ liệu</div><div class="kv-value" style="color:var(--primary)">${num(s.share_of_dataset, 1)}% (${s.count}/${summary.n_samples})</div></div></div>
            </div>
          </section>
          <section class="card">
            <h2 style="margin-bottom:12px">Đặc điểm nổi bật</h2>
            <ul class="bullets">${s.highlights.map(h => `<li>${esc(h)}</li>`).join("")}</ul>
          </section>
          <section class="card tinted remark">
            ${icon("lightbulb", 24)}
            <div><h3>Nhận xét</h3><p>${esc(s.remark)}</p></div>
          </section>
        </aside>
      </div>
      <p class="caption" style="margin-top:14px">Dữ liệu: ${esc(summary.source)} · ${summary.n_samples} mẫu · số liệu tính trực tiếp từ tệp CSV qua API <code>/dataset/summary</code>.</p>
      </div>
      </div>`;

    mountPredictor(view, ctx, summary, metrics);

    chart(view.querySelector("#donut"), {
      type: "doughnut",
      data: {
        labels: FEATURES.map(f => FEATURE_SHORT[f]),
        datasets: [{
          data: FEATURES.map(f => s.mean_shares[f]),
          backgroundColor: FEATURES.map(f => FEATURE_COLORS[f]),
          borderColor: "#fff",
          borderWidth: 2,
          hoverOffset: 6,
        }],
      },
      options: {
        cutout: "58%",
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { label: c => ` ${c.label}: ${num(c.parsed, 1)}% (${num(st[FEATURES[c.dataIndex]].mean)} cm)` } },
        },
      },
    });
  },
};
