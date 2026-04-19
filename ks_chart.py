import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# 1. Đọc dữ liệu từ file Excel
file_path = r"D:\LV_OFFICIAL\ketquaks.xlsx"
df = pd.read_excel(file_path)
likert_cols = df.columns[4:]

# 2. Định nghĩa tên các nhóm ngắn gọn để hiển thị đẹp trên trục X
groups = {
    'A': 'A. Tìm kiếm',
    'B': 'B. Chi tiết LV',
    'C': 'C. Trợ lý\nDocument',
    'D': 'D. Trợ lý\nGlobal',
    'E': 'E. Xu hướng',
    'F': 'F. Tính mới',
    'G': 'G. Giao diện',
    'H': 'H. Giá trị chung'
}

likert_mapping = [
    '1 - Rất không đồng ý',
    '2 - Không đồng ý',
    '3- Bình thường',
    '4 - Đồng ý',
    '5 - Rất đồng ý'
]

# 3. Gom dữ liệu: Tính số người trung bình chọn mỗi mức độ cho từng nhóm
plot_data = pd.DataFrame(index=groups.values(), columns=likert_mapping).fillna(0.0)

for key, name in groups.items():
    # Lấy các cột thuộc nhóm hiện tại (Bắt đầu bằng "A.", "B.",...)
    cols = [c for c in likert_cols if c.startswith(key + '.')]
    if len(cols) == 0:
        continue
        
    for col in cols:
        counts = df[col].value_counts()
        for k in likert_mapping:
            if k in counts:
                plot_data.loc[name, k] += counts[k]
                
    # Tính trung bình số người chọn mỗi mức trên 1 câu hỏi
    plot_data.loc[name] = plot_data.loc[name] / len(cols)

# 4. Vẽ biểu đồ cột ghép (Grouped Bar Chart)
fig, ax = plt.subplots(figsize=(16, 8))

# Cài đặt màu sắc từ Đỏ (Không đồng ý) đến Xanh (Rất đồng ý)
colors = ['#d7191c', '#fdae61', '#ffffbf', '#a6d96a', '#1a9641']

# Vẽ biểu đồ (để các cột đứng cạnh nhau)
plot_data.plot(kind='bar', color=colors, ax=ax, edgecolor='black', width=0.85)

# Thiết lập tiêu đề và nhãn
ax.set_title('Mức độ đánh giá theo từng phân hệ chức năng', 
             fontsize=18, fontweight='bold', pad=20)
ax.set_xlabel('Phân hệ chức năng (Nhóm câu hỏi)', fontsize=14, fontweight='bold', labelpad=15)
ax.set_ylabel('Số lượng người dùng (Trung bình)', fontsize=14, fontweight='bold')

# Điều chỉnh trục X để chữ nằm ngang, dễ đọc
plt.xticks(rotation=0, fontsize=11)

# Đưa bảng chú thích (Legend) ra bên ngoài
ax.legend(title='Mức độ đánh giá', bbox_to_anchor=(1.02, 1), loc='upper left', fontsize=12)

# Hiển thị số lượng trên đỉnh mỗi cột (làm tròn 1 chữ số thập phân)
for c in ax.containers:
    # Ẩn các cột có giá trị 0 để biểu đồ không bị rối
    labels = [f'{w:.1f}' if w > 0 else '' for w in c.datavalues]
    ax.bar_label(c, labels=labels, padding=3, fontsize=9, color='black')

# Thêm đường kẻ ngang mờ để dễ dóng số liệu
ax.grid(axis='y', linestyle='--', alpha=0.5)

plt.tight_layout()

# Lưu và hiển thị
plt.savefig(r'D:\LV_OFFICIAL\grouped_bar_chart.png', dpi=300, bbox_inches='tight')
plt.show()