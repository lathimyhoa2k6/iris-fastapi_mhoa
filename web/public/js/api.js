// The web module only talks to the two APIs over HTTP; their addresses come from config.js.
import { clearAuth, token } from "./auth.js";

const CONFIG = window.APP_CONFIG || { modelApi: "", dbApi: "/db" };
export const MODEL_API = CONFIG.modelApi;
export const DB_API = CONFIG.dbApi;

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

function detailMessage(body, status) {
  const detail = body && body.detail;
  if (Array.isArray(detail)) {
    return detail.map(d => `${d.loc ? d.loc.slice(-1)[0] + ": " : ""}${d.msg}`).join("; ");
  }
  if (typeof detail === "string") return detail;
  return `Máy chủ trả mã lỗi HTTP ${status}`;
}

async function request(base, path, { method = "GET", body, auth = false, raw = false } = {}) {
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (auth) {
    const t = token();
    if (!t) throw new ApiError("Bạn cần đăng nhập để dùng chức năng này.", 401);
    headers.Authorization = `Bearer ${t}`;
  }
  let res;
  try {
    res = await fetch(base + path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
  } catch (_) {
    throw new ApiError(`Không kết nối được tới máy chủ ${base || location.origin}. Kiểm tra dịch vụ đã chạy chưa.`, 0);
  }
  if (!res.ok) {
    let data = null;
    try { data = await res.json(); } catch (_) { /* not JSON */ }
    if (res.status === 401 && auth) clearAuth();
    throw new ApiError(detailMessage(data, res.status), res.status);
  }
  return raw ? res : res.json();
}

export const modelApi = (path, opts) => request(MODEL_API, path, opts);
export const dbApi = (path, opts) => request(DB_API, path, opts);

/** Absolute URL of a file served by the model API (e.g. /static/images/setosa.jpg). */
export const modelAsset = path => (/^https?:/.test(path) ? path : MODEL_API + path);

export function query(params) {
  const q = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== "") q.set(k, v); });
  const s = q.toString();
  return s ? `?${s}` : "";
}

/** Download an authenticated file (Excel export) and save it under the server's file name. */
export async function downloadFromDb(path) {
  const res = await dbApi(path, { auth: true, raw: true });
  const disposition = res.headers.get("Content-Disposition") || "";
  const name = (disposition.match(/filename="([^"]+)"/) || [])[1] || "export.xlsx";
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  return name;
}
