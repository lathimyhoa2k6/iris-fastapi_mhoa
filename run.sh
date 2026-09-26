#!/usr/bin/env bash
# One-shot bootstrap: create the virtualenv, install dependencies, seed, start the modules.
#
#   bash run.sh          three modules on three ports: model API :8000, database API :8001, web :8080
#   bash run.sh single   the same three modules in one process on :8000 (what Render runs)
#   bash run.sh seed     first training of the regression models + demo account (demo / demo123)
#   bash run.sh train    install dev dependencies, retrain the SVM and regression models, redraw figures
#   bash run.sh test     install dev dependencies and run the pytest suite
#
# Works in Git Bash / WSL on Windows and in any POSIX shell on Linux or macOS.

set -euo pipefail
cd "$(dirname "$0")"

MODE="${1:-serve}"
VENV=".venv"

say() { printf '\n\033[36m==> %s\033[0m\n' "$1"; }
die() { printf '\n\033[31mLỖI: %s\033[0m\n' "$1" >&2; exit 1; }

# --- 1. Locate a Python interpreter -------------------------------------------
# On Windows the `py` launcher is the reliable one; a bare `python` may be the
# Microsoft Store stub that exits without doing anything.
PY=""
for candidate in "py -3" python3 python; do
  if $candidate -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >/dev/null 2>&1; then
    PY="$candidate"
    break
  fi
done
[ -n "$PY" ] || die "Không tìm thấy Python 3.10+. Cài tại https://www.python.org/downloads/ và nhớ tích 'Add python.exe to PATH'."

# --- 2. Create the virtualenv on first run ------------------------------------
if [ ! -d "$VENV" ]; then
  say "Tạo môi trường ảo .venv (chỉ lần đầu)"
  $PY -m venv "$VENV"
fi

# Windows venvs put the interpreter in Scripts/, POSIX ones in bin/.
if [ -x "$VENV/Scripts/python.exe" ]; then
  VPY="$VENV/Scripts/python.exe"
elif [ -x "$VENV/bin/python" ]; then
  VPY="$VENV/bin/python"
else
  die "Môi trường ảo hỏng. Xoá thư mục .venv rồi chạy lại lệnh này."
fi

# --- 3. Configuration: .env with a generated JWT secret -------------------------
if [ ! -f .env ]; then
  say "Tạo .env từ .env.example (sinh JWT_SECRET ngẫu nhiên)"
  SECRET="$("$VPY" -c 'import secrets; print(secrets.token_urlsafe(48))')"
  sed "s|^JWT_SECRET=.*|JWT_SECRET=$SECRET|" .env.example > .env
fi
set -a
# shellcheck disable=SC1091
. ./.env
set +a

# --- 4. Install dependencies ---------------------------------------------------
"$VPY" -m pip install --quiet --upgrade pip
case "$MODE" in
  train|test)
    say "Cài thư viện huấn luyện và kiểm thử (requirements-dev.txt)"
    "$VPY" -m pip install --quiet -r requirements-dev.txt ;;
  *)
    say "Cài thư viện cho 3 module (requirements.txt)"
    "$VPY" -m pip install --quiet -r requirements.txt ;;
esac

case "$MODE" in
  train)
    say "Huấn luyện lại SVM phân loại"
    "$VPY" train.py
    say "Huấn luyện lại 5 mô hình hồi quy"
    "$VPY" train_regression.py
    say "Vẽ lại hình cho báo cáo"
    "$VPY" figures.py
    "$VPY" figures_regression.py
    say "Xong. Chạy 'bash run.sh' để khởi động dịch vụ."
    exit 0 ;;
  test)
    say "Chạy bộ kiểm thử pytest"
    exec "$VPY" -m pytest ;;
  seed)
    "$VPY" seed.py
    exit 0 ;;
  serve|single) ;;
  *) die "Chế độ không hợp lệ: $MODE (serve | single | seed | train | test)" ;;
esac

[ -f svm_model.pkl ] || die "Thiếu svm_model.pkl. Chạy 'bash run.sh train' để huấn luyện lại."

say "Seed: train lần đầu (nếu chưa có mô hình) + tài khoản demo"
"$VPY" seed.py

# Open the browser (first URL) once every given URL's port is accepting connections.
open_browser() {
  ("$VPY" - "$@" <<'PYEOF' &
import socket, sys, time, urllib.parse, webbrowser
urls = sys.argv[1:]
pending = {(urllib.parse.urlparse(u).hostname, urllib.parse.urlparse(u).port) for u in urls}
for _ in range(120):
    for addr in list(pending):
        with socket.socket() as s:
            if s.connect_ex(addr) == 0:
                pending.discard(addr)
    if not pending:
        webbrowser.open(urls[0])
        break
    time.sleep(0.5)
PYEOF
  ) >/dev/null 2>&1
}

# --- 5. Serve ------------------------------------------------------------------
if [ "$MODE" = "single" ]; then
  PORT="${PORT:-$MODEL_API_PORT}"
  say "Chế độ gộp: cả 3 module trong một tiến trình tại http://127.0.0.1:$PORT  (Ctrl+C để dừng)"
  open_browser "http://127.0.0.1:$PORT/"
  SERVICE_MODE=single exec "$VPY" -m uvicorn app:app --host 127.0.0.1 --port "$PORT"
fi

export SERVICE_MODE=split
PIDS=()
start() {
  "$VPY" -m uvicorn "$1" --host 127.0.0.1 --port "$2" &
  PIDS+=("$!")
}
cleanup() {
  trap - INT TERM EXIT
  kill "${PIDS[@]}" 2>/dev/null || true
}
trap cleanup INT TERM EXIT

say "Khởi động 3 module  (Ctrl+C để dừng cả ba)"
printf '    API mô hình : http://127.0.0.1:%s/docs\n' "$MODEL_API_PORT"
printf '    API CSDL    : http://127.0.0.1:%s/docs\n' "$DB_API_PORT"
printf '    Giao diện   : http://127.0.0.1:%s/   (tài khoản demo / demo123)\n\n' "$WEB_PORT"

start app:app "$MODEL_API_PORT"
start db_api.main:app "$DB_API_PORT"
start web.server:app "$WEB_PORT"
open_browser "http://127.0.0.1:$WEB_PORT/" "http://127.0.0.1:$MODEL_API_PORT/" "http://127.0.0.1:$DB_API_PORT/"
wait
