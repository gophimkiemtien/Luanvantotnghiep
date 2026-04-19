#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Trích xuất toàn bộ metadata và nội dung AI từ file Markdown,
kèm theo phân loại chuẩn chuyên ngành theo danh sách hardcode.
Tích hợp: MongoDB, Multi-Key Round-Robin, Tự động Retry.
"""

import os
import re
import pathlib
import argparse
import itertools
import time
from typing import List
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from pymongo import MongoClient

# ==========================================
# 1. CẤU HÌNH DATABASE & AI
# ==========================================
MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "ctu"
COLLECTION_NAME = "thesis_metadata"
MODEL_ID = "gemini-2.5-flash"

# Điền danh sách các API Key của bạn vào đây
API_KEYS = [
   
]

# Tạo bộ sinh vòng lặp vô tận cho API Keys
key_pool = itertools.cycle(API_KEYS)

# Kết nối MongoDB
client = MongoClient(MONGO_URI)
db = client[DB_NAME]
collection = db[COLLECTION_NAME]

# ==========================================
# 2. DANH SÁCH CHUẨN CÁC CHUYÊN NGÀNH
# ==========================================
STANDARD_MAJORS = [
"An toàn thông tin", "Bảo vệ thực vật", "Báo chí", "Bệnh học thủy sản", "Chăn nuôi",
"Chính trị học", "Công nghệ sau thu hoạch", "Công nghệ sinh học", "Công nghệ tài chính",
"Công nghệ thực phẩm", "Công nghệ chế biến thủy sản", "Công nghệ kỹ thuật hóa học",
"Công nghệ rau hoa quả và cảnh quan", "Công nghệ thông tin", "Du lịch", "Giáo dục công dân",
"Giáo dục mầm non", "Giáo dục thể chất", "Giáo dục tiểu học", "Hệ thống thông tin",
"Hóa dược", "Hóa học", "Kế toán", "Kiểm toán", "Kinh doanh quốc tế", "Kinh doanh thương mại",
"Kinh tế", "Kinh tế nông nghiệp", "Kinh tế tài nguyên thiên nhiên", "Khoa học cây trồng",
"Khoa học dữ liệu", "Khoa học đất", "Khoa học máy tính", "Khoa học môi trường",
"Kỹ thuật cấp thoát nước", "Kỹ thuật cơ điện tử", "Kỹ thuật cơ khí", "Kỹ thuật điều khiển và tự động hóa",
"Kỹ thuật điện", "Kỹ thuật điện tử - viễn thông", "Kỹ thuật máy tính", "Kỹ thuật môi trường",
"Kỹ thuật ô tô", "Kỹ thuật phần mềm", "Kỹ thuật vật liệu", "Kỹ thuật xây dựng",
"Kỹ thuật xây dựng công trình giao thông", "Kỹ thuật xây dựng công trình thủy", "Kỹ thuật y sinh",
"Logistics và Quản lý chuỗi cung ứng", "Luật", "Luật kinh tế", "Mạng máy tính và truyền thông dữ liệu",
"Marketing", "Ngôn ngữ Anh", "Ngôn ngữ Pháp", "Nông học", "Nuôi trồng thủy sản",
"Quản lý công nghiệp", "Quản lý đất đai", "Quản lý tài nguyên và môi trường", "Quản lý thủy sản",
"Quản lý xây dựng", "Quản trị dịch vụ du lịch và lữ hành", "Quản trị kinh doanh", "Quy hoạch vùng và đô thị",
"Sinh học", "Sinh học ứng dụng", "Sư phạm địa lý", "Sư phạm hóa học", "Sư phạm khoa học tự nhiên",
"Sư phạm lịch sử", "Sư phạm lịch sử - địa lý", "Sư phạm ngữ văn", "Sư phạm sinh học", "Sư phạm tiếng anh",
"Sư phạm tiếng pháp", "Sư phạm tin học", "Sư phạm toán học", "Sư phạm vật lý", "Tài chính - Ngân hàng",
"Thống kê", "Thông tin - thư viện", "Thú y", "Toán ứng dụng", "Triết học",
"Truyền thông đa phương tiện", "Văn học", "Vật lý kỹ thuật", "Xã hội học"
]

# ==========================================
# 3. ĐỊNH NGHĨA SCHEMA ĐẦU RA (Pydantic)
# ==========================================
class ThesisFullExtraction(BaseModel):
    title: str = Field(description="Tên đề tài luận văn")
    author: str = Field(description="Họ tên tác giả")
    major: str = Field(description="Tên chuyên ngành đào tạo (ghi đúng như trên bìa)")
    student_id: str = Field(description="Mã số sinh viên / học viên")
    year: int = Field(description="Năm bảo vệ hoặc năm tốt nghiệp (dạng số)")
    supervisor: str = Field(description="Họ tên người hướng dẫn, có thể kèm học vị")
    original_abstract: str = Field(description="Toàn bộ nội dung phần TÓM TẮT gốc")
    ai_tldr: str = Field(description="Đoạn tóm tắt siêu ngắn gọn mục tiêu, phương pháp, kết quả chính")
    keywords: List[str] = Field(description="Danh sách 5-7 từ khóa quan trọng nhất")
    applied_topic: List[str] = Field(description="1-2 lĩnh vực ứng dụng thực tế (không phải chuyên ngành)")
    standard_major: str = Field(description=f"Phân loại luận văn vào MỘT trong các chuyên ngành sau: {', '.join(STANDARD_MAJORS)}. Tuyệt đối không dùng chuyên ngành khác ngoài danh sách này.")

# ==========================================
# 4. HÀM ĐỌC FILE MARKDOWN
# ==========================================
def read_md_file(md_path: pathlib.Path) -> tuple[str, str]:
    content = md_path.read_text(encoding="utf-8")
    
    cover_match = re.search(r'# THÔNG TIN BÌA\n(.*?)(?=# TÓM TẮT|# NỘI DUNG CHÍNH|\Z)', content, re.DOTALL | re.IGNORECASE)
    cover_text = cover_match.group(1).strip() if cover_match else ""
    
    abstract_match = re.search(r'# TÓM TẮT\n(.*?)(?=# NỘI DUNG CHÍNH|\Z)', content, re.DOTALL | re.IGNORECASE)
    abstract_text = abstract_match.group(1).strip() if abstract_match else ""
    
    if not abstract_text:
        content_match = re.search(r'# NỘI DUNG CHÍNH\n(.*)', content, re.DOTALL | re.IGNORECASE)
        if content_match:
            abstract_text = content_match.group(1).strip()[:3000]
            
    return cover_text, abstract_text

# ==========================================
# 5. GỌI GEMINI VỚI CƠ CHẾ ĐỔI KEY TỰ ĐỘNG
# ==========================================
def extract_all_from_md(cover_text: str, abstract_text: str, max_retries: int = 5) -> ThesisFullExtraction:
    majors_list = "\n".join(f"- {m}" for m in STANDARD_MAJORS)
    prompt = f"""
Bạn là chuyên gia thư viện số. Hãy trích xuất thông tin từ luận văn dựa trên hai phần sau:

=== PHẦN BÌA ===
{cover_text}

=== PHẦN TÓM TẮT ===
{abstract_text}

Yêu cầu:
1. Trích xuất chính xác các trường metadata: title, author, major, student_id, year, supervisor.
2. Lấy toàn bộ nội dung phần TÓM TẮT làm original_abstract (giữ nguyên, không cắt xén).
3. Từ nội dung tóm tắt, hãy tạo:
   - ai_tldr: một đoạn 2-3 câu tóm gọn mục tiêu, phương pháp và kết quả/kết luận chính.
   - keywords: 5-7 từ khóa quan trọng nhất.
   - applied_topic: 1-2 lĩnh vực ứng dụng thực tế (KHÔNG phải tên chuyên ngành).
4. Phân loại luận văn vào MỘT trong các chuyên ngành chuẩn sau đây (tuyệt đối không tự chế):

{majors_list}

Trả về JSON theo đúng schema.
"""
    attempts = 0
    while attempts < max_retries:
        current_key = next(key_pool)
        ai_client = genai.Client(api_key=current_key)
        
        try:
            response = ai_client.models.generate_content(
                model=MODEL_ID,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ThesisFullExtraction,
                    temperature=0.1,
                ),
            )
            return ThesisFullExtraction.model_validate_json(response.text)
            
        except Exception as e:
            error_msg = str(e).lower()
            # Bắt lỗi 429 Quota Exceeded hoặc Too Many Requests
            if "429" in error_msg or "exhausted" in error_msg or "quota" in error_msg:
                attempts += 1
                print(f"   ⚠️ Key đang dùng báo quá tải/hết hạn mức. Đang đổi key khác (Thử lại {attempts}/{max_retries})...")
                time.sleep(3) # Nghỉ một chút trước khi thử key mới
            else:
                # Nếu là lỗi cú pháp, mất mạng... thì in ra và thử lại luôn
                attempts += 1
                print(f"   ⚠️ Lỗi API: {e}. Đang thử lại ({attempts}/{max_retries})...")
                time.sleep(2)
                
    raise Exception("Đã thử hết vòng lặp Key nhưng vẫn thất bại. Vui lòng kiểm tra lại mạng hoặc API Keys!")

# ==========================================
# 6. XỬ LÝ BATCH
# ==========================================
def process_all_md_files(md_folder: str, overwrite: bool = False):
    md_dir = pathlib.Path(md_folder)
    
    if not md_dir.exists():
        print(f"❌ Không tìm thấy thư mục: {md_folder}")
        return
        
    md_files = list(md_dir.glob("*.md"))
    total = len(md_files)
    if total == 0:
        print(f"⚠️ Thư mục '{md_folder}' trống. Hãy chạy tool tách PDF trước!")
        return
    
    print(f"🚀 Tìm thấy {total} file Markdown. Bắt đầu xử lý AI...\n" + "="*50)
    success_count = 0
    
    for idx, md_path in enumerate(md_files, 1):
        file_name = md_path.name
        
        # KIỂM TRA FILE TRONG MONGODB
        existing = collection.find_one({"file_name": file_name})
        if existing and not overwrite:
            print(f"[{idx}/{total}] ⏭️ Bỏ qua (đã có trong Database): {file_name}")
            continue
        
        print(f"[{idx}/{total}] 📄 Đang phân tích bằng AI: {file_name}")
        cover_text, abstract_text = read_md_file(md_path)
        
        if not abstract_text:
            print(f"   ⚠️ Không tìm thấy phần TÓM TẮT trong {file_name}, bỏ qua.")
            continue
        
        try:
            extracted = extract_all_from_md(cover_text, abstract_text)
            
            doc = {
                "file_name": file_name,
                "title": extracted.title,
                "author": extracted.author,
                "major": extracted.major,               
                "student_id": extracted.student_id,
                "year": extracted.year,
                "supervisor": extracted.supervisor,
                "original_abstract": extracted.original_abstract,
                "ai_tldr": extracted.ai_tldr,
                "keywords": extracted.keywords,
                "applied_topic": extracted.applied_topic,
                "standard_major": extracted.standard_major,  
                "status": "extracted",
                "updated_at": time.time()
            }
            
            collection.update_one(
                {"file_name": file_name},
                {"$set": doc},
                upsert=True
            )
            success_count += 1
            print(f"   ✅ Đã lưu DB: {extracted.title[:45]}... | Ngành: {extracted.standard_major}")
            
            # Delay nhẹ để các key có thời gian "thở", tránh spam hệ thống Google quá nhanh
            time.sleep(2) 
            
        except Exception as e:
            print(f"   ❌ Bỏ qua file {file_name} do lỗi hệ thống: {e}")
    
    print("="*50)
    print(f"🎉 Hoàn tất Phase 2! Đã xử lý và đưa vào MongoDB thành công {success_count}/{total} file.")

# ==========================================
# 7. MAIN CÓ TÍCH HỢP ARGPARSE
# ==========================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Phase 2: Trích xuất metadata luận văn bằng AI Gemini (Multi-key) và lưu vào MongoDB."
    )
    parser.add_argument("-i", "--input", default="output_md", help="Thư mục chứa file Markdown (mặc định: output_md)")
    parser.add_argument("--overwrite", action="store_true", help="Kích hoạt ghi đè nếu file đã tồn tại trong Database")
    
    args = parser.parse_args()
    
    process_all_md_files(args.input, overwrite=args.overwrite)
