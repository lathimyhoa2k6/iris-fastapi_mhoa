import pyodbc


def get_connection():
    return pyodbc.connect(
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=LAPTOP-NHDL7CM3;"
        "DATABASE=IrisDB;"
        "Trusted_Connection=yes;"
    )


if __name__ == "__main__":
    conn = get_connection()
    print("Kết nối SQL Server thành công!")
    conn.close()