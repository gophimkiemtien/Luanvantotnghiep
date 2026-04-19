from pymongo import MongoClient

# Kết nối DB
client = MongoClient("mongodb://localhost:27017/")
db = client["ctu"]
users_col = db["users"]

# Xóa dữ liệu cũ (nếu có) để làm mới
users_col.delete_many({})

# Danh sách người dùng mẫu
sample_users = [
    {
        "username": "b2203449",  # MSSV của bạn
        "password": "123",       # Trong thực tế nên mã hóa (hash), nhưng làm đồ án thì để text tạm cho dễ test
        "full_name": "Lê Hoàng Gia Khánh",
        "role": "Sinh viên"
    },
    {
        "username": "admin",
        "password": "123",
        "full_name": "Quản trị viên Hệ thống",
        "role": "Admin"
    },
    {
        "username": "cb001",
        "password": "123",
        "full_name": "TS. Nguyễn Văn A",
        "role": "Giảng viên"
    }
]

users_col.insert_many(sample_users)
print("✅ Đã tạo thành công 3 tài khoản mẫu vào MongoDB!")