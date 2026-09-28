# Nguồn tài nguyên (CREDITS)

Mọi tài nguyên bên dưới đã được **tải về và phục vụ từ chính dự án** — trang web không hotlink
và không gọi CDN nào lúc chạy. Giấy phép tra ngày 15/09/2026 (ảnh) và 24/09/2026 (phần còn lại).

## Ảnh

Ba ảnh trong `static/images/`, lấy từ Wikimedia Commons. Dưới mỗi ảnh lớn trên giao diện có chú thích
dạng *"Nguồn: tác giả, giấy phép, liên kết"* (trường `source`, `license`, `source_url` của API `/species`
và `/predict`). Ảnh thu nhỏ ở thanh bên dùng lại đúng ba ảnh này, có ghi nguồn ở thuộc tính `title`
và dòng chú thích bên dưới nhóm "Các loài hoa".

| Tệp | Loài | Tác giả | Giấy phép | Trang gốc |
|-----|------|---------|-----------|-----------|
| `static/images/setosa.jpg` | *Iris setosa* | Денис Анисимов (Denis Anisimov) | Public domain | https://commons.wikimedia.org/wiki/File:Irissetosa1.jpg |
| `static/images/versicolor.jpg` | *Iris versicolor* | D. Gordon E. Robertson | CC BY-SA 3.0 | https://commons.wikimedia.org/wiki/File:Blue_Flag,_Ottawa.jpg |
| `static/images/virginica.jpg` | *Iris virginica* | Frank Mayfield | CC BY-SA 2.0 | https://commons.wikimedia.org/wiki/File:Iris_virginica.jpg |

Chi tiết thêm: `static/images/IMAGE_CREDITS.md`.

Hình line-art hoa ở chân thanh bên là SVG **tự vẽ** trong `web/public/js/app.js`, không lấy từ nguồn ngoài.

## Icon

- **Lucide** v1.47.0 — https://lucide.dev — giấy phép **ISC** (`web/public/vendor/LUCIDE_LICENSE.txt`).
  Các icon được nhúng thẳng dạng SVG trong `web/public/js/icons.js` (sinh từ gói `lucide-static`).

## Font

- **Be Vietnam Pro** (400, 500, 600, 700; subset latin, latin-ext, vietnamese) — The Be Vietnam Pro Project Authors,
  https://github.com/bettergui/BeVietnamPro — giấy phép **SIL Open Font License 1.1** (`web/public/fonts/OFL.txt`).
  Tệp `.woff2` lấy từ gói Fontsource `@fontsource/be-vietnam-pro`.

## Thư viện giao diện

- **Chart.js** v4.5.1 — https://www.chartjs.org — giấy phép **MIT** (ghi ở đầu tệp `web/public/vendor/chart.umd.min.js`).

## Dữ liệu

- **Iris dataset** — R. A. Fisher (1936), *The use of multiple measurements in taxonomic problems*.
  Kho UCI Machine Learning Repository: https://archive.ics.uci.edu/dataset/53/iris — giấy phép **CC BY 4.0**.
- Bản dùng trong dự án: Kaggle `uciml/iris` (https://www.kaggle.com/datasets/uciml/iris), tệp `data/Iris.csv`,
  tải bằng `kagglehub`; bản dự phòng `sklearn.datasets.load_iris()` (scikit-learn, BSD-3-Clause).
  Hai bản lệch nhau đúng 2 dòng (35 và 38) — xem `metrics.json → data.source_comparison`.
