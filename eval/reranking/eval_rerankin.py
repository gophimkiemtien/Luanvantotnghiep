import time
import statistics
from pymongo import MongoClient
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer, CrossEncoder
import os
from dotenv import load_dotenv

# 1. Khởi tạo kết nối 
load_dotenv()
mongo_client = MongoClient("mongodb://localhost:27017/")
db = mongo_client["cantho_university"]
meta_col = db["thesis_metadata_final"]
qdrant_client = QdrantClient("http://localhost:6333")

COLLECTION_NAME = "thesis_chunks_v3"

# Tải Model
print("Đang tải models (vui lòng đợi)...")
embed_model = SentenceTransformer('intfloat/multilingual-e5-large', device='cpu')
reranker = CrossEncoder('BAAI/bge-reranker-v2-m3', device='cpu')
print("Tải models thành công!\n")

def check_relevance(q_major, q_keywords, doc_meta):
    """Hàm chấm điểm Relevant (1) hay Not Relevant (0)"""
    r_major = str(doc_meta.get("standard_major", "")).lower().strip()
    r_keywords = set([str(k).lower().strip() for k in doc.get("keywords", [])])
    
    major_match = (q_major != "" and q_major == r_major)
    kw_match = len(q_keywords.intersection(r_keywords)) > 0
    return 1 if (major_match or kw_match) else 0

def calculate_metrics(relevance_vector, k):
    """Tính Precision@K và MRR"""
    p_k = sum(relevance_vector[:k]) / k if k > 0 else 0
    mrr = 0.0
    for i, val in enumerate(relevance_vector[:k]):
        if val == 1:
            mrr = 1.0 / (i + 1)
            break
    return p_k, mrr

def run_ablation_study():
    # Lấy 15 bài test từ DB
    test_docs = list(meta_col.find(
        {"ai_tldr": {"$exists": True, "$ne": ""}},
        {"file_name": 1, "keywords": 1, "standard_major": 1, "ai_tldr": 1}
    ).limit(15))
    
    if not test_docs:
        print("Không tìm thấy dữ liệu test!")
        return

    # Biến lưu kết quả
    results_base = {'p3': [], 'mrr': [], 'latency': []}
    results_rerank = {'p3': [], 'mrr': [], 'latency': []}

    print(f"=== BẮT ĐẦU ABLATION STUDY TRÊN {len(test_docs)} TÀI LIỆU ===\n")

    for idx, doc in enumerate(test_docs):
        print(f"Đang test tài liệu {idx+1}/{len(test_docs)}...")
        query_text = doc['ai_tldr']
        q_major = str(doc.get("standard_major", "")).lower().strip()
        q_kws = set([str(k).lower().strip() for k in doc.get("keywords", [])])
        q_file = doc['file_name']

        # --- PHIÊN BẢN 1: KHÔNG DÙNG RE-RANKER (BASE SEARCH) ---
        start_time = time.time()
        query_vec = embed_model.encode(f"query: {query_text}", normalize_embeddings=True).tolist()
        
        # FIX: Thêm using="dense"
        base_hits = qdrant_client.query_points(
            collection_name=COLLECTION_NAME, 
            query=query_vec, 
            using="dense", 
            limit=4, 
            with_payload=True
        ).points
        
        latency_base = (time.time() - start_time) * 1000
        
        rel_base = []
        for hit in base_hits:
            r_file = hit.payload.get('metadata', {}).get('source_file', '')
            if r_file and r_file != q_file: # Bỏ qua chính nó
                r_meta = meta_col.find_one({"file_name": r_file})
                if r_meta:
                    rel_base.append(check_relevance(q_major, q_kws, r_meta))
                if len(rel_base) == 3: break
                
        p3_base, mrr_base = calculate_metrics(rel_base, 3)
        results_base['p3'].append(p3_base)
        results_base['mrr'].append(mrr_base)
        results_base['latency'].append(latency_base)

        # --- PHIÊN BẢN 2: CÓ DÙNG RE-RANKER ---
        start_time = time.time()
        
        # FIX: Thêm using="dense"
        broad_hits = qdrant_client.query_points(
            collection_name=COLLECTION_NAME, 
            query=query_vec, 
            using="dense", 
            limit=20, 
            with_payload=True
        ).points
        
        # Chạy qua Cross-Encoder
        pairs = [(query_text, hit.payload.get('content', '')) for hit in broad_hits]
        scores = reranker.predict(pairs)
        for i, hit in enumerate(broad_hits):
            hit.score = float(scores[i])
            
        # Sắp xếp lại và lấy Top 3
        reranked_hits = sorted(broad_hits, key=lambda x: x.score, reverse=True)
        latency_rerank = (time.time() - start_time) * 1000

        rel_rerank = []
        for hit in reranked_hits:
            r_file = hit.payload.get('metadata', {}).get('source_file', '')
            if r_file and r_file != q_file:
                r_meta = meta_col.find_one({"file_name": r_file})
                if r_meta:
                    rel_rerank.append(check_relevance(q_major, q_kws, r_meta))
                if len(rel_rerank) == 3: break
                
        p3_rerank, mrr_rerank = calculate_metrics(rel_rerank, 3)
        results_rerank['p3'].append(p3_rerank)
        results_rerank['mrr'].append(mrr_rerank)
        results_rerank['latency'].append(latency_rerank)

    # --- TỔNG HỢP VÀ IN BÁO CÁO ---
    print("\n" + "="*50)
    print("BÁO CÁO KẾT QUẢ ABLATION STUDY (RE-RANKER)")
    print("="*50)
    
    base_p3_avg = statistics.mean(results_base['p3']) if results_base['p3'] else 0
    base_mrr_avg = statistics.mean(results_base['mrr']) if results_base['mrr'] else 0
    base_lat_avg = statistics.mean(results_base['latency']) if results_base['latency'] else 0
    
    rr_p3_avg = statistics.mean(results_rerank['p3']) if results_rerank['p3'] else 0
    rr_mrr_avg = statistics.mean(results_rerank['mrr']) if results_rerank['mrr'] else 0
    rr_lat_avg = statistics.mean(results_rerank['latency']) if results_rerank['latency'] else 0

    print(f"1. PHIÊN BẢN BASE (Không Re-rank):")
    print(f"   - Precision@3 : {base_p3_avg:.4f}")
    print(f"   - MRR         : {base_mrr_avg:.4f}")
    print(f"   - Độ trễ (ms) : {base_lat_avg:.2f} ms")
    
    print(f"\n2. PHIÊN BẢN RERANKED (Có Re-rank):")
    p3_diff = ((rr_p3_avg - base_p3_avg) / base_p3_avg * 100) if base_p3_avg > 0 else 0
    mrr_diff = ((rr_mrr_avg - base_mrr_avg) / base_mrr_avg * 100) if base_mrr_avg > 0 else 0
    print(f"   - Precision@3 : {rr_p3_avg:.4f} (Cải thiện: {p3_diff:+.1f}%)")
    print(f"   - MRR         : {rr_mrr_avg:.4f} (Cải thiện: {mrr_diff:+.1f}%)")
    print(f"   - Độ trễ (ms) : {rr_lat_avg:.2f} ms (Chậm hơn: {rr_lat_avg - base_lat_avg:+.2f} ms)")
    print("="*50)

if __name__ == "__main__":
    run_ablation_study()