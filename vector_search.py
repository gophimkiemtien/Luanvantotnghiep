import os
import pandas as pd
import time
from tqdm import tqdm
from google import genai
from google.genai import types
import itertools

# Import main để lấy các thành phần cần thiết (Lưu ý KHÔNG dùng hybrid_search_with_rerank nữa)
import main
from main import (
    parse_query_with_llm, 
    qdrant_client,         # Import trực tiếp qdrant_client
    embed_model,           # Import model nhúng dense
    sparse_model,          # Import model nhúng sparse
    COLLECTION_NAME        # Tên collection
)
from qdrant_client.http import models as rest # Import thư viện rest của qdrant

# ================= CẤU HÌNH API KEYS =================
API_KEYS = [
    "AIzaSyCkFTBO3IBe7lsz6cue2PPLXR72lwyjWMU"
]

key_cycle = itertools.cycle(API_KEYS)

def get_next_client():
    next_key = next(key_cycle)
    new_client = genai.Client(api_key=next_key)
    main.ai_client = new_client 
    return new_client

# --- HÀM TÌM KIẾM MỚI (CHỈ VECTOR SEARCH + BM25, KHÔNG RERANK) ---
def hybrid_search_without_rerank(query: str, top_k: int = 4):
    """
    Hàm này thực hiện tìm kiếm lai (Dense + Sparse) bằng Qdrant 
    nhưng KHÔNG chấm điểm lại bằng Cross-Encoder. Trả về đúng top_k kết quả.
    """
    dense_vec = embed_model.encode(f"query: {query}", normalize_embeddings=True).tolist()
    sparse_vec = list(sparse_model.embed([query]))[0]
    sparse_qdrant = rest.SparseVector(indices=sparse_vec.indices.tolist(), values=sparse_vec.values.tolist())

    try:
        # Lấy trực tiếp số lượng top_k từ Qdrant
        fusion_results = qdrant_client.query_points(
            collection_name=COLLECTION_NAME,
            prefetch=[
                rest.Prefetch(query=dense_vec, using="dense", limit=top_k),
                rest.Prefetch(query=sparse_qdrant, using="sparse", limit=top_k),
            ],
            query=rest.FusionQuery(fusion=rest.Fusion.RRF),
            with_payload=True,
            limit=top_k # Giới hạn đúng số lượng cần thiết (Ví dụ: 4)
        ).points
        return fusion_results
    except Exception as e:
        print(f"Lỗi Qdrant RRF: {e}")
        return []

# ================= HÀM CHẠY CHÍNH =================
def generate_ragas_dataset(input_csv="ragas_ground_truth_auto.csv", output_csv="ragas_ready_data_baseline.csv"): # Đổi tên file output để tránh ghi đè
    print(f"Đọc dữ liệu gốc từ {input_csv}...")
    df_input = pd.read_csv(input_csv)
    
    processed_count = 0
    
    if os.path.exists(output_csv):
        df_existing = pd.read_csv(output_csv)
        processed_count = len(df_existing)
        print(f"Phát hiện file {output_csv} đã có {processed_count} dòng.")
        if processed_count >= len(df_input):
            print("Toàn bộ dữ liệu đã được xử lý xong từ trước!")
            return
        print(f"Sẽ chạy TÍÊP TỤC từ dòng số {processed_count}...")
    else:
        print(f"Chưa có file kết quả, tạo mới {output_csv}...")
        empty_df = pd.DataFrame(columns=["question", "contexts", "answer", "ground_truth"])
        empty_df.to_csv(output_csv, index=False, encoding='utf-8-sig')

    print("Đang chạy RAG pipeline thực tế (CẤU HÌNH BASELINE - KHÔNG RERANK)...")
    
    for index, row in tqdm(df_input.iterrows(), total=len(df_input)):
        if index < processed_count:
            continue
            
        question = row['question']
        ground_truth = row['ground_truth']
        
        current_ai_client = get_next_client()
        
        # --- BƯỚC 1: TRUY XUẤT (ĐÃ THAY ĐỔI) ---
        try:
            parsed = parse_query_with_llm(question)
            
            # SỬ DỤNG HÀM MỚI CHỈ TÌM KIẾM VECTOR, LẤY TOP 4
            hits = hybrid_search_without_rerank(
                parsed.rewritten_query, 
                top_k=4 
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
        new_row = pd.DataFrame([{
            "question": question,
            "contexts": contexts_list, 
            "answer": answer,
            "ground_truth": ground_truth
        }])
        
        new_row.to_csv(output_csv, mode='a', header=False, index=False, encoding='utf-8-sig')
        
        time.sleep(1.5)

    print("\nHoàn tất! Dữ liệu (Baseline) đã được chuẩn bị đầy đủ.")

if __name__ == "__main__":
    generate_ragas_dataset()