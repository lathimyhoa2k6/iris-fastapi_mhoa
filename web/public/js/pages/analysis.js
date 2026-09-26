// Advanced analysis (highlight feature): PCA 2D of the dataset, the SVM confusion matrix
// on the test set and the class balance. Every remark is generated from the numbers.
import { modelApi } from "../api.js";
import { chart } from "../charts.js";
import { icon } from "../icons.js";
import { cap, errorState, esc, num, onClick, skeleton, SPECIES_COLORS, SPECIES_KEYS } from "../ui.js";

// A second encoding next to colour, so the species stay apart for colour-blind readers.
const POINT_STYLE = { setosa: "circle", versicolor: "triangle", virginica: "rectRot" };
const INK = "#1E2A5A";

const pct = (part, whole) => (whole ? (part / whole) * 100 : 0);

function insight(sentences) {
  return `<div class="insight">${icon("lightbulb", 18)}<p>${sentences.filter(Boolean).join(" ")}</p></div>`;
}

// Draws each bar's value just above it (Chart.js has no built-in data labels).
const valueLabels = {
  id: "valueLabels",
  afterDatasetsDraw(c) {
    const g = c.ctx;
    g.save();
    g.font = '600 13px "Be Vietnam Pro", system-ui, sans-serif';
    g.fillStyle = INK;
    g.textAlign = "center";
    g.textBaseline = "bottom";
    c.getDatasetMeta(0).data.forEach((bar, i) => g.fillText(String(c.data.datasets[0].data[i]), bar.x, bar.y - 6));
    g.restore();
  },
};

// ------------------------------------------------------------------ PCA

function pcaRemark(pca) {
  const [r1, r2] = pca.explained_variance_ratio;
  const total = (r1 + r2) * 100;
  const kept = total >= 90 ? "gần như toàn bộ" : total >= 70 ? "phần lớn" : "chỉ một phần";
  const sentences = [`PC1 và PC2 giữ lại ${num(total, 1)}% phương sai của 4 đặc trưng đã chuẩn hoá (PC1 ${num(r1 * 100, 1)}%, PC2 ${num(r2 * 100, 1)}%),
    nên hình 2D thể hiện ${kept} cấu trúc dữ liệu.`];

  const pc1 = Object.fromEntries(SPECIES_KEYS.map(s => [s, pca.points.filter(p => p.species === s).map(p => p.pc1)]));
  const span = s => [Math.min(...pc1[s]), Math.max(...pc1[s])];
  const pairs = [];
  SPECIES_KEYS.forEach((a, i) => SPECIES_KEYS.slice(i + 1).forEach(b => {
    const [a0, a1] = span(a);
    const [b0, b1] = span(b);
    const lo = Math.max(a0, b0);
    const hi = Math.min(a1, b1);
    const inside = lo <= hi ? [...pc1[a], ...pc1[b]].filter(x => x >= lo && x <= hi).length : 0;
    pairs.push({ a, b, lo, hi, gap: lo - hi, inside, total: pc1[a].length + pc1[b].length });
  }));

  SPECIES_KEYS.forEach(s => {
    const own = pairs.filter(p => p.a === s || p.b === s);
    if (own.every(p => p.gap > 0)) {
      const gap = Math.min(...own.map(p => p.gap));
      sentences.push(`${cap(s)} tách biệt rõ: trên trục PC1, cả ${pc1[s].length} điểm nằm riêng một cụm, cách loài gần nhất ${num(gap, 2)} đơn vị.`);
    }
  });
  pairs.filter(p => p.gap <= 0).forEach(p => {
    sentences.push(`${cap(p.a)} và ${cap(p.b)} chồng lấn một phần: ${p.inside}/${p.total} điểm của hai loài nằm trong đoạn PC1 chung
      [${num(p.lo, 2)}; ${num(p.hi, 2)}] — đây là vùng dễ nhầm lẫn khi phân loại.`);
  });
  return insight(sentences);
}

function drawPca(card, pca) {
  const [r1, r2] = pca.explained_variance_ratio;
  const datasets = SPECIES_KEYS.map(s => ({
    label: cap(s),
    data: pca.points.filter(p => p.species === s).map(p => ({ x: p.pc1, y: p.pc2, m: p.measurements })),
    pointStyle: POINT_STYLE[s],
    backgroundColor: SPECIES_COLORS[s] + "D9",
    borderColor: "#fff",
    borderWidth: 1,
    pointRadius: 5,
    pointHoverRadius: 7,
  }));
  card.innerHTML = `
    <div class="card-head"><div><h2>PCA 2D</h2>
      <p class="sub">${pca.n_samples} mẫu, 4 đặc trưng chuẩn hoá (StandardScaler) rồi chiếu xuống 2 thành phần chính</p></div></div>
    <div class="chart-box tall"><canvas id="pcaChart" role="img"
      aria-label="Biểu đồ phân tán PCA 2D của ${pca.n_samples} mẫu, tô màu theo loài"></canvas></div>
    ${pcaRemark(pca)}`;
  chart(card.querySelector("#pcaChart"), {
    type: "scatter",
    data: { datasets },
    options: {
      scales: {
        x: { title: { display: true, text: `PC1 (${num(r1 * 100, 1)}% phương sai)` }, ticks: { callback: v => num(v, 1) } },
        y: { title: { display: true, text: `PC2 (${num(r2 * 100, 1)}% phương sai)` }, ticks: { callback: v => num(v, 1) } },
      },
      plugins: {
        legend: { position: "bottom" },
        tooltip: {
          callbacks: {
            label: c => ` ${c.dataset.label} · PC1 ${num(c.raw.x, 2)}, PC2 ${num(c.raw.y, 2)}`,
            afterLabel: c => ` Số đo (cm): ${c.raw.m.map(v => num(v, 1)).join(" / ")}`,
          },
        },
      },
    },
  });
}

// ------------------------------------------------------------------ confusion matrix

function matrixRemark(labels, cm, accuracy) {
  const total = cm.flat().reduce((a, v) => a + v, 0);
  const correct = labels.reduce((a, _, i) => a + cm[i][i], 0);
  const wrong = total - correct;
  const sentences = [`Trên ${total} mẫu test, SVM phân loại đúng ${correct} mẫu (accuracy ${num(accuracy * 100, 2)}%) và sai ${wrong} mẫu.`];

  const errors = [];
  labels.forEach((a, i) => labels.forEach((b, j) => {
    if (i !== j && cm[i][j] > 0) errors.push(`${cm[i][j]} mẫu ${cap(a)} bị dự đoán thành ${cap(b)}`);
  }));
  if (errors.length) sentences.push(`Nhầm lẫn: ${errors.join("; ")}.`);

  const clean = labels.filter((_, i) => labels.every((__, j) => i === j || (cm[i][j] === 0 && cm[j][i] === 0)));
  if (clean.length && wrong) {
    sentences.push(`${clean.map(cap).join(", ")} không bị nhầm lần nào — mọi lỗi đều nằm giữa ${labels.filter(l => !clean.includes(l)).map(cap).join(" và ")}.`);
  } else if (!wrong) {
    sentences.push("Không có mẫu nào bị phân loại sai.");
  }
  return insight(sentences);
}

function drawMatrix(card, metrics) {
  const { labels, confusion_matrix: cm, accuracy_test: accuracy } = metrics.performance;
  const params = Object.entries(metrics.model.best_params || {}).map(([k, v]) => `${k}=${v}`).join(", ");
  const rows = labels.map((actual, i) => {
    const rowTotal = cm[i].reduce((a, v) => a + v, 0);
    const cells = labels.map((predicted, j) => {
      const v = cm[i][j];
      const cls = i === j ? "diag" : v > 0 ? "miss" : "";
      const title = `Thực tế ${cap(actual)} → dự đoán ${cap(predicted)}: ${v} mẫu`;
      return `<td class="${cls}" title="${esc(title)}">${v}<small>${num(pct(v, rowTotal), 0)}% hàng</small></td>`;
    }).join("");
    const head = i === 0 ? `<th class="axis axis-y" rowspan="${labels.length}" scope="rowgroup"><span>Thực tế</span></th>` : "";
    return `<tr>${head}<th class="row-h" scope="row"><span class="swatch" style="background:${SPECIES_COLORS[actual]}"></span>${esc(cap(actual))}</th>${cells}</tr>`;
  }).join("");

  card.innerHTML = `
    <div class="card-head"><div><h2>Confusion Matrix</h2>
      <p class="sub">SVM (${esc(params)}) trên ${metrics.data.test_size} mẫu test · hàng = loài thực tế, cột = loài dự đoán</p></div></div>
    <div class="table-wrap">
      <table class="cm">
        <caption class="sr-only">Ma trận nhầm lẫn của SVM trên tập test</caption>
        <colgroup><col class="c-axis"><col class="c-row">${labels.map(() => "<col>").join("")}</colgroup>
        <thead>
          <tr><th></th><th></th><th class="axis" colspan="${labels.length}" scope="colgroup">Dự đoán</th></tr>
          <tr><th></th><th></th>${labels.map(l => `<th scope="col"><span class="swatch" style="background:${SPECIES_COLORS[l]}"></span>${esc(cap(l))}</th>`).join("")}</tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
    <p class="caption">Ô tím = dự đoán đúng (đường chéo), ô đỏ nhạt = dự đoán sai. Tỉ lệ nhỏ trong ô tính theo tổng của hàng (recall của loài đó).</p>
    ${matrixRemark(labels, cm, accuracy)}`;
}

// ------------------------------------------------------------------ class balance

function balanceRemark(counts, n, metrics) {
  const values = SPECIES_KEYS.map(s => counts[s]);
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const sentences = [];
  if (lo === hi) {
    sentences.push(`Bộ dữ liệu cân bằng tuyệt đối: mỗi loài ${lo} mẫu (${num(pct(lo, n), 1)}% trong ${n} mẫu).`);
    sentences.push(`Vì không có lớp nào áp đảo, accuracy là thước đo phù hợp — đoán bừa chỉ đạt khoảng ${num(100 / values.length, 1)}%,
      và mô hình không thể đạt accuracy cao chỉ nhờ luôn đoán lớp đông nhất.`);
  } else {
    sentences.push(`Các lớp không cân bằng: lớp đông nhất gấp ${num(hi / lo, 2)} lần lớp ít nhất,
      nên cần xem thêm precision, recall và F1 từng lớp thay vì chỉ accuracy.`);
  }
  const report = metrics && metrics.performance.classification_report;
  if (report) {
    const support = SPECIES_KEYS.map(s => report[s] && report[s].support);
    if (support.every(v => v !== undefined)) {
      sentences.push(`Tập test chia theo stratify nên giữ đúng tỉ lệ này (${support.map(v => num(v, 0)).join(" / ")} mẫu).`);
    }
  }
  return insight(sentences);
}

function drawBalance(card, summary, metrics) {
  const counts = Object.fromEntries(summary.species.map(s => [s.species, s.count]));
  const values = SPECIES_KEYS.map(s => counts[s]);
  card.innerHTML = `
    <div class="card-head"><div><h2>Phân bố số lượng 3 loài</h2>
      <p class="sub">Đếm trực tiếp từ ${esc(summary.source)} · ${summary.n_samples} mẫu</p></div></div>
    <div class="chart-box short"><canvas id="balanceChart" role="img"
      aria-label="Biểu đồ cột số mẫu mỗi loài: ${SPECIES_KEYS.map(s => `${cap(s)} ${counts[s]}`).join(", ")}"></canvas></div>
    ${balanceRemark(counts, summary.n_samples, metrics)}`;
  chart(card.querySelector("#balanceChart"), {
    type: "bar",
    data: {
      labels: SPECIES_KEYS.map(cap),
      datasets: [{
        label: "Số mẫu", data: values, backgroundColor: SPECIES_KEYS.map(s => SPECIES_COLORS[s]),
        borderRadius: 4, borderSkipped: "bottom", barPercentage: 0.5, maxBarThickness: 120,
      }],
    },
    options: {
      layout: { padding: { top: 22 } },
      scales: {
        y: { beginAtZero: true, suggestedMax: Math.max(...values) * 1.1, title: { display: true, text: "Số mẫu" }, ticks: { precision: 0 } },
        x: { grid: { display: false } },
      },
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: c => ` ${c.raw} mẫu (${num(pct(c.raw, summary.n_samples), 1)}%)` } },
      },
    },
    plugins: [valueLabels],
  });
}

// ------------------------------------------------------------------ page

export default {
  title: "Phân tích nâng cao",
  subtitle: "PCA 2D, ma trận nhầm lẫn của SVM và phân bố số lượng 3 loài trong bộ dữ liệu Iris",
  icon: "chart-scatter",

  render(view, ctx) {
    view.innerHTML = `
      <section class="stack" aria-labelledby="advTitle">
        <h2 class="section-title" id="advTitle" style="margin-bottom:-6px">Phân tích nâng cao</h2>
        <div class="grid cols-2">
          <section class="card" id="pcaCard">${skeleton({ block: true, lines: 3 })}</section>
          <section class="card" id="cmCard">${skeleton({ block: true, lines: 3 })}</section>
        </div>
        <section class="card" id="balanceCard">${skeleton({ block: true, lines: 2 })}</section>
      </section>`;

    const pcaCard = view.querySelector("#pcaCard");
    const cmCard = view.querySelector("#cmCard");
    const balanceCard = view.querySelector("#balanceCard");
    const metricsReq = modelApi("/metrics");
    metricsReq.catch(() => { /* each card reports its own error */ });

    const load = async (card, id, work) => {
      try {
        await work();
      } catch (err) {
        if (!ctx.alive()) return;
        card.innerHTML = errorState(err.message, id);
        onClick(card, `#${id}`, () => this.render(view, ctx));
      }
    };

    load(pcaCard, "retryPca", async () => {
      const pca = await modelApi("/dataset/pca");
      if (ctx.alive()) drawPca(pcaCard, pca);
    });
    load(cmCard, "retryCm", async () => {
      const metrics = await metricsReq;
      if (ctx.alive()) drawMatrix(cmCard, metrics);
    });
    load(balanceCard, "retryBalance", async () => {
      const [summary, metrics] = await Promise.all([modelApi("/dataset/summary"), metricsReq.catch(() => null)]);
      if (ctx.alive()) drawBalance(balanceCard, summary, metrics);
    });
  },
};
