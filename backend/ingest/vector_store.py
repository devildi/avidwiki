import sqlite3
import chromadb
from chromadb.utils import embedding_functions
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DB_PATH = os.getenv("DATABASE_PATH", "backend/crawler/forums.db")
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

def fetch_threads_from_sqlite():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    # Fetch original question content from threads
    c.execute('''
        SELECT id, question_content as content, 'System' as author, scraped_at as post_date, title, url 
        FROM threads
    ''')
    threads = c.fetchall()
    conn.close()
    return threads

def ingest_vectors():
    """向量化论坛帖子（原有功能）"""
    collection = setup_chroma()
    threads = fetch_threads_from_sqlite()

    print(f"Found {len(threads)} threads to ingest.")

    ids = []
    documents = []
    metadatas = []

    for thread in threads:
        content = thread['content']
        if not content or len(content.strip()) < 10:
            continue

        # Combine title + content for better semantic search
        full_text = f"Title: {thread['title']}\nContent: {content}"

        # Use thread ID (which is the URL) for IDs
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

        # Batch ingest every 100 items
        if len(ids) >= 100:
            print(f"Upserting batch of {len(ids)}...")
            collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
            ids = []
            documents = []
            metadatas = []

    # Final batch
    if ids:
        print(f"Upserting final batch of {len(ids)}...")
        collection.upsert(ids=ids, documents=documents, metadatas=metadatas)

    print(f"Forum ingestion complete. Total items in collection: {collection.count()}")


def ingest_pdf_chunks(pdf_id: int, log_callback=None):
    """
    向量化单个 PDF 文档

    Args:
        pdf_id: PDF 在数据库中的 ID
        log_callback: 日志回调函数
    """
    def log(msg):
        if log_callback:
            log_callback(msg)
        else:
            print(msg)

    try:
        from pdf_extractor import PDFExtractor
        from database.pdf_schema import get_pdf_by_id, update_pdf_status

        # 获取 PDF 信息
        pdf_record = get_pdf_by_id(pdf_id)
        if not pdf_record:
            log(f"❌ PDF ID {pdf_id} not found in database")
            return False

        log(f"📄 Processing: {pdf_record['filename']}")

        # 提取文本和分块
        extractor = PDFExtractor(pdf_record['file_path'])
        chunks = extractor.extract_text()

        if not chunks:
            log(f"⚠️ No text extracted from PDF")
            update_pdf_status(pdf_id, 'failed', error_msg='No text extracted')
            return False

        # 更新状态为处理中
        update_pdf_status(pdf_id, 'processing',
                         total_pages=len(set(c['metadata']['page'] for c in chunks)),
                         total_chunks=len(chunks))

        # 向量化
        collection = setup_chroma()

        ids = [chunk['id'] for chunk in chunks]
        documents = [chunk['content'] for chunk in chunks]
        metadatas = [chunk['metadata'] for chunk in chunks]

        # 分批处理（每批 100 个）
        batch_size = 100
        for i in range(0, len(ids), batch_size):
            batch_ids = ids[i:i+batch_size]
            batch_docs = documents[i:i+batch_size]
            batch_metas = metadatas[i:i+batch_size]

            collection.upsert(ids=batch_ids, documents=batch_docs, metadatas=batch_metas)
            log(f"  ✅ Upserted batch {i//batch_size + 1}/{(len(ids)-1)//batch_size + 1}")

        # 更新状态为完成
        update_pdf_status(pdf_id, 'completed')
        log(f"✅ PDF {pdf_record['filename']} indexing complete ({len(chunks)} chunks)")
        return True

    except Exception as e:
        import traceback
        error_msg = str(e)
        log(f"❌ Error ingesting PDF: {error_msg}")
        log(traceback.format_exc())

        if pdf_id:
            from database.pdf_schema import update_pdf_status
            update_pdf_status(pdf_id, 'failed', error_msg=error_msg)

        return False


def delete_pdf_from_chroma(pdf_id: int):
    """从 ChromaDB 删除 PDF 的所有向量"""
    try:
        from database.pdf_schema import get_pdf_by_id

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
