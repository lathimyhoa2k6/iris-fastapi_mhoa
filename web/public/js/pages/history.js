// Prediction history of the logged-in user: filters, pagination, actual values, Excel export.
import { dbApi, downloadFromDb, query } from "../api.js";
import { getAuth } from "../auth.js";
import { icon } from "../icons.js";
import {
  duration, emptyState, errorState, esc, localTime, loginPrompt, MODEL_COLORS, num, onClick, skeleton, toast,
} from "../ui.js";

const LABELS = { linear: "Linear Regression", polynomial: "Polynomial Regression", ridge: "Ridge", lasso: "Lasso", elasticnet: "ElasticNet", svm: "SVM (phân loại)" };
const filters = { page: 1, page_size: 10, model: "", date_from: "", date_to: "" };

function inputText(input) {
  return Object.entries(input).map(([k, v]) => `${k}=${typeof v === "number" ? num(v, 2) : v}`).join(", ");
}

function row(p) {
  const predicted = p.task === "regression" ? `${num(p.predicted_value, 3)} cm` : esc(p.predicted_label);
  const error = p.actual_value !== null && p.predicted_value !== null ? num(p.actual_value - p.predicted_value, 3) : "—";
  const actualCell = p.task === "regression"
    ? `<input class="cell-input" type="number" step="0.1" min="0" data-id="${p.id}" value="${p.actual_value ?? ""}" aria-label="Giá trị thật của bản ghi ${p.id}">`
    : "—";
  return `<tr>
    <td>${localTime(p.created_at)}</td>
    <td>${p.task === "regression" ? "Hồi quy" : "Phân loại"}</td>
    <td><span class="swatch" style="background:${MODEL_COLORS[p.model] || "#1E2A5A"}"></span>${esc(LABELS[p.model] || p.model)}</td>
    <td style="max-width:320px">${esc(inputText(p.input))}</td>
    <td class="num"><b>${predicted}</b></td>
    <td class="num">${actualCell}</td>
    <td class="num">${error}</td>
    <td class="num">${duration(p.runtime_ms)}</td>
  </tr>`;
}

export default {
  title: "Lịch sử dự đoán",
  subtitle: "Chỉ hiển thị dự đoán của tài khoản đang đăng nhập — lọc theo ngày và mô hình, xuất Excel",
  icon: "history",

  async render(view, ctx) {
    const auth = getAuth();
    if (!auth) {
      view.innerHTML = `<div class="card">${loginPrompt("Lịch sử dự đoán gắn với tài khoản. Đăng nhập (hoặc dùng tài khoản demo / demo123) để xem.")}</div>`;
      return;
    }

    view.innerHTML = `
      <section class="card">
        <div class="card-head">
          <div><h2>Dự đoán của ${esc(auth.user.username)}</h2><p class="sub" id="summary">Đang tải…</p></div>
          <button class="btn ghost" id="export" type="button">${icon("download", 16)}Xuất Excel (theo bộ lọc)</button>
        </div>
        <form class="form-grid" id="filters" style="grid-template-columns:repeat(auto-fit,minmax(160px,1fr));align-items:end;margin-bottom:14px">
          <label class="field">Mô hình<select class="input" name="model"><option value="">Tất cả</option>
            ${Object.entries(LABELS).map(([k, v]) => `<option value="${k}" ${filters.model === k ? "selected" : ""}>${v}</option>`).join("")}</select></label>
          <label class="field">Từ ngày<input class="input" type="date" name="date_from" value="${filters.date_from}"></label>
          <label class="field">Đến ngày<input class="input" type="date" name="date_to" value="${filters.date_to}"></label>
          <label class="field">Số dòng / trang<select class="input" name="page_size">
            ${[10, 20, 50].map(n => `<option ${filters.page_size === n ? "selected" : ""}>${n}</option>`).join("")}</select></label>
          <div class="btn-row"><button class="btn" type="submit">${icon("funnel", 16)}Lọc</button>
            <button class="btn ghost" type="button" id="clear">Xoá lọc</button></div>
        </form>
        <div id="table"></div>
        <div class="pager" id="pager"></div>
      </section>`;

    const form = view.querySelector("#filters");
    form.addEventListener("submit", e => {
      e.preventDefault();
      const data = new FormData(form);
      Object.assign(filters, {
        page: 1, model: data.get("model"), date_from: data.get("date_from"), date_to: data.get("date_to"),
        page_size: parseInt(data.get("page_size"), 10),
      });
      this.load(view, ctx);
    });
    onClick(view, "#clear", () => {
      Object.assign(filters, { page: 1, model: "", date_from: "", date_to: "" });
      this.render(view, ctx);
    });
    onClick(view, "#export", async e => {
      const btn = e.currentTarget;
      btn.disabled = true;
      try {
        const name = await downloadFromDb(`/export/predictions.xlsx${query({ model: filters.model, date_from: filters.date_from, date_to: filters.date_to })}`);
        toast(`Đã tải ${name}`);
      } catch (err) {
        toast(err.message);
      } finally {
        btn.disabled = false;
      }
    });
    await this.load(view, ctx);
  },

  async load(view, ctx) {
    const table = view.querySelector("#table");
    const pager = view.querySelector("#pager");
    table.innerHTML = skeleton({ lines: 6 });
    pager.innerHTML = "";
    let data;
    try {
      data = await dbApi(`/predictions${query(filters)}`, { auth: true });
    } catch (err) {
      if (!ctx.alive()) return;
      table.innerHTML = errorState(err.message, "retry");
      onClick(table, "#retry", () => this.load(view, ctx));
      return;
    }
    if (!ctx.alive()) return;

    const filtered = filters.model || filters.date_from || filters.date_to;
    view.querySelector("#summary").textContent = `${data.total} bản ghi${filtered ? " khớp bộ lọc" : ""} · lưu trong bảng predictions`;
    if (!data.items.length) {
      table.innerHTML = filtered
        ? emptyState("Không có bản ghi khớp bộ lọc", "Thử bỏ bớt điều kiện lọc.")
        : emptyState("Chưa có dự đoán nào", "Vào Phân loại SVM, dự đoán rồi bấm “Lưu vào lịch sử”.",
          `<a class="btn" href="#/phan-loai">${icon("scan-eye", 16)}Mở Phân loại SVM</a>`);
      return;
    }
    table.innerHTML = `<div class="table-wrap"><table class="data">
      <thead><tr><th>Thời gian</th><th>Tác vụ</th><th>Mô hình</th><th>Đầu vào</th><th class="num">Dự đoán</th>
        <th class="num">Giá trị thật</th><th class="num">Sai số</th><th class="num">Thời gian chạy</th></tr></thead>
      <tbody>${data.items.map(row).join("")}</tbody></table></div>`;
    pager.innerHTML = `
      <span>Trang ${data.page}/${data.pages} · ${data.total} bản ghi</span>
      <div class="btn-row">
        <button class="btn ghost small" id="prev" ${data.page <= 1 ? "disabled" : ""}>${icon("chevron-left", 14)}Trước</button>
        <button class="btn ghost small" id="next" ${data.page >= data.pages ? "disabled" : ""}>Sau${icon("chevron-right", 14)}</button>
      </div>`;
    onClick(pager, "#prev", () => { filters.page -= 1; this.load(view, ctx); });
    onClick(pager, "#next", () => { filters.page += 1; this.load(view, ctx); });

    table.querySelectorAll(".cell-input").forEach(el => {
      el.addEventListener("change", async () => {
        const value = el.value === "" ? null : parseFloat(el.value);
        try {
          await dbApi(`/predictions/${el.dataset.id}`, { method: "PATCH", auth: true, body: { actual_value: value } });
          toast("Đã cập nhật giá trị thật");
          this.load(view, ctx);
        } catch (err) {
          toast(err.message);
        }
      });
    });
  },
};
