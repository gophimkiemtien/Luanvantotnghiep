#Chạy sever Qdrant bằng Doker
docker run -p 6333:6333 -p 6334:6334 `
>>     -v D:\qdrant_storage:/qdrant/storage `
>>     qdrant/qdrant

#Offline 
python setup/extract.py
python setup/meta.py
python setup/chunk.py
python setup/embedding.py

#Chạy API
uvicorn main:app --port 8000

#Chạy APP
cd frontend
npm run dev
