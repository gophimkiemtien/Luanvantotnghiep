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
API_URL = "http://127.0.0.1:8000/ask" 
INPUT_CSV = "ground_truth_abstracts.csv"
OUTPUT_RESULTS = "ragas_metrics_report.csv"

# ĐIỀN DANH SÁCH CÁC API KEY CỦA BẠN VÀO ĐÂY (Nhiều key sẽ giúp chạy liên tục)
API_KEYS = [
    "AIzaSyAXnbFztC8sTDCNAgzom33B4lKuwI8Ayq8",
    "AIzaSyB6nDFxCHNzdhhEpyPhbSqnPOv7k0LkZT4",
    "AIzaSyApY7_RWjMicD_y2DFft5JLhGDKQUfmGps",
    "AIzaSyCa3_A61QAuyaYkQklrH3bgb5qfaiA8Lm8",
    "AIzaSyAV6TmNv38I_PbCmkxKxba-bYdbgFfLuX8",
    "AIzaSyBj6EUHvwgAOvR-k1AkzixQCogpfC999e8",
    "AIzaSyCkJcreuzGY7aL83K8JkPGfo-4eFwLQkbI",
    "AIzaSyC3nMjfAtdQbgTPEu_3JIdHPlF0tsIUryI"
]

# Hàm khởi tạo client với Key hiện tại (Tự động xoay vòng)
def get_gemini_client(key_index):
    return genai.Client(api_key=API_KEYS[key_index % len(API_KEYS)])

# Schema bắt buộc định dạng kết quả trả về từ Giám khảo
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
    print(f"🚀 BẮT ĐẦU ĐÁNH GIÁ HỆ THỐNG ({len(df)} câu hỏi) VỚI {len(API_KEYS)} API KEYS...")

    # Bắt đầu với Key đầu tiên trong danh sách
    current_key_index = 0
    client = get_gemini_client(current_key_index)

    for i, row in tqdm(df.iterrows(), total=len(df), desc="Tiến độ"):
        question = row['question']
        ground_truth = row['expected_answer']
        
        try:
            # --- BƯỚC A: GỌI BACKEND RAG ---
            bot_data = None
            latency = 0
            
            # Retry 3 lần nếu Backend bị sập (lỗi 10054/10061)
            for attempt in range(3):
                try:
                    start_time = time.time()
                    # Sử dụng payload 'query' giống như swagger đã yêu cầu
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

            # ĐỌC CHUẨN XÁC DỮ LIỆU TỪ BACKEND
            bot_answer = bot_data.get('answer', '')
            retrieved_chunks = bot_data.get('results', []) # Đã sửa thành 'results'
            
            # Ghép Tiêu đề và Abstract lại để tạo thành Context đầy đủ
            retrieved_context = "\n---\n".join([
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
            - NGỮ CẢNH HỆ THỐNG TÌM ĐƯỢC: {retrieved_context}
            - CÂU TRẢ LỜI CỦA HỆ THỐNG: {bot_answer}
            
            [HƯỚNG DẪN CHẤM ĐIỂM]
            1. Faithfulness (0.0 - 1.0): Nội dung trong 'CÂU TRẢ LỜI CỦA HỆ THỐNG' có được lấy trực tiếp từ 'NGỮ CẢNH' không? Phạt điểm 0.0 nếu bịa đặt (ảo giác).
            2. Answer Relevancy (0.0 - 1.0): Mức độ 'CÂU TRẢ LỜI CỦA HỆ THỐNG' giải quyết đúng và trực tiếp 'CÂU HỎI'. Phạt nếu trả lời lan man.
            3. Context Precision (0.0 - 1.0): Các thông tin quan trọng nhất để trả lời câu hỏi có nằm ở phần ĐẦU của 'NGỮ CẢNH' không? 
            4. Context Recall (0.0 - 1.0): 'NGỮ CẢNH' có chứa đầy đủ thông tin để trả lời câu hỏi giống như 'ĐÁP ÁN CHUẨN' không?
            """

            scores = None
            max_retries = len(API_KEYS) + 2 # Cho phép thử số lần bằng số Key cộng thêm 2 lần dự phòng
            
            for attempt in range(max_retries):
                try:
                    judge_res = client.models.generate_content(
                        model='gemini-2.5-flash', 
                        contents=judge_prompt,
                        config={
                            'response_mime_type': 'application/json', 
                            'response_schema': RagasMetrics,
                            'temperature': 0.0 # ĐÃ THÊM: Đảm bảo độ nhất quán 100% như lý thuyết
                        }
                    )
                    scores = json.loads(judge_res.text)
                    break # Thành công thì thoát vòng lặp Retry
                    
                except Exception as e:
                    if "429" in str(e):
                        # NẾU BỊ GIỚI HẠN (RATE LIMIT) -> CHUYỂN SANG KEY TIẾP THEO
                        current_key_index += 1
                        print(f"\n🔄 Key hiện tại đã hết hạn mức. Tự động đổi sang Key số {(current_key_index % len(API_KEYS)) + 1}...")
                        client = get_gemini_client(current_key_index)
                        time.sleep(3) # Nghỉ 1 nhịp ngắn cho an toàn
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

            # Thời gian nghỉ chuẩn giữa mỗi câu (đã có nhiều key thì chỉ cần nghỉ 5s)
            time.sleep(5) 

        except Exception as e:
            print(f"\n❌ Lỗi không xác định tại câu {i+1}: {e}")

    # --- BƯỚC C: TỔNG HỢP VÀ IN KẾT QUẢ ---
    if not results:
        print("😭 Đánh giá thất bại, không có dữ liệu nào được ghi nhận.")
        return

    res_df = pd.DataFrame(results)
    
    print("\n" + "="*60)
    print("📊 KẾT QUẢ ĐÁNH GIÁ ĐỊNH LƯỢNG (DÙNG CHO BẢNG 4.1 & 4.2)")
    print("="*60)
    print(f"✅ Faithfulness (Độ trung thực)       : {res_df['faithfulness'].mean():.4f}")
    print(f"✅ Answer Relevancy (Độ liên quan)    : {res_df['answer_relevancy'].mean():.4f}")
    print(f"✅ Context Precision (Độ CX ngữ cảnh) : {res_df['context_precision'].mean():.4f}")
    print(f"✅ Context Recall (Độ phủ ngữ cảnh)   : {res_df['context_recall'].mean():.4f}")
    print(f"⏱️ Thời gian phản hồi TB (Latency)    : {res_df['latency'].mean():.4f} giây")
    print("="*60)

    res_df.to_csv(OUTPUT_RESULTS, index=False, encoding='utf-8-sig')
    print(f"📝 Đã lưu chi tiết từng câu (kèm nhận xét của Giám khảo) vào file: {OUTPUT_RESULTS}")

if __name__ == "__main__":
    run_evaluation()