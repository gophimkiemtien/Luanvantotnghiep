import matplotlib.pyplot as plt

# 1. Dữ liệu từ bảng kết quả của bạn
metrics = [
    'Faithfulness\n(Độ trung thực)', 
    'Answer Relevancy\n(Độ liên quan)', 
    'Context Precision\n(Độ chính xác)', 
    'Context Recall\n(Độ phủ)'
]
scores = [0.9200, 0.9450, 0.8600, 0.7950]

# 2. Cài đặt font chữ (tránh lỗi tiếng Việt)
plt.rcParams['font.family'] = 'sans-serif'

# 3. Tạo khung biểu đồ
fig, ax = plt.subplots(figsize=(10, 6))

# Vẽ các cột với màu sắc khác nhau để dễ phân biệt
colors = ['#2878B5', '#9AC9DB', '#F8AC8C', '#C82423']
bars = ax.bar(metrics, scores, color=colors, width=0.6, edgecolor='black', linewidth=0.5)

# 4. Tùy chỉnh trục và tiêu đề
ax.set_ylim(0, 1.1) # Trục Y giới hạn từ 0 đến 1 (nới lên 1.1 để có chỗ viết số)
ax.set_ylabel('Điểm trung bình (0 - 1)', fontsize=12, fontweight='bold', labelpad=10)
ax.set_title('BIỂU ĐỒ ĐÁNH GIÁ CHẤT LƯỢNG RAG CHATBOT BẰNG RAGAS', 
             fontsize=14, fontweight='bold', pad=20)

# Kẻ lưới ngang để dễ đối chiếu điểm số
ax.yaxis.grid(True, linestyle='--', alpha=0.7)
ax.set_axisbelow(True) # Đưa lưới xuống dưới các cột

# 5. Viết trực tiếp con số lên đỉnh của từng cột
for bar in bars:
    height = bar.get_height()
    ax.annotate(f'{height:.4f}',
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 5),  # Dịch lên trên 5 pixel
                textcoords="offset points",
                ha='center', va='bottom', 
                fontsize=12, fontweight='bold', color='black')

# Căn chỉnh lề tự động cho đẹp
plt.tight_layout()

# 6. Lưu thành file ảnh chất lượng cao để chèn vào Word
plt.savefig('ragas_evaluation_chart.png', dpi=300, bbox_inches='tight')
print("Đã lưu biểu đồ thành file: ragas_evaluation_chart.png")

# Hiển thị lên màn hình
plt.show()