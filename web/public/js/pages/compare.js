// Model comparison: leaderboard, metric and timing charts, retrain, Excel export.
import { dbApi, downloadFromDb, modelApi } from "../api.js";
import { getAuth } from "../auth.js";
import { chart } from "../charts.js";
import { icon } from "../icons.js";
import {
  duration, emptyState, errorState, esc, localTime, MODEL_COLORS, MODEL_SHORT, num, onClick, skeleton, speedBadge, toast,
} from "../ui.js";

function params(p) {
  const entries = Object.entries(p || {});
  return entries.length ? entries.map(([k, v]) => `${k}=${v}`).join(", ") : "mặc định";
}

function kpi(ico, label, value, hint) {
  return `<div class="card kpi"><div class="ico">${icon(ico, 20)}</div>
    <div><div class="label">${label}</div><div class="value">${value}</div><div class="hint">${hint}</div></div></div>`;
}

function loading(view) {
  view.innerHTML = `
    <div class="stack">
      <div class="grid cols-4">${Array(4).fill(`<div class="card">${skeleton({ lines: 2 })}</div>`).join("")}</div>
      <div class="card">${skeleton({ lines: 7 })}</div>
      <div class="grid cols-2"><div class="card">${skeleton({ block: true, lines: 0 })}</div><div class="card">${skeleton({ block: true, lines: 0 })}</div></div>
    </div>`;
}

function leaderboard(report) {
  const rows = [...report.models].sort((a, b) => b.cv_r2_mean - a.cv_r2_mean);
  return rows.map((m, i) => {
    const best = m.model === report.best_model;
    return `
      <tr class="${best ? "best" : ""}">
        <td class="num">${i + 1}</td>
        <td><span class="swatch" style="background:${MODEL_COLORS[m.model]}"></span><b>${esc(m.label)}</b>
          ${best ? `<span class="badge best">${icon("trophy", 12)}Tốt nhất</span>` : ""}</td>
        <td class="num"><b>${num(m.cv_r2_mean, 4)}</b> ± ${num(m.cv_r2_std, 4)}</td>
        <td class="num">${num(m.r2, 4)}</td>
        <td class="num">${num(m.mae, 4)}</td>
        <td class="num">${num(m.mse, 5)}</td>
        <td class="num">${num(m.rmse, 4)}</td>
        <td class="num">${duration(m.train_seconds * 1000)} ${speedBadge(m.train_speed)}</td>
        <td class="num">${duration(m.predict_ms_per_sample)} ${speedBadge(m.predict_speed)}</td>
        <td class="num">${m.n_nonzero_coef}/${m.n_coefficients}</td>
        <td>${esc(params(m.best_params))}</td>
      </tr>`;
  }).join("");
}

function runsTable(runs) {
  if (!runs.length) return emptyState("Chưa có lần train nào trong CSDL", "Bấm “Train lại” để lưu bảng đánh giá đầu tiên.");
  return `<div class="table-wrap"><table class="data">
    <thead><tr><th class="num">Lần</th><th>Thời gian</th><th>Người train</th><th>Mô hình tốt nhất</th>
      <th class="num">CV R² tốt nhất</th><th class="num">RMSE</th><th class="num">Tổng thời gian</th></tr></thead>
    <tbody>${runs.map(r => {
      const best = r.models.find(m => m.is_best) || r.models[0];
      return `<tr><td class="num">#${r.id}</td><td>${localTime(r.created_at)}</td><td>${esc(r.username || "—")}</td>
        <td><span class="swatch" style="background:${MODEL_COLORS[best.model]}"></span>${esc(best.label)}</td>
        <td class="num">${num(best.cv_r2_mean, 4)}</td><td class="num">${num(best.rmse, 4)}</td>
        <td class="num">${r.total_seconds ? duration(r.total_seconds * 1000) : "—"}</td></tr>`;
    }).join("")}</tbody></table></div>`;
}

export default {
  title: "So sánh mô hình (Đánh giá 5 mô hình tuyến tính)",
  subtitle: "Hiệu suất, tốc độ và lịch sử huấn luyện của 5 mô hình tuyến tính — GridSearchCV + KFold(5), xếp hạng theo điểm kiểm định chéo",
  icon: "chart-column",

  async render(view, ctx) {
    loading(view);
    let report;
    try {
      report = await modelApi("/regression/metrics");
    } catch (err) {
      if (!ctx.alive()) return;
      view.innerHTML = `<div class="card">${errorState(err.message, "retry")}</div>`;
      onClick(view, "#retry", () => this.render(view, ctx));
      return;
    }
    if (!ctx.alive()) return;

    const best = report.models.find(m => m.model === report.best_model);
    const fastest = [...report.models].sort((a, b) => a.predict_ms_per_sample - b.predict_ms_per_sample)[0];
    const labels = report.models.map(m => MODEL_SHORT[m.model]);
    const lows = report.models.flatMap(m => [m.cv_r2_mean - m.cv_r2_std, m.r2]);
    const highs = report.models.flatMap(m => [m.cv_r2_mean + m.cv_r2_std, m.r2]);

    view.innerHTML = `
      <div class="stack">
        <div class="grid cols-4">
          ${kpi("trophy", "Mô hình tốt nhất (theo kiểm định chéo)", esc(best.label), esc(params(best.best_params)))}
          ${kpi("target", "Điểm kiểm định chéo (CV R²)", `${num(best.cv_r2_mean, 4)}`, `± ${num(best.cv_r2_std, 4)} qua 5 fold`)}
          ${kpi("gauge", "Hiệu suất trên tập test (R² / RMSE)", `${num(best.r2, 4)} / ${num(best.rmse, 3)}`, `${report.data.test_size} mẫu test, RMSE tính bằng cm`)}
          ${kpi("zap", "Dự đoán nhanh nhất", esc(fastest.label), `${duration(fastest.predict_ms_per_sample)} mỗi mẫu`)}
        </div>

        <section class="card">
          <div class="card-head">
            <div><h2>Bảng xếp hạng 5 mô hình</h2>
              <p class="sub">Train lúc ${localTime(report.trained_at)}${report.trained_by ? ` bởi ${esc(report.trained_by)}` : ""} ·
                ${report.data.train_size} mẫu train / ${report.data.test_size} mẫu test · ${esc(report.data.cv)}</p></div>
            <div class="btn-row">
              <button class="btn" id="retrain" type="button">${icon("refresh-cw", 16)}Train lại</button>
              <button class="btn ghost" id="export" type="button">${icon("download", 16)}Xuất Excel</button>
            </div>
          </div>
          <div id="trainMsg"></div>
          <div class="table-wrap"><table class="data">
            <thead><tr><th class="num">#</th><th>Mô hình</th><th class="num">CV R² (TB ± độ lệch)</th><th class="num">R² test</th>
              <th class="num">MAE</th><th class="num">MSE</th><th class="num">RMSE</th><th class="num">Thời gian train</th>
              <th class="num">Predict / mẫu</th><th class="num">Hệ số ≠ 0</th><th>Tham số tốt nhất</th></tr></thead>
            <tbody>${leaderboard(report)}</tbody>
          </table></div>
          <p class="caption">Badge tốc độ so với mô hình nhanh nhất: <b>Nhanh</b> ≤ ${num(report.speed_thresholds.fast, 1)}×,
            <b>Trung bình</b> ≤ ${num(report.speed_thresholds.medium, 1)}×, còn lại <b>Chậm</b>. Thời gian đo bằng <code>time.perf_counter</code> trên máy chủ.</p>
        </section>

        <div class="grid cols-2">
          <section class="card">
            <div class="card-head"><div><h2>Hiệu suất mô hình: kiểm định chéo và tập test</h2>
              <p class="sub">Thanh = khoảng CV R² ± 1 độ lệch chuẩn; chấm tròn = trung bình CV; chấm vuông = R² test</p></div></div>
            <div class="chart-box"><canvas id="r2Chart" role="img" aria-label="Biểu đồ CV R² và R² test của 5 mô hình"></canvas></div>
          </section>
          <section class="card">
            <div class="card-head"><div><h2>Độ lệch dự đoán trên tập test</h2><p class="sub">MAE và RMSE (cm) — càng thấp càng tốt</p></div></div>
            <div class="chart-box"><canvas id="errChart" role="img" aria-label="Biểu đồ MAE và RMSE của 5 mô hình"></canvas></div>
          </section>
          <section class="card">
            <div class="card-head"><div><h2>Thời gian huấn luyện</h2><p class="sub">Fit cấu hình tốt nhất trên ${report.data.train_size} mẫu (ms)</p></div></div>
            <div class="chart-box short"><canvas id="trainChart" role="img" aria-label="Biểu đồ thời gian huấn luyện"></canvas></div>
          </section>
          <section class="card">
            <div class="card-head"><div><h2>Thời gian dự đoán</h2><p class="sub">Trung bình mỗi mẫu (µs), lặp 200 lần trên tập test</p></div></div>
            <div class="chart-box short"><canvas id="predChart" role="img" aria-label="Biểu đồ thời gian dự đoán"></canvas></div>
          </section>
        </div>

        <section class="card">
          <div class="card-head"><div><h2>Lịch sử huấn luyện đã lưu trong CSDL</h2><p class="sub">Bảng <code>training_runs</code> + <code>model_runs</code> của API CSDL</p></div></div>
          <div id="runs">${skeleton({ lines: 3 })}</div>
        </section>
      </div>`;

    // Accuracy: floating bars for the CV interval, points for CV mean and test R².
    chart(view.querySelector("#r2Chart"), {
      type: "bar",
      data: {
        labels,
        datasets: [
          {
            type: "bar", label: "CV R² ± 1 độ lệch",
            data: report.models.map(m => [m.cv_r2_mean - m.cv_r2_std, m.cv_r2_mean + m.cv_r2_std]),
            backgroundColor: report.models.map(m => MODEL_COLORS[m.model] + "55"),
            borderColor: report.models.map(m => MODEL_COLORS[m.model]), borderWidth: 1, borderRadius: 4,
            borderSkipped: false, barPercentage: 0.45,
          },
          {
            type: "line", label: "CV R² trung bình", data: report.models.map(m => m.cv_r2_mean), showLine: false,
            pointRadius: 5, pointHoverRadius: 7, pointBackgroundColor: "#1E2A5A", pointBorderColor: "#fff", pointBorderWidth: 2,
          },
          {
            type: "line", label: "R² test", data: report.models.map(m => m.r2), showLine: false, pointStyle: "rect",
            pointRadius: 5, pointHoverRadius: 7, pointBackgroundColor: "#F4A261", pointBorderColor: "#fff", pointBorderWidth: 2,
          },
        ],
      },
      options: {
        // An interval chart, not a magnitude: the axis hugs the data instead of starting at 0.
        scales: {
          y: { beginAtZero: false, min: Math.floor((Math.min(...lows) - 0.005) * 100) / 100, max: Math.min(1, Math.ceil((Math.max(...highs) + 0.005) * 100) / 100),
            title: { display: true, text: "R²" }, ticks: { callback: v => num(v, 3) } },
          x: { grid: { display: false } },
        },
        plugins: {
          tooltip: {
            callbacks: {
              label: c => (Array.isArray(c.raw)
                ? ` CV R²: ${num(c.raw[0], 4)} – ${num(c.raw[1], 4)}`
                : ` ${c.dataset.label}: ${num(c.raw, 4)}`),
            },
          },
        },
      },
    });

    chart(view.querySelector("#errChart"), {
      type: "bar",
      data: {
        labels,
        datasets: [
          { label: "MAE", data: report.models.map(m => m.mae), backgroundColor: "#6C63FF", borderRadius: 4, borderColor: "#fff", borderWidth: 1 },
          { label: "RMSE", data: report.models.map(m => m.rmse), backgroundColor: "#B38BFA", borderRadius: 4, borderColor: "#fff", borderWidth: 1 },
        ],
      },
      options: {
        scales: { y: { beginAtZero: true, title: { display: true, text: "cm" } }, x: { grid: { display: false } } },
        plugins: { tooltip: { callbacks: { label: c => ` ${c.dataset.label}: ${num(c.raw, 4)} cm` } } },
      },
    });

    const timing = (canvas, values, unit, speeds) => chart(canvas, {
      type: "bar",
      data: {
        labels,
        datasets: [{
          label: unit, data: values, backgroundColor: report.models.map(m => MODEL_COLORS[m.model]),
          borderRadius: 4, barPercentage: 0.6,
        }],
      },
      options: {
        indexAxis: "y",
        scales: { x: { beginAtZero: true, title: { display: true, text: unit } }, y: { grid: { display: false } } },
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { label: c => ` ${num(c.raw, 3)} ${unit} · ${speeds[c.dataIndex].label} (${num(speeds[c.dataIndex].ratio_to_fastest, 2)}× nhanh nhất)` } },
        },
      },
    });
    timing(view.querySelector("#trainChart"), report.models.map(m => m.train_seconds * 1000), "ms", report.models.map(m => m.train_speed));
    timing(view.querySelector("#predChart"), report.models.map(m => m.predict_ms_per_sample * 1000), "µs", report.models.map(m => m.predict_speed));

    this.loadRuns(view, ctx);

    onClick(view, "#export", async e => {
      if (!getAuth()) { toast("Hãy đăng nhập để xuất Excel"); location.hash = "#/dang-nhap"; return; }
      const btn = e.currentTarget;
      btn.disabled = true;
      try {
        const name = await downloadFromDb("/export/model-runs.xlsx");
        toast(`Đã tải ${name}`);
      } catch (err) {
        toast(err.message);
      } finally {
        btn.disabled = false;
      }
    });

    onClick(view, "#retrain", async e => {
      if (!getAuth()) { toast("Hãy đăng nhập để train lại mô hình"); location.hash = "#/dang-nhap"; return; }
      const btn = e.currentTarget;
      const msg = view.querySelector("#trainMsg");
      btn.disabled = true;
      btn.innerHTML = `${icon("refresh-cw", 16)}Đang train 5 mô hình…`;
      msg.innerHTML = `<div class="notice info" style="margin-bottom:12px">${icon("timer", 18)}GridSearchCV đang chạy trên máy chủ, thường mất vài giây.</div>`;
      try {
        const started = performance.now();
        const fresh = await modelApi("/regression/train", { method: "POST", auth: true });
        const run = await dbApi("/model-runs", {
          method: "POST", auth: true,
          body: {
            trained_at: fresh.trained_at, target: fresh.task.target, train_size: fresh.data.train_size,
            test_size: fresh.data.test_size, best_model: fresh.best_model, total_seconds: fresh.total_seconds,
            models: fresh.models,
          },
        });
        toast(`Train xong sau ${duration(performance.now() - started)} · đã lưu lần train #${run.id}`);
        if (ctx.alive()) this.render(view, ctx);
      } catch (err) {
        msg.innerHTML = `<div class="notice error" style="margin-bottom:12px">${icon("circle-alert", 18)}${esc(err.message)}</div>`;
        btn.disabled = false;
        btn.innerHTML = `${icon("refresh-cw", 16)}Train lại`;
      }
    });
  },

  async loadRuns(view, ctx) {
    const box = view.querySelector("#runs");
    try {
      const data = await dbApi("/model-runs?limit=10");
      if (ctx.alive()) box.innerHTML = runsTable(data.runs);
    } catch (err) {
      if (!ctx.alive()) return;
      box.innerHTML = errorState(err.message, "retryRuns");
      onClick(box, "#retryRuns", () => this.loadRuns(view, ctx));
    }
  },
};
