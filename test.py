import matplotlib.pyplot as plt

# Dữ liệu
modes = ['Fixed Normal', 'Adaptive', 'Fixed High']
power = [261.78, 273.21, 286.94]

# Màu sắc tương đồng với biểu đồ gốc
colors = ['#2e8b57', '#d88b17', '#c43c2e'] # Xanh lá, Cam, Đỏ

# Tạo biểu đồ
fig, ax = plt.subplots(figsize=(8, 5), dpi=150)
bars = ax.bar(modes, power, color=colors)

# Thêm nhãn dữ liệu trên từng cột
for bar in bars:
    yval = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2, yval + 2, f'{yval}', ha='center', va='bottom', fontsize=10)

# Thiết lập tiêu đề và nhãn trục (đã sửa lỗi tiếng Việt)
ax.set_title('So sánh công suất trung bình giữa ba chế độ vận hành', fontsize=14, fontweight='bold')
ax.set_ylabel('Công suất trung bình (mW)', fontsize=12)

# Thêm lưới kẻ ngang cho dễ nhìn
ax.yaxis.grid(True, linestyle='-', alpha=0.3)
ax.xaxis.grid(False)

# Điều chỉnh giới hạn trục tung để có khoảng trống cho nhãn dữ liệu
ax.set_ylim(0, 310)

# Hiển thị biểu đồ
plt.tight_layout()
plt.show()