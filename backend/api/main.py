from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
import sqlite3
import os
import sys
import threading
import logging
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from dotenv import load_dotenv
import shutil

# Add backend modules to path
sys.path.append(os.path.join(os.getcwd(), 'backend', 'database'))
sys.path.append(os.path.join(os.getcwd(), 'backend', 'ingest'))
sys.path.append(os.path.join(os.getcwd(), 'backend', 'crawler'))

# Load environment variables
load_dotenv()

# Configure Hugging Face mirror (for users in China or with network issues)
os.environ['HF_ENDPOINT'] = os.getenv('HF_ENDPOINT', 'https://hf-mirror.com')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("backend/api/api.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration from environment variables with defaults
DB_PATH = os.getenv("DATABASE_PATH", "backend/crawler/forums.db")
CHROMA_PATH = os.getenv("CHROMA_PATH", "data/chroma_db")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")


class SearchRequest(BaseModel):
    query: str
    limit: int = 10
    llm_provider: Optional[str] = "local"  # "local", "cloud", or "deepseek"


class SearchResponse(BaseModel):
    answer: str
    sources: List[dict]


class SettingsUpdate(BaseModel):
    source_url: str


class Source(BaseModel):
    id: int
    url: str
    display_name: str
    last_updated: str


class LLMConfig(BaseModel):
    provider: str  # "local" or "cloud"
    model: Optional[str] = None


from contextlib import asynccontextmanager

# Global Chroma Client
chroma_client = None
collection = None


def get_collection():
    global chroma_client, collection
    if collection is None:
        try:
            import chromadb
            from chromadb.utils import embedding_functions

            if not os.path.exists(CHROMA_PATH):
                os.makedirs(CHROMA_PATH)

            chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
            ef = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="all-MiniLM-L6-v2"
            )
            collection = chroma_client.get_or_create_collection(
                name="avid_posts",
                embedding_function=ef
            )
            logger.info("ChromaDB collection loaded.")
        except Exception as e:
            logger.error(f"Error loading ChromaDB: {e}", exc_info=True)
            return None
    return collection


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    get_collection()
    yield
    # Shutdown logic (if any)
    pass


app = FastAPI(title="Avid MC RAG API", lifespan=lifespan)

# Global exception handler to avoid exposing sensitive information
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Please check the logs for details."}
    )

# Add CORS middleware with configurable origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,  # Configured via environment variables
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/sources", response_model=List[Source])
def get_sources():
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id, url, display_name, last_updated FROM sources")
        rows = c.fetchall()
        conn.close()
        return [
            {
                "id": row[0],
                "url": row[1],
                "display_name": row[2],
                "last_updated": row[3] or "Never"
            } for row in rows
        ]
    except Exception as e:
        logger.error(f"Error fetching sources: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch sources from database")


@app.post("/sources")
def add_source(source: SettingsUpdate): # Overloading SettingsUpdate for URL
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        # Simple Logic: display_name = hostname or part of url
        display_name = source.source_url.split('/')[-1] or source.source_url
        c.execute("INSERT INTO sources (url, display_name, last_updated) VALUES (?, ?, ?)",
                 (source.source_url, display_name, ""))
        conn.commit()
        conn.close()
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Error adding source: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to add new source")


from fastapi.responses import StreamingResponse
import json
import asyncio
from task_manager import task_manager

import sys
import os
import sqlite3
import time
from datetime import datetime


def run_crawler_task(source_id: int):
    try:
        stop_event = task_manager.start_task(source_id)

        def log_cb(msg, type="log", data=None):
            task_manager.add_log(source_id, msg, type=type, data=data)

        log_file = os.path.join(os.getcwd(), "backend/crawler/crawler.log")

        with open(log_file, "a") as f:
            f.write(f"\n--- Targeted Crawl ID {source_id} Started at {datetime.now()} ---\n")
            f.flush()

            specific_urls = None
            try:
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("SELECT url FROM sources WHERE id = ?", (source_id,))
                row = c.fetchone()
                if row:
                    specific_urls = [row[0]]
                    log_cb(f"🎯 Targeted crawl requested for source ID {source_id}: {row[0]}")
                conn.close()
            except Exception as db_e:
                log_cb(f"⚠️ Error fetching targeted URL: {db_e}")

            # 1. Run Crawler
            try:
                sys.path.append(os.path.join(os.getcwd(), 'backend', 'crawler'))
                from forum_crawler import AvidCrawler
                log_cb("🚀 Background Crawler Started...")
                crawler = AvidCrawler(specific_urls=specific_urls)
                crawler.run(stop_event=stop_event, log_callback=log_cb)

                if stop_event.is_set():
                    log_cb("🛑 Task cancelled by user.", type="log")
                    task_manager.finish_task(source_id, status="cancelled")
                else:
                    log_cb("✅ Background Crawler Finished.")

                    # 2. Trigger Vector Ingestion
                    try:
                        sys.path.append(os.path.join(os.getcwd(), 'backend', 'ingest'))
                        from vector_store import ingest_vectors
                        log_cb("🚀 Background Vector Ingestion Started...")
                        ingest_vectors()
                        log_cb("✅ Background Vector Ingestion Finished.")
                        task_manager.finish_task(source_id, status="finished")
                    except Exception as ingest_err:
                        log_cb(f"❌ Ingestion Error: {ingest_err}")
                        task_manager.finish_task(source_id, status="error")
            except Exception as crawl_err:
                log_cb(f"❌ Crawler Error: {crawl_err}")
                task_manager.finish_task(source_id, status="error")

            # Allow some time for SSE to drain before cleanup
            time.sleep(10)
            task_manager.cleanup_task(source_id)

    except Exception as e:
        logger.error(f"Background Task Critical Error: {e}", exc_info=True)


@app.post("/crawler/run")
def trigger_crawler(source_id: int):
    if task_manager.is_task_running(source_id):
        return {"status": "error", "message": "Task already running for this source"}

    # Run in a separate thread to not block the API
    thread = threading.Thread(target=run_crawler_task, args=(source_id,))
    thread.start()
    return {"status": "started", "message": f"Crawler started for source {source_id}"}


@app.get("/crawler/logs/{source_id}")
async def stream_logs(source_id: int):
    queue = task_manager.get_log_queue(source_id)
    if not queue:
        async def empty_stream():
            yield "data: " + json.dumps({"type": "status", "message": "finished"}) + "\n\n"
        return StreamingResponse(empty_stream(), media_type="text/event-stream")

    async def log_generator():
        try:
            from queue import Empty
            while True:
                try:
                    # Non-blocking get from threading.Queue
                    msg = queue.get_nowait()
                    if msg is None:
                        yield "data: " + json.dumps({"type": "status", "message": "finished"}) + "\n\n"
                        break
                    yield "data: " + json.dumps(msg) + "\n\n"
                except Empty:
                    await asyncio.sleep(0.5)
        finally:
            task_manager.remove_log_queue(source_id, queue)

    return StreamingResponse(log_generator(), media_type="text/event-stream")


@app.post("/crawler/stop/{source_id}")
def stop_crawler(source_id: int):
    if task_manager.is_task_running(source_id):
        task_manager.stop_task(source_id)
        return {"status": "success", "message": "Cancellation signal sent"}
    return {"status": "error", "message": "No active task found for this source"}


@app.post("/search", response_model=SearchResponse)
def search(request: SearchRequest):
    col = get_collection()
    if not col:
        raise HTTPException(status_code=500, detail="Search engine not initialized (Model downloading?)")

    try:
        # 1. Vector Search
        results = col.query(
            query_texts=[request.query],
            n_results=request.limit
        )

        sources = []
        context_text = ""

        if results['documents']:
            # Flatten results
            docs = results['documents'][0]
            metas = results['metadatas'][0]

            for i, doc in enumerate(docs):
                meta = metas[i]

                # 根据来源类型构建不同的数据
                source_data = {
                    "title": meta.get('title', 'Unknown'),
                    "url": meta.get('url', '#'),
                    "snippet": doc[:200] + "..."
                }

                # 如果是 PDF 来源，添加额外元数据
                if meta.get('source') == 'pdf':
                    source_data['filename'] = meta.get('filename', '')
                    source_data['page'] = meta.get('page', 0)
                    # PDF 的 URL 设为 #
                    source_data['url'] = '#'

                sources.append(source_data)
                context_text += f"---\nTitle: {meta.get('title')}\nContent: {doc}\n"

        # 2. LLM Generation
        if context_text:
            try:
                from openai import OpenAI
                import os

                # Get LLM config from request or environment
                llm_provider = request.llm_provider or os.getenv("LLM_PROVIDER", "local")

                # Check if LLM is disabled
                if llm_provider == "none":
                    answer = ""
                elif llm_provider == "local":
                    # Use Ollama (local)
                    api_key = os.getenv("OPENAI_API_KEY", "ollama")
                    base_url = os.getenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
                    model = os.getenv("OPENAI_MODEL", "llama3")
                elif llm_provider == "deepseek":
                    # Use DeepSeek (via OpenAI-compatible API)
                    api_key = os.getenv("DEEPSEEK_API_KEY", "")
                    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
                    model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

                    if not api_key:
                        raise ValueError("DEEPSEEK_API_KEY not configured in environment variables")
                else:
                    # Use OpenAI (cloud)
                    api_key = os.getenv("OPENAI_API_KEY", "")
                    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
                    model = os.getenv("OPENAI_MODEL", "gpt-4")

                if llm_provider != "none":
                    if not api_key and llm_provider == "cloud":
                        raise ValueError("OpenAI API key not configured")

                    client = OpenAI(
                        api_key=api_key,
                        base_url=base_url,
                        timeout=600.0  # 10 minutes timeout for local models
                    )

                    system_prompt = """You are an expert Avid Media Composer support assistant.
                    Answer the user's question using ONLY the provided context snippets.
                    If the answer is not in the context, say "I couldn't find a specific answer in the knowledge base."
                    Keep the answer concise and professional.
                    Always answer in Chinese (中文)."""

                    user_prompt = f"Context:\n{context_text}\n\nQuestion: {request.query}\n\nPlease answer in Chinese."""

                    completion = client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        temperature=0.3
                    )

                    answer = completion.choices[0].message.content
            except Exception as llm_e:
                logger.error(f"LLM generation error: {llm_e}", exc_info=True)
                answer = "Found relevant threads but failed to generate AI summary. Please check the server logs."
        else:
            answer = "No relevant discussions found in the knowledge base."

        return {
            "answer": answer,
            "sources": sources
        }

    except Exception as e:
        logger.error(f"Search error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Search operation failed. Please check the server logs.")


@app.post("/search/stream")
async def search_stream(request: SearchRequest):
    """流式响应搜索端点，实时返回 LLM 生成的内容"""
    col = get_collection()
    if not col:
        raise HTTPException(status_code=500, detail="Search engine not initialized (Model downloading?)")

    try:
        # 1. Vector Search
        results = col.query(
            query_texts=[request.query],
            n_results=request.limit
        )

        sources = []
        context_text = ""

        if results['documents']:
            # Flatten results
            docs = results['documents'][0]
            metas = results['metadatas'][0]

            for i, doc in enumerate(docs):
                meta = metas[i]

                # 根据来源类型构建不同的数据
                source_data = {
                    "title": meta.get('title', 'Unknown'),
                    "url": meta.get('url', '#'),
                    "snippet": doc[:200] + "..."
                }

                # 如果是 PDF 来源，添加额外元数据
                if meta.get('source') == 'pdf':
                    source_data['filename'] = meta.get('filename', '')
                    source_data['page'] = meta.get('page', 0)
                    # PDF 的 URL 设为 #
                    source_data['url'] = '#'

                sources.append(source_data)
                context_text += f"---\nTitle: {meta.get('title')}\nContent: {doc}\n"

        # 2. LLM Generation with Streaming
        async def generate_response():
            try:
                # 先发送 sources
                yield f"data: {json.dumps({'type': 'sources', 'data': sources})}\n\n"
                # 添加一个空的 yield 来触发立即刷新
                yield f"data: {json.dumps({'type': 'ping'})}\n\n"

                if not context_text:
                    yield f"data: {json.dumps({'type': 'answer', 'content': 'No relevant discussions found in the knowledge base.'})}\n\n"
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
                    return

                from openai import AsyncOpenAI
                import os

                # Get LLM config from request or environment
                llm_provider = request.llm_provider or os.getenv("LLM_PROVIDER", "local")

                # Check if LLM is disabled
                if llm_provider == "none":
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
                    return

                if llm_provider == "local":
                    # Use Ollama (local)
                    api_key = os.getenv("OPENAI_API_KEY", "ollama")
                    base_url = os.getenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
                    model = os.getenv("OPENAI_MODEL", "llama3")
                elif llm_provider == "deepseek":
                    # Use DeepSeek (via OpenAI-compatible API)
                    api_key = os.getenv("DEEPSEEK_API_KEY", "")
                    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
                    model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

                    if not api_key:
                        raise ValueError("DEEPSEEK_API_KEY not configured in environment variables")
                else:
                    # Use OpenAI (cloud)
                    api_key = os.getenv("OPENAI_API_KEY", "")
                    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
                    model = os.getenv("OPENAI_MODEL", "gpt-4")

                if llm_provider != "none":
                    if not api_key and llm_provider == "cloud":
                        raise ValueError("OpenAI API key not configured")

                    client = AsyncOpenAI(
                        api_key=api_key,
                        base_url=base_url,
                        timeout=600.0  # 10 minutes timeout for local models
                    )

                    system_prompt = """You are an expert Avid Media Composer support assistant.
                    Answer the user's question using ONLY the provided context snippets.
                    If the answer is not in the context, say "I couldn't find a specific answer in the knowledge base."
                    Keep the answer concise and professional.
                    Always answer in Chinese (中文)."""

                    user_prompt = f"Context:\n{context_text}\n\nQuestion: {request.query}\n\nPlease answer in Chinese."

                    # 异步流式生成
                    stream = await client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        temperature=0.3,
                        stream=True
                    )

                    async for chunk in stream:
                        if chunk.choices[0].delta.content:
                            content = chunk.choices[0].delta.content
                            yield f"data: {json.dumps({'type': 'answer', 'content': content})}\n\n"

                    yield f"data: {json.dumps({'type': 'done'})}\n\n"

            except Exception as e:
                logger.error(f"Streaming error: {e}", exc_info=True)
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

        return StreamingResponse(generate_response(), media_type="text/event-stream")

    except Exception as e:
        logger.error(f"Search error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Search operation failed. Please check the server logs.")


# ==================== PDF Management Routes ====================

# Initialize PDF tables on startup
from pdf_schema import init_pdf_tables
init_pdf_tables()


@app.get("/pdf/list", response_model=List[dict])
def get_pdf_list():
    """获取所有 PDF 列表"""
    try:
        from pdf_schema import get_all_pdfs
        pdfs = get_all_pdfs()

        # 格式化响应
        result = []
        for pdf in pdfs:
            result.append({
                "id": pdf['id'],
                "filename": pdf['filename'],
                "original_name": pdf['original_name'],
                "file_size": pdf['file_size'],
                "total_pages": pdf['total_pages'],
                "total_chunks": pdf['total_chunks'],
                "upload_date": pdf['upload_date'],
                "last_indexed": pdf['last_indexed'],
                "status": pdf['indexing_status'],
                "error": pdf['error_message']
            })

        return result
    except Exception as e:
        logger.error(f"Error fetching PDF list: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch PDF list")


@app.post("/pdf/upload")
async def upload_pdf(file: UploadFile = File(...)):
    """上传 PDF 文件"""
    try:
        # 验证文件类型
        if not file.filename.endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Only PDF files are allowed")

        # 创建上传目录
        upload_dir = "data/docs/uploads"
        os.makedirs(upload_dir, exist_ok=True)

        # 保存文件
        file_path = os.path.join(upload_dir, file.filename)

        # 如果文件已存在，添加时间戳
        if os.path.exists(file_path):
            name, ext = os.path.splitext(file.filename)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = os.path.join(upload_dir, f"{name}_{timestamp}{ext}")

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        file_size = os.path.getsize(file_path)

        # 保存到数据库
        from pdf_schema import add_pdf_record
        pdf_id = add_pdf_record(
            filename=os.path.basename(file_path),
            original_name=file.filename,
            file_path=file_path,
            file_size=file_size
        )

        if pdf_id is None:
            # 文件已存在
            os.remove(file_path)
            raise HTTPException(status_code=400, detail="File already exists")

        logger.info(f"PDF uploaded: {file.filename} (ID: {pdf_id})")

        return {
            "status": "success",
            "message": "PDF uploaded successfully",
            "pdf_id": pdf_id,
            "filename": os.path.basename(file_path),
            "file_size": file_size
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading PDF: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to upload PDF")


@app.delete("/pdf/{pdf_id}")
def delete_pdf(pdf_id: int):
    """删除 PDF 文档"""
    try:
        from pdf_schema import delete_pdf, get_pdf_by_id
        from vector_store import delete_pdf_from_chroma

        # 获取 PDF 信息
        pdf = get_pdf_by_id(pdf_id)
        if not pdf:
            raise HTTPException(status_code=404, detail="PDF not found")

        # 从 ChromaDB 删除向量
        delete_pdf_from_chroma(pdf_id)

        # 从数据库和文件系统删除
        delete_pdf(pdf_id)

        logger.info(f"PDF deleted: ID {pdf_id}")

        return {"status": "success", "message": f"PDF {pdf['filename']} deleted"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting PDF: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete PDF")


@app.post("/pdf/{pdf_id}/index")
def index_pdf(pdf_id: int):
    """手动触发 PDF 索引（向量化）"""
    try:
        # 检查是否已有任务在运行
        if task_manager.is_task_running(pdf_id):
            return {"status": "error", "message": "Indexing already in progress"}

        # 在后台线程中运行索引任务
        def run_indexing():
            try:
                stop_event = task_manager.start_task(pdf_id)

                def log_cb(msg, type="log", data=None):
                    task_manager.add_log(pdf_id, msg, type=type, data=data)

                log_cb(f"🚀 Starting PDF indexing for ID {pdf_id}")

                from vector_store import ingest_pdf_chunks
                success = ingest_pdf_chunks(pdf_id, log_callback=log_cb)

                if stop_event.is_set():
                    log_cb("🛑 Indexing cancelled by user")
                    task_manager.finish_task(pdf_id, status="cancelled")
                elif success:
                    log_cb("✅ Indexing completed successfully")
                    task_manager.finish_task(pdf_id, status="finished")
                else:
                    log_cb("❌ Indexing failed")
                    task_manager.finish_task(pdf_id, status="error")

                time.sleep(10)
                task_manager.cleanup_task(pdf_id)

            except Exception as e:
                logger.error(f"Indexing task error: {e}", exc_info=True)
                task_manager.finish_task(pdf_id, status="error")

        thread = threading.Thread(target=run_indexing)
        thread.start()

        return {"status": "started", "message": f"Indexing started for PDF {pdf_id}"}

    except Exception as e:
        logger.error(f"Error starting indexing: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to start indexing")


@app.get("/pdf/indexing/progress/{pdf_id}")
async def stream_indexing_progress(pdf_id: int):
    """SSE: 流式传输索引进度"""
    queue = task_manager.get_log_queue(pdf_id)
    if not queue:
        async def empty_stream():
            yield "data: " + json.dumps({"type": "status", "message": "finished"}) + "\n\n"
        return StreamingResponse(empty_stream(), media_type="text/event-stream")

    async def log_generator():
        try:
            from queue import Empty
            while True:
                try:
                    msg = queue.get_nowait()
                    if msg is None:
                        yield "data: " + json.dumps({"type": "status", "message": "finished"}) + "\n\n"
                        break
                    yield "data: " + json.dumps(msg) + "\n\n"
                except Empty:
                    await asyncio.sleep(0.5)
        finally:
            task_manager.remove_log_queue(pdf_id, queue)

    return StreamingResponse(log_generator(), media_type="text/event-stream")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
