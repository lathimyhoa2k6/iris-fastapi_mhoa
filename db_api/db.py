"""SQL Server access for the database API."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

import pyodbc

import settings


# Múi giờ Việt Nam: UTC+7
VIETNAM_TZ = timezone(timedelta(hours=7))

# Giữ lại biến này vì export.py và các phần khác của ứng dụng đang sử dụng.
UTC_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def utc_now() -> str:
    """
    Lấy thời gian hiện tại theo giờ Việt Nam.
    Giữ tên hàm utc_now để không phải sửa history.py.
    """
    return datetime.now(VIETNAM_TZ).strftime(
        "%Y-%m-%dT%H:%M:%S"
    )


def local_tz() -> timezone:
    """Múi giờ địa phương của ứng dụng, mặc định là Việt Nam UTC+7."""
    return timezone(
        timedelta(
            hours=float(
                settings.get(
                    "APP_TZ_OFFSET_HOURS",
                    "7",
                )
            )
        )
    )


def date_bounds(
    date_from: date | None,
    date_to: date | None,
) -> tuple[str | None, str | None]:
    """
    Chuyển ngày theo giờ Việt Nam thành khoảng UTC
    để truy vấn SQL Server chính xác.
    """

    def utc(d: date) -> str:
        return (
            datetime.combine(
                d,
                time.min,
                local_tz(),
            )
            .astimezone(timezone.utc)
            .strftime(UTC_FORMAT)
        )

    return (
        utc(date_from) if date_from else None,
        utc(date_to + timedelta(days=1))
        if date_to
        else None,
    )


def connect():
    """Mở kết nối đến SQL Server."""

    return pyodbc.connect(
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=LAPTOP-NHDL7CM3;"
        "DATABASE=IrisDB;"
        "Trusted_Connection=yes;"
    )


def get_conn():
    """FastAPI dependency: mỗi request dùng một kết nối SQL Server."""

    conn = connect()

    try:
        yield conn
    finally:
        conn.close()