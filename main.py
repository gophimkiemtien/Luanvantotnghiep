import os
import json
import re
import math
import traceback
from datetime import datetime
from typing import List, Optional
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pymongo import MongoClient
from qdrant_client import QdrantClient
from qdrant_client.http import models as rest
from sentence_transformers import SentenceTransformer, CrossEncoder
from fastembed import SparseTextEmbedding
from google import genai
from google.genai import types

load_dotenv()

app = FastAPI(title="CTU Scholar API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ---------- Clients & Models ----------
mongo_client = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017/"))
db = mongo_client["ctu"]
meta_col = db["thesis_metadata"]
chat_col = db["global_chat"]
users_col = db["users"]
gap_cache = db["research_gap_cache"]
trends_cache = db["trends_cache"]

qdrant_client = QdrantClient(os.getenv("QDRANT_HOST", "http://localhost:6333"))
COLLECTION_NAME = "thesis_ctu"
DOC_COLLECTION_NAME = "thesis_ctu_documents"

embed_model = SentenceTransformer('intfloat/multilingual-e5-large', device='cpu')
sparse_model = SparseTextEmbedding(model_name="Qdrant/bm25")
reranker = CrossEncoder('BAAI/bge-reranker-v2-m3', device='cpu')

ai_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

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

# ---------- Helper Functions ----------
class ContentFilter:
    @staticmethod
    def is_gibberish(text: str) -> bool:
        """Kiểm tra chuỗi rác (keyboard smash) như 'asdfgh'"""
        text = text.strip()
        if not text:
            return True

        # 1. Kiểm tra từ quá dài không có khoảng trắng
        words = text.split()
        if len(words) == 1 and len(text) > 15:
            return True

        # 2. Kiểm tra ký tự lặp lại quá nhiều (aaaaa, vvvvv)
        if re.search(r'(.)\1{4,}', text.lower()):
            return True

        # 3. Kiểm tra tỷ lệ nguyên âm (Vowel Ratio) cho tiếng Việt/Anh
        vowels = "aeiouyáàảãạâấầẩẫậăắằẳẵặéèẻẽẹêếềểễệíìỉĩịóòỏõọôốồổỗộơớờởỡợúùủũụưứừửữự"
        vowel_count = sum(1 for char in text.lower() if char in vowels)

        # Nếu chuỗi dài mà không có nguyên âm -> Rác
        if len(text) > 5 and vowel_count == 0:
            return True
        if len(text) > 10 and (vowel_count / len(text)) < 0.1:
            return True

        return False

def sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-x))

def clean_ai_json(text: str):
    clean = re.sub(r'```json|```', '', text).strip()
    return json.loads(clean)

# ---------- Pydantic Schemas ----------
class ParsedQuery(BaseModel):
    intent: str = Field(description="factual, reasoning, trend, recommend, greeting, nonsense, out_of_domain")
    year: Optional[int] = None
    major: Optional[str] = None
    rewritten_query: str

class ResearchGapResponse(BaseModel):
    limitations: str = Field(description="Phân tích các hạn chế của nghiên cứu")
    future_works: List[str] = Field(description="3 hướng nghiên cứu mới")

class QuestionRequest(BaseModel):
    query: str
    file_name: Optional[str] = None
    top_k: int = 5

class GlobalChatRequest(BaseModel):
    user_id: str
    message: str
    session_id: Optional[str] = None

class LoginRequest(BaseModel):
    username: str
    password: str

class NoveltyCheckRequest(BaseModel):
    abstract: str
    top_k: int = 5

class SemanticSearchRequest(BaseModel):
    query: str
    major: Optional[str] = None
    year: Optional[int] = None
    limit: int = 50

# ---------- Core RAG Functions ----------
def parse_query_with_llm(query: str) -> ParsedQuery:
    try:
        prompt = f"""Phân tích câu hỏi người dùng cho hệ thống CTU Scholar: "{query}"
        Trả JSON: {{
            "intent": "factual|reasoning|trend|recommend|greeting|nonsense|out_of_domain", 
            "year": số hoặc null, 
            "major": string hoặc null, 
            "rewritten_query": "string"
        }}
        
        Lưu ý: 
        - nonsense: Câu hỏi vô nghĩa, gõ phím bậy, hoặc nội dung nhảm nhí.
        - out_of_domain: Câu hỏi không liên quan đến học thuật/luận văn (vd: hỏi giá vàng, thời tiết)."""
        
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash', contents=prompt,
            config=types.GenerateContentConfig(temperature=0.0, response_mime_type="application/json")
        )
        return ParsedQuery.model_validate_json(response.text)
    except Exception as e:
        print(f"Lỗi Parse query: {e}")
        return ParsedQuery(intent="factual", year=None, major=None, rewritten_query=query)

def hybrid_search_with_rerank(query: str, filter_cond: Optional[rest.Filter] = None,
                              top_k: int = 20, final_n: int = 5, threshold: float = 0.6):
    dense_vec = embed_model.encode(f"query: {query}", normalize_embeddings=True).tolist()
    sparse_vec = list(sparse_model.embed([query]))[0]
    sparse_qdrant = rest.SparseVector(indices=sparse_vec.indices.tolist(), values=sparse_vec.values.tolist())

    try:
        fusion_results = qdrant_client.query_points(
            collection_name=COLLECTION_NAME,
            prefetch=[
                rest.Prefetch(query=dense_vec, using="dense", limit=top_k),
                rest.Prefetch(query=sparse_qdrant, using="sparse", limit=top_k),
            ],
            query=rest.FusionQuery(fusion=rest.Fusion.RRF),
            query_filter=filter_cond,
            with_payload=True,
            limit=top_k
        ).points
    except Exception as e:
        print(f"Lỗi Qdrant RRF: {e}")
        return []

    if not fusion_results: return []

    pairs = [(query, hit.payload.get('content', '')) for hit in fusion_results]
    rerank_scores = reranker.predict(pairs)
    for i, hit in enumerate(fusion_results):
        hit.score = sigmoid(float(rerank_scores[i]))

    filtered = [hit for hit in fusion_results if hit.score >= threshold]
    print(f"🔍 Rerank: {len(filtered)}/{len(fusion_results)} chunks đạt ngưỡng {threshold}")
    return sorted(filtered, key=lambda x: x.score, reverse=True)[:final_n]

# ---------- API Endpoints ----------
@app.post("/ask")
async def ask_thesis(request: QuestionRequest):
    try:
        clean_query = request.query.strip()

        # --- 1. Lớp lọc Heuristic (không tốn phí AI) ---
        if ContentFilter.is_gibberish(clean_query):
            return {
                "answer": "Hệ thống không nhận diện được câu hỏi của bạn. Vui lòng nhập một câu hỏi rõ ràng về nội dung luận văn hoặc nghiên cứu.",
                "results": [],
                "sources": []
            }

        # Chào hỏi nhanh
        quick_greetings = ["chào", "xin chào", "hello", "hi", "alo", "ê"]
        if clean_query.lower() in quick_greetings:
            return {
                "answer": "Chào bạn! Tôi là trợ lý CTU Scholar. Hãy đặt câu hỏi về luận văn mà bạn quan tâm nhé.",
                "results": [],
                "sources": []
            }

        # --- 2. Phân tích intent bằng LLM ---
        parsed = parse_query_with_llm(clean_query)

        if parsed.intent == "nonsense":
            return {
                "answer": "Câu hỏi của bạn có vẻ không rõ nghĩa. Hãy thử lại với một câu hỏi học thuật cụ thể.",
                "results": [],
                "sources": []
            }

        if parsed.intent == "out_of_domain":
            return {
                "answer": "Xin lỗi, tôi chỉ hỗ trợ giải đáp các câu hỏi liên quan đến nội dung học thuật và luận văn trong hệ thống.",
                "results": [],
                "sources": []
            }

        if parsed.intent == "greeting":
            return {
                "answer": "Chào bạn! Tôi là trợ lý CTU Scholar. Tôi có thể giúp gì cho bạn trong việc tìm hiểu luận văn này?",
                "results": [],
                "sources": []
            }

        # --- 3. Xử lý RAG cho các intent học thuật ---
        must, must_not = [], []
        if parsed.major and parsed.major in STANDARD_MAJORS:
            must.append(rest.FieldCondition(key="metadata.standard_major", match=rest.MatchValue(value=parsed.major)))
        if parsed.year:
            must.append(rest.FieldCondition(key="metadata.year", match=rest.MatchValue(value=parsed.year)))

        if parsed.intent == "recommend":
            if request.file_name:
                must_not.append(rest.FieldCondition(key="metadata.source_file", match=rest.MatchValue(value=request.file_name)))
        else:
            if request.file_name:
                must.append(rest.FieldCondition(key="metadata.source_file", match=rest.MatchValue(value=request.file_name)))

        filter_cond = rest.Filter(must=must if must else None, must_not=must_not if must_not else None)
        hits = hybrid_search_with_rerank(parsed.rewritten_query, filter_cond, top_k=20, final_n=request.top_k, threshold=0.6)

        if not hits:
            return {
                "answer": "Không tìm thấy thông tin liên quan đến câu hỏi của bạn trong hệ thống.",
                "results": [],
                "sources": []
            }

        # Thu thập metadata của các luận văn liên quan
        fnames = []
        seen_fnames = set()
        for h in hits:
            fn = h.payload.get('metadata', {}).get('source_file', '')
            if fn and fn not in seen_fnames:
                seen_fnames.add(fn)
                fnames.append(fn)

        results_meta = []
        for fn in fnames:
            doc = meta_col.find_one({"file_name": fn}, {"_id": 0})
            if doc:
                results_meta.append(doc)

        context = "\n---\n".join([h.payload.get('content', '') for h in hits])

        prompt = f"""Bạn là CTU Scholar, một trợ lý học thuật chuyên nghiệp. Hãy trả lời câu hỏi dựa trên Ngữ cảnh được cung cấp.

Ngữ cảnh:
{context}

Câu hỏi: {clean_query}

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

        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.0)
        )

        return {
            "answer": response.text,
            "results": results_meta,
            "sources": fnames
        }

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Lỗi server: {str(e)}")

@app.post("/global-chat")
async def global_chat(request: GlobalChatRequest):
    try:
        sid = request.session_id or datetime.now().strftime("%Y%m%d%H%M%S")
        clean_msg = request.message.strip()

        # --- 1. Lớp lọc Heuristic (Không tốn phí AI) ---
        if ContentFilter.is_gibberish(clean_msg):
            answer = "Hệ thống không nhận diện được nội dung bạn nhập. Vui lòng đặt câu hỏi rõ ràng về luận văn hoặc nghiên cứu nhé!"
            return {"answer": answer, "session_id": sid, "sources": []}

        # Lọc chào hỏi nhanh
        quick_greetings = ["chào", "xin chào", "hello", "hi", "alo", "ê"]
        if clean_msg.lower() in quick_greetings:
            answer = "Chào bạn! Tôi là trợ lý CTU Scholar. Tôi có thể giúp gì cho bạn trong việc tìm kiếm luận văn?"
            return {"answer": answer, "session_id": sid, "sources": []}

        # --- 2. Lớp lọc AI Intent ---
        parsed = parse_query_with_llm(clean_msg)
        
        if parsed.intent == "nonsense":
            return {"answer": "Câu hỏi của bạn có vẻ không rõ ràng. Hãy thử hỏi về đề tài nghiên cứu hoặc chuyên ngành tại CTU nhé!", "session_id": sid, "sources": []}
        
        if parsed.intent == "out_of_domain":
            return {"answer": "Xin lỗi, tôi chỉ hỗ trợ các thông tin liên quan đến học thuật và kho luận văn của trường.", "session_id": sid, "sources": []}

        # --- 3. Xử lý RAG chính ---
        history = list(chat_col.find({"session_id": sid}).sort("timestamp", -1).limit(10))
        history.reverse()
        context_history = "\n".join([f"User: {h['user_message']}\nBot: {h['bot_response']}" for h in history if 'user_message' in h])

        must = []
        if parsed.major and parsed.major in STANDARD_MAJORS:
            must.append(rest.FieldCondition(key="metadata.standard_major", match=rest.MatchValue(value=parsed.major)))
        if parsed.year:
            must.append(rest.FieldCondition(key="metadata.year", match=rest.MatchValue(value=parsed.year)))
        
        filter_cond = rest.Filter(must=must) if must else None
        hits = hybrid_search_with_rerank(parsed.rewritten_query, filter_cond, top_k=20, final_n=4, threshold=0.6)
        
        if not hits:
            answer = "Rất tiếc, tôi không tìm thấy thông tin phù hợp trong kho luận văn."
            sources = []
        else:
            context = "\n".join([h.payload.get('content', '') for h in hits])
            sources = list(set([h.payload.get('metadata', {}).get('source_file', 'N/A') for h in hits]))
            prompt = f"Bạn là CTU Scholar. Lịch sử: {context_history}\nNgữ cảnh: {context}\nCâu hỏi: {clean_msg}\nTrả lời chính xác, trích dẫn nguồn."
            resp = ai_client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
            answer = resp.text

        # Lưu lịch sử
        chat_col.insert_one({
            "user_id": request.user_id, "session_id": sid, "user_message": request.message,
            "bot_response": answer, "intent": parsed.intent, "sources": sources, "timestamp": datetime.utcnow()
        })
        return {"answer": answer, "session_id": sid, "sources": sources}
        
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Lỗi: {str(e)}")

@app.post("/semantic-search")
async def semantic_search(request: SemanticSearchRequest):
    try:
        must = []
        if request.major and request.major in STANDARD_MAJORS:
            must.append(rest.FieldCondition(key="standard_major", match=rest.MatchValue(value=request.major)))
        if request.year:
            must.append(rest.FieldCondition(key="year", match=rest.MatchValue(value=request.year)))
        filter_cond = rest.Filter(must=must) if must else None

        dense_vec = embed_model.encode(f"query: {request.query}", normalize_embeddings=True).tolist()
        search_results = qdrant_client.query_points(
            collection_name=DOC_COLLECTION_NAME, query=dense_vec, query_filter=filter_cond, with_payload=True, limit=request.limit 
        ).points

        results, MIN_SCORE = [], 0.8
        for hit in search_results:
            if hit.score < MIN_SCORE: continue
            doc_info = hit.payload.copy() if hit.payload else {}
            doc_info["score"] = round(hit.score, 4)
            fn = doc_info.get("file_name", "")
            if fn:
                base_name = fn.rsplit('.', 1)[0]
                db_doc = meta_col.find_one({"file_name": {"$regex": f"^{base_name}"}}, {"_id": 0})
                if db_doc: doc_info.update(db_doc)
            results.append(doc_info)
        return {"total_found": len(results), "results": results}
    except Exception as e:
        raise HTTPException(500, f"Lỗi: {str(e)}")

@app.post("/login")
async def login(request: LoginRequest):
    user = users_col.find_one({"username": request.username, "password": request.password})
    if not user: raise HTTPException(401, "Sai tên đăng nhập hoặc mật khẩu")
    return {"id": user["username"], "username": user.get("full_name", user["username"]), "role": user.get("role", "user")}

@app.get("/thesis/{file_name}")
async def get_thesis_by_filename(file_name: str):
    doc = meta_col.find_one({"file_name": file_name}, {"_id": 0})
    if not doc: raise HTTPException(404, "Không tìm thấy luận văn")
    return doc

@app.get("/recommend/{file_name}")
async def get_recommend(file_name: str):
    doc = meta_col.find_one({"file_name": file_name})
    if not doc or not doc.get('ai_tldr'): return []
    query_vec = embed_model.encode(f"query: {doc['ai_tldr']}", normalize_embeddings=True).tolist()
    hits = qdrant_client.query_points(collection_name=DOC_COLLECTION_NAME, query=query_vec, limit=20, with_payload=True).points
    unique = {}
    for h in hits:
        fname = h.payload.get('file_name')
        if fname and fname != file_name and fname not in unique: unique[fname] = h.score
    top_fnames = sorted(unique.items(), key=lambda x: x[1], reverse=True)[:5]
    return [meta_col.find_one({"file_name": fn}, {"_id":0, "title":1, "author":1, "year":1, "file_name":1}) for fn, _ in top_fnames if meta_col.find_one({"file_name": fn})]

@app.get("/research-gap/{file_name}")
async def get_research_gap(file_name: str):
    cached = gap_cache.find_one({"file_name": file_name})
    if cached and (datetime.utcnow() - cached["timestamp"]).total_seconds() < 86400:
        return ResearchGapResponse.model_validate_json(cached["analysis"])
    doc = meta_col.find_one({"file_name": file_name})
    if not doc or not doc.get('ai_tldr'): return ResearchGapResponse(limitations="Không có dữ liệu", future_works=[])
    prompt = f"Phân tích khoảng trống từ tóm tắt: {doc['ai_tldr']}\nTrả JSON: {{'limitations': '...', 'future_works': ['...']}}"
    response = ai_client.models.generate_content(model='gemini-2.5-flash', contents=prompt, config=types.GenerateContentConfig(temperature=0.0, response_mime_type="application/json", response_schema=ResearchGapResponse))
    gap_cache.update_one({"file_name": file_name}, {"$set": {"analysis": response.parsed.model_dump_json(), "timestamp": datetime.utcnow()}}, upsert=True)
    return response.parsed

@app.post("/check-novelty")
async def check_novelty(request: NoveltyCheckRequest):
    hits = hybrid_search_with_rerank(request.abstract, top_k=request.top_k, final_n=request.top_k, threshold=0.6)
    similar = []
    seen_fnames = set()
    for h in hits:
        fname = h.payload.get('metadata', {}).get('source_file')
        if fname and fname not in seen_fnames:
            seen_fnames.add(fname)
            doc = meta_col.find_one({"file_name": fname}, {"_id":0, "title":1, "author":1, "year":1})
            if doc: similar.append({**doc, "score": h.score})
    return {"is_novel": len(similar) == 0, "similar_theses": similar}

@app.get("/chat-sessions/{user_id}")
async def get_chat_sessions(user_id: str):
    pipeline = [{"$match": {"user_id": user_id}}, {"$sort": {"timestamp": 1}}, {"$group": {"_id": "$session_id", "title": {"$first": "$user_message"}, "last_active": {"$last": "$timestamp"}}}, {"$sort": {"last_active": -1}}]
    return [{"session_id": s["_id"], "title": s["title"][:50]} for s in chat_col.aggregate(pipeline)]

@app.get("/chat-history/{session_id}")
async def get_chat_history(session_id: str):
    history = list(chat_col.find({"session_id": session_id}).sort("timestamp", 1))
    formatted = []
    for h in history:
        if "user_message" in h: formatted.append({"role": "user", "text": h["user_message"]})
        if "bot_response" in h: formatted.append({"role": "bot", "text": h["bot_response"], "sources": h.get("sources", [])})
    return formatted

def get_cached(key: str, ttl_seconds=300):
    doc = trends_cache.find_one({"key": key})
    return doc["data"] if doc and (datetime.utcnow() - doc["timestamp"]).total_seconds() < ttl_seconds else None

def set_cache(key: str, data):
    trends_cache.update_one({"key": key}, {"$set": {"data": data, "timestamp": datetime.utcnow()}}, upsert=True)

@app.get("/trends")
async def get_trends():
    if cached := get_cached("trends"): return cached
    data = [{"year": str(r["_id"]), "count": r["count"]} for r in meta_col.aggregate([{"$match": {"year": {"$ne": None}}}, {"$group": {"_id": "$year", "count": {"$sum": 1}}}, {"$sort": {"_id": 1}}])]
    set_cache("trends", data); return data

@app.get("/keyword-growth")
async def get_keyword_growth():
    if cached := get_cached("keyword_growth", 600): return cached
    top = [k["_id"] for k in meta_col.aggregate([{"$unwind": "$keywords"}, {"$group": {"_id": "$keywords", "count": {"$sum": 1}}}, {"$sort": {"count": -1}}, {"$limit": 5}])]
    growth = list(meta_col.aggregate([{"$unwind": "$keywords"}, {"$match": {"keywords": {"$in": top}, "year": {"$ne": None}}}, {"$group": {"_id": {"year": "$year", "kw": "$keywords"}, "total": {"$sum": 1}}}, {"$sort": {"_id.year": 1}}]))
    years = sorted(set(d["_id"]["year"] for d in growth))
    chart = []
    for y in years:
        pt = {"year": str(y)}
        for kw in top: pt[kw] = next((d["total"] for d in growth if d["_id"]["year"] == y and d["_id"]["kw"] == kw), 0)
        chart.append(pt)
    result = {"chart_data": chart, "keywords": top}; set_cache("keyword_growth", result); return result

@app.get("/trend-insights")
async def get_trend_insights():
    if cached := get_cached("trend_insights", 3600): return cached
    top_kws = [k["_id"] for k in meta_col.aggregate([{"$match": {"year": {"$gte": 2023}}}, {"$unwind": "$keywords"}, {"$group": {"_id": "$keywords", "count": {"$sum": 1}}}, {"$sort": {"count": -1}}, {"$limit": 10}])]
    prompt = f"Từ khóa hot: {', '.join(top_kws)}. Phân tích hướng nghiên cứu ĐHCT và gợi ý 3 đề tài mới. Trả JSON: {{'analysis':'...','suggestions':['...']}}"
    resp = ai_client.models.generate_content(model='gemini-2.5-flash', contents=prompt, config=types.GenerateContentConfig(temperature=0.0))
    data = clean_ai_json(resp.text); set_cache("trend_insights", data); return data

@app.get("/topic/{topic_name}")
async def get_topic_info(topic_name: str):
    if existing := db["topics"].find_one({"topic_name": topic_name}, {"_id": 0}): return existing
    prompt = f"Giải nghĩa '{topic_name}' trong học thuật. JSON: {{'topic_name':'{topic_name}', 'definition':'...', 'related_topics':[]}}"
    resp = ai_client.models.generate_content(model='gemini-2.5-flash', contents=prompt, config=types.GenerateContentConfig(temperature=0.0))
    data = clean_ai_json(resp.text); db["topics"].insert_one(data.copy()); return data

@app.get("/evaluate/recommend-final")
async def evaluate_recommendations_final(k: int = 20, limit: int = 100):
    try:
        # Lấy danh sách luận văn làm tập test
        test_docs = list(meta_col.find(
            {"ai_tldr": {"$exists": True, "$ne": ""}},
            {"_id": 0, "file_name": 1, "keywords": 1, "standard_major": 1, "ai_tldr": 1}
        ).limit(limit))

        if not test_docs: 
            return {"status": "error", "message": "Không tìm thấy dữ liệu trong MongoDB"}

        # Lấy toàn bộ metadata để làm lookup table
        full_meta = list(meta_col.find({}, {"file_name": 1, "keywords": 1, "standard_major": 1, "_id": 0}))
        
        db_lookup = {}
        for doc in full_meta:
            fn = doc.get("file_name")
            if fn:
                pure_id = fn.split('.')[0].strip() 
                kws = set([str(kw).lower().strip() for kw in doc.get("keywords", [])])
                major = str(doc.get("standard_major", "")).lower().strip()
                db_lookup[pure_id] = {"keywords": kws, "major": major, "original_fn": fn}

        precision_scores = []
        mrr_at_k_scores = [] # Đổi tên biến cho rõ ràng là MRR@K
        ndcg_scores = []
        evaluation_logs = []

        def calculate_dcg(scores):
            return sum(score / math.log2(i + 2) for i, score in enumerate(scores))

        for query_doc in test_docs:
            q_fn = query_doc["file_name"]
            q_id_pure = q_fn.split('.')[0].strip()
            q_kws = set([str(kw).lower().strip() for kw in query_doc.get("keywords", [])])
            q_major = str(query_doc.get("standard_major", "")).lower().strip()

            query_vec = embed_model.encode(f"query: {query_doc['ai_tldr']}", normalize_embeddings=True).tolist()
            
            search_results = qdrant_client.query_points(
                collection_name=DOC_COLLECTION_NAME, query=query_vec, limit=k + 1, with_payload=True
            ).points

            recommended_ids = []
            for hit in search_results:
                r_fn = hit.payload.get('file_name')
                if r_fn:
                    r_id_pure = r_fn.split('.')[0].strip()
                    if r_id_pure != q_id_pure:
                        recommended_ids.append(r_id_pure)
                if len(recommended_ids) == k: break

            relevance_scores = [] 
            binary_relevance = [] 
            detail_matches = []

            for r_id in recommended_ids:
                r_meta = db_lookup.get(r_id)
                if r_meta:
                    kw_match_count = len(q_kws.intersection(r_meta["keywords"]))
                    major_match = (q_major != "" and q_major == r_meta["major"])
                    
                    if kw_match_count > 0 and major_match:
                        rel_score = 3
                        reason = f"Khớp Major + {kw_match_count} Keywords"
                    elif kw_match_count > 0:
                        rel_score = 2
                        reason = f"Chỉ khớp {kw_match_count} Keywords"
                    elif major_match:
                        rel_score = 1
                        reason = "Chỉ khớp Major"
                    else:
                        rel_score = 0
                        reason = "Không khớp thông tin nào"

                    is_rel_binary = 1 if rel_score > 0 else 0
                    
                    relevance_scores.append(rel_score)
                    binary_relevance.append(is_rel_binary)
                    detail_matches.append({
                        "file_id": r_id, 
                        "relevance_score": rel_score,
                        "reason": reason
                    })
                else:
                    relevance_scores.append(0)
                    binary_relevance.append(0)
                    detail_matches.append({"file_id": r_id, "relevance_score": 0, "reason": "Không tìm thấy trong DB"})

            if relevance_scores:
                # 1. Tính Precision@K
                p_k = sum(binary_relevance) / k
                precision_scores.append(p_k)
                
                # 2. Tính MRR@K (Tìm hạng đúng đầu tiên trong K kết quả)
                rr_at_k = 0.0
                for i, val in enumerate(binary_relevance):
                    if val == 1:
                        rr_at_k = 1.0 / (i + 1)
                        break # Chỉ lấy kết quả đúng đầu tiên rồi dừng lại
                mrr_at_k_scores.append(rr_at_k)

                # 3. Tính NDCG@K
                actual_dcg = calculate_dcg(relevance_scores)
                ideal_scores = sorted(relevance_scores, reverse=True)
                ideal_dcg = calculate_dcg(ideal_scores)
                ndcg_at_k = (actual_dcg / ideal_dcg) if ideal_dcg > 0 else 0.0
                ndcg_scores.append(ndcg_at_k)

                evaluation_logs.append({
                    "query_file": q_fn, 
                    "query_major": q_major, 
                    "query_keywords": list(q_kws),
                    "results": detail_matches, 
                    "metrics": {
                        "precision_at_k": round(p_k, 2),
                        "mrr_at_k": round(rr_at_k, 2), # Cập nhật Key JSON
                        "ndcg_at_k": round(ndcg_at_k, 2)
                    }
                })

        num_tests = len(precision_scores)
        avg_precision = sum(precision_scores) / num_tests if num_tests > 0 else 0
        avg_mrr_at_k = sum(mrr_at_k_scores) / num_tests if num_tests > 0 else 0
        avg_ndcg = sum(ndcg_scores) / num_tests if num_tests > 0 else 0

        return {
            "status": "success", 
            "summary": {
                "total_evaluated": num_tests, 
                f"mean_precision_at_{k}": round(avg_precision, 4), 
                f"mean_mrr_at_{k}": round(avg_mrr_at_k, 4), # Cập nhật Key JSON
                f"mean_ndcg_at_{k}": round(avg_ndcg, 4)
            }, 
            "evaluation_details": evaluation_logs
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Lỗi thực nghiệm: {str(e)}")
    
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)