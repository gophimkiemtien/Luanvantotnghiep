import os
import pandas as pd
import time
from tqdm import tqdm
from google import genai
from google.genai import types
import itertools

# Import toàn bộ module main để có thể ghi đè ai_client
import main
from main import (
    parse_query_with_llm, 
    hybrid_search_with_rerank
)

# ================= CẤU HÌNH API KEYS =================
# Điền danh sách các key của bạn vào đây
API_KEYS = [
    "AIzaSyCkFTBO3IBe7lsz6cue2PPLXR72lwyjWMU"
]

# Tạo một iterator để xoay vòng các key vô tận (key1 -> key2 -> key3 -> key1...)
key_cycle = itertools.cycle(API_KEYS)

def get_next_client():
    """Hàm lấy key tiếp theo và cập nhật cho toàn bộ hệ thống"""
    next_key = next(key_cycle)
    new_client = genai.Client(api_key=next_key)
    
    # Quan trọng: Ghi đè ai_client trong file main.py 
    # Để hàm parse_query_with_llm cũng dùng key luân phiên này
    main.ai_client = new_client 
    
    return new_client

# ================= HÀM CHẠY CHÍNH =================
def generate_ragas_dataset(input_csv="ragas_ground_truth_auto_2.csv", output_csv="ragas_ready_data.csv"):
    print(f"Đọc dữ liệu gốc từ {input_csv}...")
    df_input = pd.read_csv(input_csv)
    
    processed_count = 0
    
    # --- KIỂM TRA LỊCH SỬ CHẠY ĐỂ RESUME ---
    if os.path.exists(output_csv):
        # Đọc file kết quả hiện tại để xem đã làm được bao nhiêu câu
        df_existing = pd.read_csv(output_csv)
        processed_count = len(df_existing)
        print(f"Phát hiện file {output_csv} đã có {processed_count} dòng.")
        if processed_count >= len(df_input):
            print("Toàn bộ dữ liệu đã được xử lý xong từ trước!")
            return
        print(f"Sẽ chạy TÍÊP TỤC từ dòng số {processed_count}...")
    else:
        print(f"Chưa có file kết quả, tạo mới {output_csv}...")
        # Tạo file mới với header
        empty_df = pd.DataFrame(columns=["question", "contexts", "answer", "ground_truth"])
        empty_df.to_csv(output_csv, index=False, encoding='utf-8-sig')

    print("Đang chạy RAG pipeline thực tế...")
    
    # Bắt đầu vòng lặp
    for index, row in tqdm(df_input.iterrows(), total=len(df_input)):
        # Bỏ qua các dòng đã được xử lý ở lần chạy trước
        if index < processed_count:
            continue
            
        question = row['question']
        ground_truth = row['ground_truth']
        
        # Đổi API Key cho câu này
        current_ai_client = get_next_client()
        
        # --- BƯỚC 1: TRUY XUẤT ---
        try:
            parsed = parse_query_with_llm(question)
            hits = hybrid_search_with_rerank(
                parsed.rewritten_query, 
                top_k=20, 
                final_n=4, 
                threshold=0.6
            )
            contexts_list = [h.payload.get('content', '') for h in hits]
            context_str = "\n---\n".join(contexts_list)
        except Exception as e:
            print(f"\nLỗi truy xuất/parse ở câu {index}: {e}")
            contexts_list = []
            context_str = ""
        
        # --- BƯỚC 2: SINH CÂU TRẢ LỜI ---
        prompt = f"""Bạn là CTU Scholar, một trợ lý học thuật chuyên nghiệp. Hãy trả lời câu hỏi dựa trên Ngữ cảnh được cung cấp.

Ngữ cảnh:
{context_str}

Câu hỏi: {question}

Yêu cầu định dạng trình bày (BẮT BUỘC):
1. Tính chính xác: Chỉ trả lời dựa trên ngữ cảnh, tuyệt đối không bịa đặt.
2. Dạng bảng biểu: Nếu câu hỏi yêu cầu "So sánh", "Phân biệt":
   - Bắt buộc trình bày dưới dạng BẢNG (Markdown Table).
   - Tiêu đề cột phải được **in đậm**.
   - Không được xuống dòng bên trong một ô.
   - Sau bảng, bắt buộc có một đoạn **Tổng kết** tóm tắt điểm giống/khác.
3. Dạng liệt kê: Bắt buộc dùng gạch đầu dòng (-) hoặc số (1, 2...). In đậm từ khóa ở đầu mỗi ý.
4. Quản lý khoảng trắng: Để MỘT DÒNG TRỐNG giữa các đoạn văn.
5. Viết tên tác giả: Viết hoa chữ cái đầu mỗi từ.

Trả lời:"""

        try:
            response = current_ai_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.0)
            )
            answer = response.text
        except Exception as e:
            print(f"\nLỗi khi gọi Gemini cho câu {index}: {e}")
            answer = "LỖI_GENERATE"
            
        # --- BƯỚC 3: LƯU TRỰC TIẾP VÀO FILE ---
        # Chỉ tạo DataFrame 1 dòng và append (mode='a') vào file CSV
        new_row = pd.DataFrame([{
            "question": question,
            "contexts": contexts_list, 
            "answer": answer,
            "ground_truth": ground_truth
        }])
        
        new_row.to_csv(output_csv, mode='a', header=False, index=False, encoding='utf-8-sig')
        
        # Nghỉ 1.5 giây để dàn đều request, tránh bị Google chặn do gọi quá nhanh
        time.sleep(1.5)

    print("\nHoàn tất! Dữ liệu đã được chuẩn bị đầy đủ.")

if __name__ == "__main__":
    generate_ragas_dataset()