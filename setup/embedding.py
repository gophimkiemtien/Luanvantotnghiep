#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Upload chunks (JSON) vào Qdrant với kiến trúc Hybrid Search: 
Dense vector (E5) + Sparse vector (BM25 qua FastEmbed).
Đảm bảo: offline processing, payload index, retry, logging, doc‑level vectors.
"""

import json
import pathlib
import uuid
import time
import logging
from typing import List

import torch
from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    Distance, VectorParams, PointStruct, SparseVector,
    PayloadSchemaType
)
from sentence_transformers import SentenceTransformer
from fastembed import SparseTextEmbedding
from tqdm import tqdm
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# ==========================================
# 1. CẤU HÌNH LOGGING
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('qdrant_upload.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ==========================================
# 2. CẤU HÌNH THAM SỐ
# ==========================================
QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = "thesis_ctu"          # Collection lưu chunks (Dense + Sparse)
DOC_COLLECTION_NAME = "thesis_ctu_documents"   # Collection lưu vector đại diện cho toàn bộ luận văn (chỉ Dense)
CHUNKS_FOLDER = "chunks_data"
BATCH_SIZE = 32
UPLOAD_BATCH_SIZE = 100
DEVICE = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"

logger.info(f"⚙️ Sử dụng thiết bị: {DEVICE.upper()}")

# ==========================================
# 3. KHỞI TẠO QDRANT & MODELS
# ==========================================
qdrant = QdrantClient(url=QDRANT_URL, timeout=60)

logger.info("⏳ Đang tải mô hình Dense (intfloat/multilingual-e5-large)...")
model = SentenceTransformer('intfloat/multilingual-e5-large', device=DEVICE)
EMBED_DIM = model.get_sentence_embedding_dimension()
logger.info(f"✅ Mô hình Dense loaded, kích thước vector: {EMBED_DIM}")

logger.info("⏳ Đang tải mô hình Sparse (Qdrant/bm25 via FastEmbed)...")
sparse_model = SparseTextEmbedding(model_name="Qdrant/bm25")
logger.info("✅ Mô hình Sparse loaded thành công.")


# ==========================================
# 4. TẠO COLLECTION VÀ PAYLOAD INDEX
# ==========================================
def ensure_collection(collection_name: str, is_doc_collection: bool = False):
    """Tạo collection và payload index cho các trường quan trọng."""
    if not qdrant.collection_exists(collection_name):
        if is_doc_collection:
            # Document collection chỉ cần dense vector
            qdrant.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=EMBED_DIM, distance=Distance.COSINE)
            )
            logger.info(f"✅ Đã tạo document collection: {collection_name}")
        else:
            # Chunks collection hỗ trợ Hybrid (Dense + Sparse)
            qdrant.create_collection(
                collection_name=collection_name,
                vectors_config={
                    "dense": VectorParams(size=EMBED_DIM, distance=Distance.COSINE),
                },
                sparse_vectors_config={
                    "sparse": {} # Qdrant tự quản lý cấu hình sparse
                }
            )
            logger.info(f"✅ Đã tạo chunks collection (Hybrid): {collection_name}")
    else:
        logger.info(f"ℹ️ Collection '{collection_name}' đã tồn tại.")

    # Tạo payload index cho các trường dùng để filter
    indexes_to_create = [
        ("metadata.year", PayloadSchemaType.INTEGER),
        ("metadata.major", PayloadSchemaType.KEYWORD),
        ("metadata.standard_major", PayloadSchemaType.KEYWORD),
        ("metadata.file_name", PayloadSchemaType.KEYWORD),
        ("chunk_id", PayloadSchemaType.KEYWORD),
    ]
    for field, schema_type in indexes_to_create:
        try:
            qdrant.create_payload_index(
                collection_name=collection_name,
                field_name=field,
                field_schema=schema_type
            )
            logger.info(f"   📌 Tạo index cho {field}")
        except Exception as e:
            if "already exists" in str(e).lower():
                logger.debug(f"Index {field} đã tồn tại")
            else:
                logger.warning(f"Không thể tạo index {field}: {e}")

# ==========================================
# 5. UPLOAD VỚI RETRY
# ==========================================
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10),
       retry=retry_if_exception_type(Exception))
def upload_points_with_retry(collection_name: str, points: List[PointStruct]):
    """Upload points có retry khi mạng lỗi hoặc Qdrant bị quá tải."""
    qdrant.upload_points(
        collection_name=collection_name,
        points=points,
        batch_size=UPLOAD_BATCH_SIZE,
        wait=False # Chạy bất đồng bộ để tăng tốc
    )

# ==========================================
# 6. XỬ LÝ VÀ NẠP CHUNKS (DENSE + SPARSE)
# ==========================================
def upload_chunks_folder(chunks_folder: str):
    path = pathlib.Path(chunks_folder)
    json_files = list(path.glob("*.json"))
    if not json_files:
        logger.warning(f"Không tìm thấy file JSON trong {chunks_folder}")
        return

    logger.info(f"🚀 Bắt đầu nạp {len(json_files)} file luận văn vào Qdrant (Chunks)...")

    for json_file in tqdm(json_files, desc="Processing chunks"):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                chunks = json.load(f)
            if not chunks:
                continue

            # Chuẩn bị texts cho Dense (Dòng E5 bắt buộc có "passage: ")
            dense_texts = [f"passage: {chunk['content']}" for chunk in chunks]
            
            # Chuẩn bị texts cho Sparse (BM25 dùng text gốc)
            sparse_texts = [chunk['content'] for chunk in chunks]

            # Tính toán Vector
            # LƯU Ý: Đã bật normalize_embeddings=True cho Dense
            dense_vectors = model.encode(dense_texts, batch_size=BATCH_SIZE, normalize_embeddings=True, show_progress_bar=False)
            
            # Tính toán Sparse Vector bằng FastEmbed
            sparse_vectors = list(sparse_model.embed(sparse_texts, batch_size=BATCH_SIZE))

            points = []
            for idx, chunk in enumerate(chunks):
                point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk['id']))
                
                # Format sparse vector cho Qdrant
                sparse_vec_qdrant = SparseVector(
                    indices=sparse_vectors[idx].indices.tolist(),
                    values=sparse_vectors[idx].values.tolist()
                )

                points.append(PointStruct(
                    id=point_id,
                    vector={
                        "dense": dense_vectors[idx].tolist(),
                        "sparse": sparse_vec_qdrant
                    },
                    payload={
                        "chunk_id": chunk['id'],
                        "content": chunk['content'],
                        "metadata": chunk.get('metadata', {})
                    }
                ))

            upload_points_with_retry(COLLECTION_NAME, points)
            logger.debug(f"✅ Uploaded {len(points)} chunks từ {json_file.name}")

        except Exception as e:
            logger.error(f"❌ Lỗi xử lý file {json_file.name}: {e}")

    logger.info(f"🎉 Hoàn tất upload chunks vào collection '{COLLECTION_NAME}'.")


# ==========================================
# 7. TẠO VECTOR ĐẠI DIỆN CHO TOÀN BỘ LUẬN VĂN (DOC-LEVEL)
# ==========================================
def create_document_vectors(mongo_client, db_name, collection_name):
    """Lấy luận văn từ MongoDB, tạo vector đại diện và upload lên doc collection."""
    from pymongo import MongoClient
    mongo = mongo_client or MongoClient("mongodb://localhost:27017/")
    db = mongo[db_name]
    col = db[collection_name]

    docs = list(col.find({"ai_tldr": {"$exists": True, "$ne": ""}}))
    logger.info(f"📚 Tạo vector cho {len(docs)} luận văn...")

    points = []
    for doc in docs:
        rep_text = doc.get("ai_tldr", "") or doc.get("original_abstract", "")[:500]
        if not rep_text:
            continue
            
        vector = model.encode(f"passage: {rep_text}", normalize_embeddings=True).tolist()
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, doc["file_name"]))
        
        points.append(PointStruct(
            id=point_id,
            vector=vector,
            payload={
                "file_name": doc["file_name"],
                "title": doc.get("title", ""),
                "author": doc.get("author", ""),
                "year": doc.get("year"),
                "major": doc.get("major", ""),
                "standard_major": doc.get("standard_major", ""),
                "keywords": doc.get("keywords", []),
                "ai_tldr": rep_text
            }
        ))

    if points:
        upload_points_with_retry(DOC_COLLECTION_NAME, points)
        logger.info(f"✅ Đã upload {len(points)} document vectors vào '{DOC_COLLECTION_NAME}'.")
    else:
        logger.warning("Không có document nào có ai_tldr để tạo vector.")


# ==========================================
# 8. HÀM MAIN
# ==========================================
if __name__ == "__main__":
    start = time.time()
    try:
        # 1. Khởi tạo & Upload Chunks (Hybrid)
        ensure_collection(COLLECTION_NAME, is_doc_collection=False)
        upload_chunks_folder(CHUNKS_FOLDER)

        # 2. Khởi tạo & Upload Documents (Dense)
        ensure_collection(DOC_COLLECTION_NAME, is_doc_collection=True)
        try:
            from pymongo import MongoClient
            mongo_client = MongoClient("mongodb://localhost:27017/")
            create_document_vectors(mongo_client, "ctu", "thesis_metadata")
        except ImportError:
            logger.warning("Chưa cài pymongo, bỏ qua tạo document vectors.")
        except Exception as e:
            logger.error(f"Lỗi khi tạo document vectors: {e}")

        elapsed = time.time() - start
        logger.info(f"⏱️ Tổng thời gian thực hiện: {round(elapsed/60, 2)} phút.")
        
    except Exception as e:
        logger.exception(f"❌ Lỗi hệ thống: {e}")
        logger.info("💡 Đảm bảo Qdrant đang chạy và đã cài đặt: pip install sentence-transformers qdrant-client tenacity fastembed pymongo")