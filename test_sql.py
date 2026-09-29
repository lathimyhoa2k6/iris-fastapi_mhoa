import pyodbc

conn = pyodbc.connect(
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=LAPTOP-NHDL7CM3;"
    "DATABASE=IrisDB;"
    "Trusted_Connection=yes;"
)

cursor = conn.cursor()

cursor.execute(
    "INSERT INTO users (username, password) VALUES (?, ?)",
    ("testhoa", "123456")
)

conn.commit()

print("Đã thêm tài khoản vào SQL Server!")

cursor.close()
conn.close()