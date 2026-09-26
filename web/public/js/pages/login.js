// Login / registration against the database API (bcrypt + JWT).
import { dbApi } from "../api.js";
import { getAuth, setAuth } from "../auth.js";
import { icon } from "../icons.js";
import { esc, toast } from "../ui.js";

export default {
  title: "Đăng nhập",
  subtitle: "Tài khoản dùng để lưu lịch sử dự đoán, train lại mô hình và xuất Excel",
  icon: "user-round",

  render(view) {
    const auth = getAuth();
    let mode = "login";
    const draw = () => {
      view.innerHTML = `
        <div class="auth-wrap">
          <section class="card">
            <div class="segmented" style="width:100%;margin-bottom:18px">
              <button type="button" data-mode="login" class="${mode === "login" ? "active" : ""}" style="flex:1">Đăng nhập</button>
              <button type="button" data-mode="register" class="${mode === "register" ? "active" : ""}" style="flex:1">Đăng ký</button>
            </div>
            ${auth ? `<div class="notice info" style="margin-bottom:14px">${icon("circle-check", 18)}Đang đăng nhập bằng <b>${esc(auth.user.username)}</b>.</div>` : ""}
            <form id="authForm" class="stack" style="gap:14px" novalidate>
              <label class="field">Tên đăng nhập
                <input class="input" name="username" autocomplete="username" required minlength="3" maxlength="32" pattern="[A-Za-z0-9_.\\-]+"></label>
              <label class="field">Mật khẩu
                <input class="input" name="password" type="password" autocomplete="${mode === "login" ? "current-password" : "new-password"}" required minlength="6" maxlength="72"></label>
              ${mode === "register" ? `<label class="field">Nhập lại mật khẩu
                <input class="input" name="confirm" type="password" autocomplete="new-password" required></label>` : ""}
              <div id="msg"></div>
              <button class="btn" type="submit">${icon(mode === "login" ? "log-in" : "user-round", 16)}${mode === "login" ? "Đăng nhập" : "Tạo tài khoản"}</button>
            </form>
            <p class="caption" style="margin-top:14px">
              ${mode === "login"
                ? "Tài khoản dùng thử do script seed tạo: <b>demo</b> / <b>demo123</b>."
                : "Tên đăng nhập 3–32 ký tự (chữ, số, . _ -), mật khẩu tối thiểu 6 ký tự. Mật khẩu được băm bằng bcrypt trước khi lưu."}
            </p>
          </section>
        </div>`;

      view.querySelectorAll("[data-mode]").forEach(b => b.addEventListener("click", () => { mode = b.dataset.mode; draw(); }));
      const form = view.querySelector("#authForm");
      form.addEventListener("submit", async e => {
        e.preventDefault();
        const msg = view.querySelector("#msg");
        const data = Object.fromEntries(new FormData(form));
        const fail = text => { msg.innerHTML = `<div class="notice error">${icon("circle-alert", 18)}${esc(text)}</div>`; };
        if (!/^[A-Za-z0-9_.-]{3,32}$/.test(data.username)) return fail("Tên đăng nhập 3–32 ký tự, chỉ gồm chữ, số và . _ -");
        if ((data.password || "").length < 6) return fail("Mật khẩu tối thiểu 6 ký tự");
        if (mode === "register" && data.password !== data.confirm) return fail("Hai lần nhập mật khẩu không khớp");

        const btn = form.querySelector("button[type=submit]");
        btn.disabled = true;
        try {
          const res = await dbApi(mode === "login" ? "/auth/login" : "/auth/register", {
            method: "POST", body: { username: data.username, password: data.password },
          });
          location.hash = "#/tong-quan";
          setAuth(res);
          toast(mode === "login" ? `Xin chào ${res.user.username}` : `Đã tạo tài khoản ${res.user.username}`);
        } catch (err) {
          fail(err.message);
          btn.disabled = false;
        }
      });
    };
    draw();
  },
};
