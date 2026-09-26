// SVM species classifier: the original da1 page, reskinned. Same API calls and the
// same conveniences as before (health light, response time, copy buttons, remembered
// input, prefill links such as /?sl=6.5&sw=3.0&pl=5.5&pw=2.0&auto=1).
import { dbApi, MODEL_API, modelApi, modelAsset } from "../api.js";
import { getAuth } from "../auth.js";
import { icon } from "../icons.js";
import { esc, PALETTE, toast } from "../ui.js";

const FIELDS = ["sepal_length", "sepal_width", "petal_length", "petal_width"];
const SHORT = { sepal_length: "sl", sepal_width: "sw", petal_length: "pl", petal_width: "pw" };
const LABELS = { sepal_length: "Sepal length (cm)", sepal_width: "Sepal width (cm)", petal_length: "Petal length (cm)", petal_width: "Petal width (cm)" };
const COLORS = { setosa: PALETTE[0], versicolor: PALETTE[3], virginica: PALETTE[4] };
const DEFAULTS = ["5.1", "3.5", "1.4", "0.2"];
const STORE_KEY = "iris-last-input";
const SAMPLES = { setosa: "5.1,3.5,1.4,0.2", versicolor: "6.0,2.7,4.2,1.3", virginica: "6.5,3.0,5.5,2.0" };

export default {
  title: "Phân loại loài hoa bằng SVM",
  subtitle: "Nhập bốn kích thước của bông hoa, API dự đoán loài và trả về hình minh hoạ",
  icon: "scan-eye",

  render(view, ctx) {
    view.innerHTML = `
      <div class="grid cols-2" style="align-items:start">
        <section class="card">
          <div class="card-head"><h2>Bốn kích thước</h2>
            <p class="status-line"><span class="dot-status" id="dot"></span><span id="status">Đang kiểm tra dịch vụ…</span></p></div>
          <form id="form">
            <div class="form-grid">
              ${FIELDS.map((f, i) => `<label class="field">${LABELS[f]}
                <input class="input" id="${f}" type="number" step="0.1" min="0.1" max="30" value="${DEFAULTS[i]}" required></label>`).join("")}
            </div>
            <button class="btn" id="btn" type="submit" style="width:100%;margin-top:16px">${icon("scan-eye", 16)}Dự đoán loài hoa</button>
          </form>
          <div class="btn-row" style="margin-top:14px">
            <span class="sub">Mẫu thử nhanh:</span>
            ${Object.entries(SAMPLES).map(([k, v]) => `<button class="chip" type="button" data-v="${v}">${k}</button>`).join("")}
            <button class="chip" type="button" id="reset">Đặt lại</button>
          </div>
          <p class="caption" id="modelInfo" style="margin-top:16px">Mô hình: SVM (scikit-learn) · API: FastAPI</p>
          <p class="caption"><a href="${MODEL_API}/docs" target="_blank" rel="noopener">Tài liệu API (Swagger)</a> ·
            <a href="${MODEL_API}/metrics" target="_blank" rel="noopener">Số liệu mô hình</a></p>
        </section>
        <section id="result" aria-live="polite">
          <div class="card"><div class="state">${icon("flower-2", 34)}<b>Chưa có kết quả</b><p>Nhập số đo rồi bấm “Dự đoán loài hoa”, hoặc chọn một mẫu thử nhanh.</p></div></div>
        </section>
      </div>`;

    const form = view.querySelector("#form");
    const btn = view.querySelector("#btn");
    const box = view.querySelector("#result");
    const read = () => Object.fromEntries(FIELDS.map(f => [f, parseFloat(view.querySelector(`#${f}`).value)]));
    const write = values => FIELDS.forEach((f, i) => { view.querySelector(`#${f}`).value = values[i]; });

    // Prefill from the URL, e.g. /?sl=6.5&sw=3.0&pl=5.5&pw=2.0&auto=1 — used for demo links
    // and for screenshots that need a result already on screen.
    function applyQueryParams() {
      const q = new URLSearchParams(location.search);
      let filled = false;
      for (const field of FIELDS) {
        const value = q.get(SHORT[field]) ?? q.get(field);
        if (value !== null && value !== "" && !Number.isNaN(parseFloat(value))) {
          view.querySelector(`#${field}`).value = value;
          filled = true;
        }
      }
      return filled && q.get("auto") === "1";
    }

    // Fall back to whatever was typed last time, so a reload does not lose the input.
    function restoreLastInput() {
      try {
        const saved = JSON.parse(localStorage.getItem(STORE_KEY) || "null");
        if (Array.isArray(saved) && saved.length === FIELDS.length) write(saved);
      } catch (_) { /* private mode or blocked storage: keep the defaults */ }
    }

    function rememberInput() {
      try { localStorage.setItem(STORE_KEY, JSON.stringify(FIELDS.map(f => view.querySelector(`#${f}`).value))); }
      catch (_) { /* storage unavailable, nothing to do */ }
    }

    // Probe /health on load: on Render's free plan the first request may need ~30-60s.
    async function checkHealth() {
      const dot = view.querySelector("#dot");
      const text = view.querySelector("#status");
      try {
        const body = await modelApi("/health");
        if (!ctx.alive()) return;
        const ok = body.status === "healthy";
        dot.className = "dot-status " + (ok ? "ok" : "bad");
        text.textContent = ok ? "Dịch vụ sẵn sàng · mô hình đã nạp" : "Dịch vụ chạy nhưng chưa nạp được mô hình";
      } catch (_) {
        if (!ctx.alive()) return;
        dot.className = "dot-status bad";
        text.textContent = "Không kết nối được tới dịch vụ";
      }
    }

    // Show the accuracy of the running model so the demo can quote it.
    async function showModelInfo() {
      try {
        const m = await modelApi("/metrics");
        if (!ctx.alive()) return;
        view.querySelector("#modelInfo").textContent =
          `SVM kernel=${m.model.best_params.kernel} · accuracy ${(m.performance.accuracy_test * 100).toFixed(2)}% · FastAPI`;
      } catch (_) { /* metrics.json missing: keep the static label */ }
    }

    function showError(message) {
      box.innerHTML = `<div class="result-card error"><strong>Không dự đoán được.</strong><p>${esc(message)}</p></div>`;
    }

    function showResult(data, ms, payload) {
      const rows = Object.entries(data.probabilities).sort((a, b) => b[1] - a[1]).map(([name, p]) => `
        <div class="prob-row"><span>${name}</span>
          <span class="track"><span class="fill" style="display:block;width:${(p * 100).toFixed(1)}%;background:${COLORS[name] || PALETTE[0]}"></span></span>
          <span style="text-align:right">${(p * 100).toFixed(1)}%</span></div>`).join("");
      const author = data.source.replace(/^Wikimedia Commons\s*[-—]\s*/, "");
      box.innerHTML = `
        <div class="card">
          <div class="result-card">
            <h3>${esc(data.display_name)}</h3>
            <p class="sub">${esc(data.vietnamese_name)} · lớp ${data.class_id} ·
              <span class="badge best">${(data.confidence * 100).toFixed(1)}%</span> · ${ms} ms</p>
            <p style="margin:10px 0 0">${esc(data.description)}</p>
            <img class="photo" src="${esc(modelAsset(data.image_url))}" alt="${esc(data.alt_text)}">
            <p class="caption">Nguồn: ${esc(author)}, ${esc(data.license)}${data.source_url
              ? `, <a href="${esc(data.source_url)}" target="_blank" rel="noopener">${esc(data.source_url.replace("https://", ""))}</a>` : ""}</p>
            <div class="stack" style="gap:8px;margin-top:12px">${rows}</div>
          </div>
          <div class="btn-row" style="margin-top:14px">
            <button class="btn ghost small" type="button" data-copy="link">${icon("link", 14)}Sao chép liên kết mẫu này</button>
            <button class="btn ghost small" type="button" data-copy="curl">${icon("terminal", 14)}Sao chép lệnh curl</button>
            <button class="btn ghost small" type="button" data-copy="json">${icon("braces", 14)}Sao chép JSON kết quả</button>
            <button class="btn small" type="button" id="saveSvm">${icon("save", 14)}Lưu vào lịch sử</button>
          </div>
        </div>`;

      const apiOrigin = MODEL_API || location.origin;
      const link = `${location.origin}${location.pathname}?` + FIELDS.map(f => `${SHORT[f]}=${payload[f]}`).join("&") + "&auto=1";
      const curl = `curl -X POST "${apiOrigin}/predict" \\\n  -H "Content-Type: application/json" \\\n  -d '${JSON.stringify(payload)}'`;
      const texts = { link, curl, json: JSON.stringify(data, null, 2) };
      box.querySelectorAll("[data-copy]").forEach(tool => {
        tool.addEventListener("click", async () => {
          const label = tool.innerHTML;
          try {
            await navigator.clipboard.writeText(texts[tool.dataset.copy]);
            tool.textContent = "Đã sao chép";
          } catch (_) {
            tool.textContent = "Không sao chép được";
          }
          setTimeout(() => { tool.innerHTML = label; }, 1400);
        });
      });
      box.querySelector("#saveSvm").addEventListener("click", async e => {
        if (!getAuth()) { toast("Hãy đăng nhập để lưu lịch sử"); location.hash = "#/dang-nhap"; return; }
        e.currentTarget.disabled = true;
        try {
          await dbApi("/predictions", {
            method: "POST", auth: true,
            body: { items: [{ task: "classification", model: "svm", input: payload, predicted_label: data.species_key, runtime_ms: ms }] },
          });
          toast("Đã lưu dự đoán SVM vào lịch sử");
        } catch (err) {
          toast(err.message);
          e.currentTarget.disabled = false;
        }
      });
    }

    view.querySelectorAll(".chip[data-v]").forEach(chip => {
      chip.addEventListener("click", () => { write(chip.dataset.v.split(",")); form.requestSubmit(); });
    });
    view.querySelector("#reset").addEventListener("click", () => {
      write(DEFAULTS);
      box.innerHTML = `<div class="card"><div class="state">${icon("flower-2", 34)}<b>Chưa có kết quả</b><p>Nhập số đo rồi bấm “Dự đoán loài hoa”.</p></div></div>`;
    });

    form.addEventListener("submit", async event => {
      event.preventDefault();
      const payload = read();
      rememberInput();
      btn.disabled = true;
      btn.textContent = "Đang dự đoán…";
      const started = performance.now();
      try {
        const data = await modelApi("/predict", { method: "POST", body: payload });
        if (!ctx.alive()) return;
        showResult(data, Math.round(performance.now() - started), payload);
      } catch (err) {
        if (ctx.alive()) showError(err.message);
      } finally {
        btn.disabled = false;
        btn.innerHTML = `${icon("scan-eye", 16)}Dự đoán loài hoa`;
      }
    });

    const autoSubmit = applyQueryParams();
    if (!autoSubmit && !location.search) restoreLastInput();
    checkHealth();
    showModelInfo();
    if (autoSubmit) form.requestSubmit();
  },
};
