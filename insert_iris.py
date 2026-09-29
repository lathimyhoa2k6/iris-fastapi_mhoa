import pandas as pd
import pyodbc

# Đọc dữ liệu Iris
df = pd.read_csv("data/Iris.csv")

# Kết nối SQL Server
conn = pyodbc.connect(
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=LAPTOP-NHDL7CM3;"
    "DATABASE=IrisDB;"
    "Trusted_Connection=yes;"
)

cursor = conn.cursor()

# Xóa dữ liệu cũ trong bảng iris_data
cursor.execute("DELETE FROM iris_data")

# Thêm dữ liệu Iris vào SQL Server
for _, row in df.iterrows():
    cursor.execute(
        """
        INSERT INTO iris_data
        (sepal_length, sepal_width, petal_length, petal_width, species)
        VALUES (?, ?, ?, ?, ?)
        """,
        row["SepalLengthCm"],
        row["SepalWidthCm"],
        row["PetalLengthCm"],
        row["PetalWidthCm"],
        row["Species"]
    )

conn.commit()

print("Đã đưa dữ liệu Iris vào SQL Server!")
print("Số dòng:", len(df))

cursor.close()
conn.close()