"""Display information for the three Iris species, shared by the API and the web page.

The user-facing text stays in Vietnamese because the report and the web page are.
"""

SPECIES = [
    {
        "class_id": 0,
        "species_key": "setosa",
        "display_name": "Iris setosa",
        "vietnamese_name": "Diên vĩ setosa",
        "description": (
            "Cánh hoa nhỏ, ngắn và hẹp (dài 1.0–1.9 cm). Đây là loài duy nhất tách biệt "
            "tuyến tính hoàn toàn khỏi hai loài còn lại, nên mô hình gần như không bao giờ nhầm."
        ),
        "image_url": "/static/images/setosa.jpg",
        "alt_text": "Hình minh hoạ hoa Iris setosa",
        # Author name romanised so the report appendix renders under pdfLaTeX;
        # IMAGE_CREDITS.md keeps the Cyrillic original alongside this spelling.
        "source": "Wikimedia Commons - Denis Anisimov",
        "license": "Public domain",
        "source_url": "https://commons.wikimedia.org/wiki/File:Irissetosa1.jpg",
    },
    {
        "class_id": 1,
        "species_key": "versicolor",
        "display_name": "Iris versicolor",
        "vietnamese_name": "Diên vĩ versicolor",
        "description": (
            "Kích thước trung bình, cánh hoa dài 3.0–5.1 cm. Có vùng giao thoa nhỏ với "
            "Iris virginica — phần lớn lỗi phân loại của mô hình nằm ở ranh giới này."
        ),
        "image_url": "/static/images/versicolor.jpg",
        "alt_text": "Hình minh hoạ hoa Iris versicolor",
        "source": "Wikimedia Commons — D. Gordon E. Robertson",
        "license": "CC BY-SA 3.0",
        "source_url": "https://commons.wikimedia.org/wiki/File:Blue_Flag,_Ottawa.jpg",
    },
    {
        "class_id": 2,
        "species_key": "virginica",
        "display_name": "Iris virginica",
        "vietnamese_name": "Diên vĩ virginica",
        "description": (
            "Loài lớn nhất, cánh hoa dài 4.5–6.9 cm và đài hoa rộng. Thường bị nhầm với "
            "Iris versicolor khi kích thước cánh hoa nằm ở vùng chuyển tiếp."
        ),
        "image_url": "/static/images/virginica.jpg",
        "alt_text": "Hình minh hoạ hoa Iris virginica",
        "source": "Wikimedia Commons — Frank Mayfield",
        "license": "CC BY-SA 2.0",
        "source_url": "https://commons.wikimedia.org/wiki/File:Iris_virginica.jpg",
    },
]

BY_ID = {item["class_id"]: item for item in SPECIES}

CREDITS_FILE = "static/images/IMAGE_CREDITS.md"


def get(class_id: int) -> dict:
    """Return the display information of one class, image credit and licence included."""
    return dict(BY_ID[class_id])
