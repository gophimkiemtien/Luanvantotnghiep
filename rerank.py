import json
import pandas as pd
import requests
import time
from google import genai
from pydantic import BaseModel, Field
from tqdm import tqdm

# ==========================================
# 1. CẤU HÌNH HỆ THỐNG & DANH SÁCH API KEYS
# ==========================================
# Đã đổi URL thành endpoint cấu hình Cắt giảm (Baseline)
API_URL = "http://127.0.0.1:8000/ask-vector-only" 
INPUT_CSV = r"D:\LV_OFFICIAL\eval\ragas\kq.csv"
OUTPUT_RESULTS = "ragas_metrics_report_baseline.csv" # Tên file output mới

# ĐIỀN DANH SÁCH CÁC API KEY CỦA BẠN VÀO ĐÂY
API_KEYS = [
   
]

def get_gemini_client(key_index):
    return genai.Client(api_key=API_KEYS[key_index % len(API_KEYS)])

class RagasMetrics(BaseModel):
    faithfulness: float = Field(description="Điểm trung thực từ 0.0 đến 1.0")
    answer_relevancy: float = Field(description="Điểm liên quan từ 0.0 đến 1.0")
    context_precision: float = Field(description="Điểm chính xác ngữ cảnh từ 0.0 đến 1.0")
    context_recall: float = Field(description="Điểm độ phủ ngữ cảnh từ 0.0 đến 1.0")
    reasoning: str = Field(description="Giải thích ngắn gọn lý do tại sao cho các mức điểm này")

# ==========================================
# 2. HÀM CHẠY ĐÁNH GIÁ CHÍNH
# ==========================================
def run_evaluation():
    try:
        df = pd.read_csv(INPUT_CSV, encoding='utf-8-sig').reset_index(drop=True)
    except FileNotFoundError:
        print(f"❌ Không tìm thấy file {INPUT_CSV}. Vui lòng kiểm tra đường dẫn.")
        return

    results = []
    print(f"🚀 BẮT ĐẦU ĐÁNH GIÁ HỆ THỐNG (BASELINE - VECTOR ONLY) ({len(df)} câu hỏi) VỚI {len(API_KEYS)} API KEYS...")

    current_key_index = 0
    client = get_gemini_client(current_key_index)

    for i, row in tqdm(df.iterrows(), total=len(df), desc="Tiến độ"):
        question = row['question']
        ground_truth = row['ground_truth']
        
        try:
            # --- BƯỚC A: GỌI BACKEND RAG (Chỉ Vector Search) ---
            bot_data = None
            latency = 0
            
            for attempt in range(3):
                try:
                    start_time = time.time()
                    response = requests.post(API_URL, json={"query": question}, timeout=90)
                    if response.status_code == 200:
                        bot_data = response.json()
                        latency = time.time() - start_time
                        break
                    else:
                        print(f"\n⚠️ Backend báo lỗi {response.status_code}. Đang thử lại...")
                        time.sleep(5)
                except Exception:
                    time.sleep(5)

            if not bot_data:
                print(f"\n❌ Bỏ qua câu {i+1} do Backend không phản hồi.")
                continue

            answer = bot_data.get('answer', '')
            retrieved_chunks = bot_data.get('results', []) 
            
            contexts = "\n---\n".join([
                f"Tiêu đề: {c.get('title', '')}\nTóm tắt: {c.get('original_abstract', '')}" 
                for c in retrieved_chunks
            ])
            
            # --- BƯỚC B: GIÁM KHẢO GEMINI CHẤM ĐIỂM ---
            judge_prompt = f"""
            Bạn là một Giám khảo chấm điểm hệ thống Trợ lý ảo Học thuật (RAG). 
            Hãy đánh giá hệ thống một cách khắt khe dựa trên 4 chỉ số (từ 0.0 đến 1.0).
            
            [THÔNG TIN ĐẦU VÀO]
            - CÂU HỎI: {question}
            - ĐÁP ÁN CHUẨN (GROUND TRUTH): {ground_truth}
            - NGỮ CẢNH HỆ THỐNG TÌM ĐƯỢC: {contexts}
            - CÂU TRẢ LỜI CỦA HỆ THỐNG: {answer}
            
            [HƯỚNG DẪN CHẤM ĐIỂM]
            1. Faithfulness (0.0 - 1.0): Nội dung trong 'CÂU TRẢ LỜI CỦA HỆ THỐNG' có được lấy trực tiếp từ 'NGỮ CẢNH' không? Phạt điểm 0.0 nếu bịa đặt (ảo giác).
            2. Answer Relevancy (0.0 - 1.0): Mức độ 'CÂU TRẢ LỜI CỦA HỆ THỐNG' giải quyết đúng và trực tiếp 'CÂU HỎI'. Phạt nếu trả lời lan man.
            3. Context Precision (0.0 - 1.0): Các thông tin quan trọng nhất để trả lời câu hỏi có nằm ở phần ĐẦU của 'NGỮ CẢNH' không? 
            4. Context Recall (0.0 - 1.0): 'NGỮ CẢNH' có chứa đầy đủ thông tin để trả lời câu hỏi giống như 'ĐÁP ÁN CHUẨN' không?
            """

            scores = None
            max_retries = len(API_KEYS) + 2
            
            for attempt in range(max_retries):
                try:
                    judge_res = client.models.generate_content(
                        model='gemini-2.5-flash', 
                        contents=judge_prompt,
                        config={
                            'response_mime_type': 'application/json', 
                            'response_schema': RagasMetrics,
                            'temperature': 0.0 
                        }
                    )
                    scores = json.loads(judge_res.text)
                    break 
                    
                except Exception as e:
                    if "429" in str(e):
                        current_key_index += 1
                        print(f"\n🔄 Key hiện tại đã hết hạn mức. Tự động đổi sang Key số {(current_key_index % len(API_KEYS)) + 1}...")
                        client = get_gemini_client(current_key_index)
                        time.sleep(3) 
                    else:
                        print(f"\n⚠️ Lỗi khác từ Gemini API: {e}")
                        time.sleep(5)

            if scores is None:
                print(f"\n❌ Lỗi chấm điểm câu {i+1} dù đã xoay vòng hết các API Key.")
                continue

            results.append({
                "id": i + 1,
                "question": question,
                "faithfulness": scores['faithfulness'],
                "answer_relevancy": scores['answer_relevancy'],
                "context_precision": scores['context_precision'],
                "context_recall": scores['context_recall'],
                "latency": latency,
                "reasoning": scores['reasoning']
            })

            time.sleep(5) 

        except Exception as e:
            print(f"\n❌ Lỗi không xác định tại câu {i+1}: {e}")

    # --- BƯỚC C: TỔNG HỢP VÀ IN KẾT QUẢ ---
    if not results:
        print("😭 Đánh giá thất bại, không có dữ liệu nào được ghi nhận.")
        return

    res_df = pd.DataFrame(results)
    
    print("\n" + "="*60)
    print("📊 KẾT QUẢ ĐÁNH GIÁ ĐỊNH LƯỢNG (BASELINE - VECTOR ONLY)")
    print("="*60)
    print(f"✅ Faithfulness (Độ trung thực)       : {res_df['faithfulness'].mean():.4f}")
    print(f"✅ Answer Relevancy (Độ liên quan)    : {res_df['answer_relevancy'].mean():.4f}")
    print(f"✅ Context Precision (Độ CX ngữ cảnh) : {res_df['context_precision'].mean():.4f}")
    print(f"✅ Context Recall (Độ phủ ngữ cảnh)   : {res_df['context_recall'].mean():.4f}")
    print(f"⏱️ Thời gian phản hồi TB (Latency)    : {res_df['latency'].mean():.4f} giây")
    print("="*60)

    res_df.to_csv(OUTPUT_RESULTS, index=False, encoding='utf-8-sig')
    print(f"📝 Đã lưu chi tiết từng câu vào file: {OUTPUT_RESULTS}")

if __name__ == "__main__":
    run_evaluation()
