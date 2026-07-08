import chromadb
from chromadb.utils import embedding_functions
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add database module to path
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'database'))
try:
    from mongo_client import get_db
except ImportError:
    # Fallback
    sys.path.append(os.path.join(os.getcwd(), 'backend', 'database'))
    from mongo_client import get_db

CHROMA_PATH = os.getenv("CHROMA_PATH", "data/chroma_db")

def setup_chroma():
    print(f"Initializing ChromaDB at {CHROMA_PATH}...")
    if not os.path.exists(CHROMA_PATH):
        os.makedirs(CHROMA_PATH)
        
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    
    # Use a high quality, free local model
    # all-MiniLM-L6-v2 is the default for Chroma but explicit is better
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )
    
    collection = client.get_or_create_collection(
        name="avid_posts",
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"}
    )
    return collection

def fetch_threads_from_mongo():
    db = get_db()
    threads = []
    # Fetch original question content from threads that have not been vectorized yet
    docs = db.avid.find({"question_content": {"$exists": True, "$ne": ""}, "is_vectorized": {"$ne": True}})
    for doc in docs:
        threads.append({
            "id": doc.get("url"),
            "content": doc.get("question_content"),
            "author": "System",
            "post_date": doc.get("scraped_at") or doc.get("last_post_date"),
            "title": doc.get("title"),
            "url": doc.get("url")
        })
    return threads

def ingest_vectors():
    """向量化论坛帖子（增量式优化版）"""
    db = get_db()
    threads = fetch_threads_from_mongo()

    if not threads:
        print("No new threads to ingest.")
        return

    collection = setup_chroma()
    print(f"Found {len(threads)} new/updated threads to ingest.")

    ids = []
    documents = []
    metadatas = []
    urls_in_batch = []

    for thread in threads:
        content = thread['content']
        if not content or len(content.strip()) < 10:
            # Mark it as vectorized so we don't query it again
            db.avid.update_one({"url": thread['url']}, {"$set": {"is_vectorized": True}})
            continue

        # Combine title + content for better semantic search
        full_text = f"Title: {thread['title']}\nContent: {content}"

        import hashlib
        short_id = hashlib.md5(thread['id'].encode()).hexdigest()
        ids.append(f"thread_{short_id}")

        documents.append(full_text)
        metadatas.append({
            "source": "forum",
            "url": thread['url'],
            "author": thread['author'],
            "date": thread['post_date'],
            "title": thread['title']
        })
        urls_in_batch.append(thread['url'])

        # Batch ingest every 100 items
        if len(ids) >= 100:
            print(f"Upserting batch of {len(ids)}...")
            collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
            
            # Mark these threads as vectorized in Mongo
            db.avid.update_many(
                {"url": {"$in": urls_in_batch}},
                {"$set": {"is_vectorized": True}}
            )
            
            ids = []
            documents = []
            metadatas = []
            urls_in_batch = []

    # Final batch
    if ids:
        print(f"Upserting final batch of {len(ids)}...")
        collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
        
        # Mark final threads as vectorized in Mongo
        db.avid.update_many(
            {"url": {"$in": urls_in_batch}},
            {"$set": {"is_vectorized": True}}
        )

    print(f"Forum ingestion complete. Total items in collection: {collection.count()}")


def ingest_pdf_chunks(pdf_id: str, log_callback=None, stop_event=None):
    """
    向量化单个 PDF 文档（流式处理优化版 - 适用于大文档）

    Args:
        pdf_id: PDF 在数据库中的 ID
        log_callback: 日志回调函数
        stop_event: 停止事件用于取消任务
    """
    def log(msg):
        if log_callback:
            log_callback(msg)
        else:
            print(msg)

    try:
        from pdf_extractor_large import LargePDFExtractor
        from pdf_schema import get_pdf_by_id, update_pdf_status

        # 获取 PDF 信息
        pdf_record = get_pdf_by_id(pdf_id)
        if not pdf_record:
            log(f"❌ PDF ID {pdf_id} not found in database")
            return False

        log(f"📄 Processing: {pdf_record['filename']}")

        # 创建提取器
        extractor = LargePDFExtractor(pdf_record['file_path'])

        # 先获取PDF基本信息
        pdf_info = extractor.get_pdf_info()
        if not pdf_info:
            log(f"⚠️ Failed to read PDF info")
            return False

        total_pages = pdf_info['total_pages']
        file_size = pdf_info['file_size']
        log(f"  📊 File size: {file_size / 1024 / 1024:.2f} MB")
        log(f"  📊 Total pages: {total_pages}")

        # 初始化向量数据库和计数器
        collection = setup_chroma()
        total_chunks = 0
        batch_size = 100  # 增加批次大小到100，减少数据库IOPS和WAL文件增长
        start_time = None  # 用于计算速度
        vectorizing_start_page = 0  # 记录向量化起始页

        import gc


        # 定义进度回调函数
        def progress_callback(current_page: int, total_pg: int, message: str):
            """流式处理进度回调 - 发送结构化进度数据"""
            import time

            nonlocal start_time
            if start_time is None:
                start_time = time.time()

            # 计算处理速度和预估时间
            elapsed = time.time() - start_time
            speed = current_page / elapsed if elapsed > 0 else 0
            eta = (total_pg - current_page) / speed if speed > 0 else 0

            # 发送文本日志（兼容性）
            log(f"  ⏳ {message} (速度: {speed:.1f}页/秒, 剩余: {eta:.0f}秒)")

            # 发送结构化进度数据（新增）
            if log_callback:
                progress_data = {
                    "type": "progress",
                    "current": current_page,
                    "total": total_pg,
                    "chunks": total_chunks,
                    "speed": round(speed, 2),  # 保留2位小数更准确
                    "percentage": round((current_page / total_pg * 100), 1) if total_pg > 0 else 0,
                    "eta": round(eta)  # 预计剩余时间（秒）
                }
                log_callback(progress_data, type="progress")

        # 更新状态为处理中
        update_pdf_status(pdf_id, 'processing', total_pages=total_pages)

        log(f"  🔄 Starting text extraction (streaming mode)...")

        # 流式处理：边提取边向量化，内存优化
        try:
            failed_batches = []  # 记录失败的批次
            retry_count = 0
            max_retries = 2  # 最多重试2次

            for batch in extractor.extract_text_stream(
                batch_size=batch_size,
                progress_callback=progress_callback,
                stop_event=stop_event
            ):
                if stop_event and stop_event.is_set():
                    log("🛑 Vectorization cancelled by user")
                    break
                if not batch:
                    continue

                # 获取这批数据的页码范围
                first_page = batch[0]['metadata']['page']
                last_page = batch[-1]['metadata']['page']

                # 准备这批数据
                ids = [chunk['id'] for chunk in batch]
                documents = [chunk['content'] for chunk in batch]
                metadatas = [chunk['metadata'] for chunk in batch]

                try:
                    import time
                    vector_start = time.time()

                    # 向量化前提示
                    log(f"  🔍 Vectorizing {len(batch)} chunks from pages {first_page}-{last_page}...")

                    # 直接执行 upsert
                    collection.upsert(ids=ids, documents=documents, metadatas=metadatas)

                    vector_time = time.time() - vector_start
                    if vector_time > 30:
                        log(f"  ⚠️ Vectorizing took {vector_time:.1f}s (slow batch)")

                    # 更新计数
                    total_chunks += len(batch)

                    # 向量化完成提示
                    log(f"  ✅ Vectorized {len(batch)} chunks (pages {first_page}-{last_page})")

                    # 显式触发GC，防止大对象堆积
                    if total_chunks % 500 == 0:
                        gc.collect()

                except Exception as batch_error:
                    log(f"  ❌ Failed to vectorize batch {first_page}-{last_page}: {str(batch_error)[:100]}")
                    failed_batches.append((first_page, last_page, str(batch_error)[:100]))

                # 发送进度更新（使用最后处理的页码）
                progress_callback(last_page, total_pages, f"Processed {last_page}/{total_pages} pages")

            # 打印处理总结
            if failed_batches:
                log(f"⚠️ Processing completed with {len(failed_batches)} failed batches:")
                for first, last, error in failed_batches[:5]:
                    log(f"   - Pages {first}-{last}: {error}")
                if len(failed_batches) > 5:
                    log(f"   ... and {len(failed_batches) - 5} more")
            else:
                log(f"✅ All batches processed successfully")

        except Exception as stream_error:
            log(f"❌ Stream processing error: {stream_error}")
            update_pdf_status(pdf_id, 'failed', error_msg=str(stream_error))
            return False

        # 更新状态为完成（或部分完成）
        status = 'completed' if not failed_batches else 'partial'
        update_pdf_status(pdf_id, status,
                         total_pages=total_pages,
                         total_chunks=total_chunks)

        log(f"✅ PDF {pdf_record['filename']} indexing complete!")
        log(f"   📈 Total: {total_pages} pages, {total_chunks} chunks")
        return True

    except Exception as e:
        import traceback
        error_msg = str(e)
        log(f"❌ Error ingesting PDF: {error_msg}")
        log(traceback.format_exc())

        if pdf_id:
            from pdf_schema import update_pdf_status
            update_pdf_status(pdf_id, 'failed', error_msg=error_msg)

        return False


def delete_pdf_from_chroma(pdf_id: str):
    """从 ChromaDB 删除 PDF 的所有向量"""
    try:
        from pdf_schema import get_pdf_by_id

        pdf_record = get_pdf_by_id(pdf_id)
        if not pdf_record:
            return False

        collection = setup_chroma()

        # 查询该 PDF 的所有 chunk ID
        # ChromaDB 不支持直接的 where delete，需要先查询
        results = collection.get(
            where={"filename": pdf_record['filename']}
        )

        if results and results.get('ids'):
            collection.delete(ids=results['ids'])
            print(f"Deleted {len(results['ids'])} chunks from ChromaDB")
            return True

        return False

    except Exception as e:
        print(f"Error deleting from ChromaDB: {e}")
        return False

if __name__ == "__main__":
    ingest_vectors()
