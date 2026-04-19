#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Chunking Markdown với chiến lược:
- Split theo heading (MarkdownHeaderTextSplitter)
- Token split với chunk_size=400, overlap=50, tokenizer E5
- Inject metadata (title, author, year, major, heading path) vào nội dung chunk (Context Enrichment)
- Lưu chunk vào JSON với metadata đầy đủ và original_content (không prefix)
"""

import json
import pathlib
import logging
from pymongo import MongoClient
from langchain_text_splitters import (
    RecursiveCharacterTextSplitter,
    MarkdownHeaderTextSplitter
)
from tqdm import tqdm
from transformers import AutoTokenizer

# ================== CẤU HÌNH ==================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TOKENIZER = AutoTokenizer.from_pretrained("intfloat/multilingual-e5-large")
CHUNK_SIZE = 400          # tokens (tận dụng tối đa context window của E5)
CHUNK_OVERLAP = 50        # tokens (12.5% overlap)
HEADERS_TO_SPLIT = [
    ("#", "Header_1"),
    ("##", "Header_2"),
    ("###", "Header_3"),
]

MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "ctu"
COLL_NAME = "thesis_metadata"

def count_tokens(text: str) -> int:
    """Đếm token bằng đúng tokenizer của E5"""
    return len(TOKENIZER.encode(text, add_special_tokens=False))

def enrich_chunk_content(chunk_text: str, global_meta: dict, doc_metadata: dict) -> str:
    """
    Inject bối cảnh toàn cục vào đầu chunk.
    global_meta: từ MongoDB (title, author, year, major, standard_major)
    doc_metadata: heading hierarchy (Header_1, Header_2, Header_3)
    """
    title = global_meta.get('title', '')
    if len(title) > 150:
        title = title[:147] + "..."
    author = global_meta.get('author', '')
    year = global_meta.get('year', '')
    major = global_meta.get('standard_major', '') or global_meta.get('major', '')
    
    # Xây dựng đường dẫn heading
    heading_parts = []
    for level in ['Header_1', 'Header_2', 'Header_3']:
        if doc_metadata.get(level):
            heading_parts.append(doc_metadata[level])
    heading_path = " > ".join(heading_parts) if heading_parts else ""
    
    # Tạo prefix
    prefix_parts = []
    if title:
        prefix_parts.append(f"[{title}]")
    if author and year:
        prefix_parts.append(f"({author}, {year})")
    elif year:
        prefix_parts.append(f"(Năm {year})")
    if major:
        prefix_parts.append(f"[{major}]")
    if heading_path:
        prefix_parts.append(heading_path)
    
    prefix = " ".join(prefix_parts) + "\n" if prefix_parts else ""
    return prefix + chunk_text

def process_batch_chunking(md_folder: str, output_folder: str):
    md_path = pathlib.Path(md_folder)
    out_path = pathlib.Path(output_folder)
    out_path.mkdir(parents=True, exist_ok=True)
    
    # Kết nối MongoDB
    mongo_client = MongoClient(MONGO_URI)
    db = mongo_client[DB_NAME]
    meta_col = db[COLL_NAME]
    
    # Khởi tạo splitters
    markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=HEADERS_TO_SPLIT)
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=count_tokens,
        separators=["\n\n", "\n", ".", " ", ""]
    )
    
    md_files = list(md_path.glob("*.md"))
    logger.info(f"Tìm thấy {len(md_files)} file Markdown. Bắt đầu chunking...")
    
    for md_file in tqdm(md_files, desc="Chunking"):
        file_id = md_file.stem
        output_file = out_path / f"{file_id}_chunks.json"
        if output_file.exists():
            logger.debug(f"Bỏ qua {md_file.name} (đã có chunk)")
            continue
        
        # Lấy metadata từ MongoDB (dùng tên PDF tương ứng)
        pdf_name = md_file.with_suffix('.md').name
        global_meta = meta_col.find_one({"file_name": pdf_name}, {"_id": 0})
        if not global_meta:
            logger.warning(f"Không tìm thấy metadata cho {pdf_name}, dùng giá trị mặc định")
            global_meta = {
                "title": "N/A",
                "author": "N/A",
                "major": "N/A",
                "standard_major": "N/A",
                "year": "N/A",
                "status": "missing_metadata"
            }
        
        try:
            content = md_file.read_text(encoding="utf-8")
            if not content.strip():
                continue
            
            # Bước 1: Split theo heading
            header_splits = markdown_splitter.split_text(content)
            # Bước 2: Split token nếu cần
            final_splits = text_splitter.split_documents(header_splits)
            
            file_chunks = []
            for idx, doc in enumerate(final_splits):
                original_text = doc.page_content.strip()
                if len(original_text) < 30:
                    continue
                
                # Enrich content
                enriched = enrich_chunk_content(original_text, global_meta, doc.metadata)
                
                chunk_entry = {
                    "id": f"{file_id}_{idx}",
                    "content": enriched,   # Dùng để embedding
                    "metadata": {
                        **global_meta,
                        **doc.metadata,
                        "chunk_index": idx,
                        "source_file": md_file.name,
                        "token_count": count_tokens(original_text),
                        "original_content": original_text   # Giữ bản gốc để hiển thị
                    }
                }
                file_chunks.append(chunk_entry)
            
            # Lưu file JSON
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(file_chunks, f, ensure_ascii=False, indent=2)
            logger.info(f"Đã tạo {len(file_chunks)} chunks cho {md_file.name}")
            
        except Exception as e:
            logger.error(f"Lỗi xử lý {md_file.name}: {e}")
    
    mongo_client.close()
    logger.info(f"Hoàn tất. Chunks lưu tại {output_folder}")

if __name__ == "__main__":
    process_batch_chunking("output_md", "chunks_data")