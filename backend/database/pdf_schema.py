"""
PDF 文档数据库表结构 (MongoDB 版)
"""
import os
import datetime
from bson import ObjectId
import sys
import logging

# Add database module to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from mongo_client import get_db
except ImportError:
    # Fallback
    sys.path.append(os.path.join(os.getcwd(), 'backend', 'database'))
    from mongo_client import get_db

logger = logging.getLogger(__name__)

def init_pdf_tables():
    """初始化 PDF 相关数据表"""
    logger.info("Initializing PDF collections and indexes...")
    db = get_db()
    
    # PDF 文档表 indexes
    db.avid_pdfs.create_index("filename", unique=True)
    logger.info("PDF database collections initialized.")

def add_pdf_record(filename, original_name, file_path, file_size, doc_type='manual'):
    """添加 PDF 记录"""
    db = get_db()
    
    try:
        now = datetime.datetime.utcnow().isoformat()
        result = db.avid_pdfs.insert_one({
            "filename": filename,
            "original_name": original_name,
            "file_path": file_path,
            "file_size": file_size,
            "total_pages": 0,
            "total_chunks": 0,
            "upload_date": now,
            "last_indexed": None,
            "indexing_status": "pending",
            "error_message": None,
            "doc_type": doc_type
        })
        return str(result.inserted_id)
    except Exception as e:
        # 文件已存在等错误
        logger.error(f"Error adding pdf record: {e}")
        return None

def update_pdf_status(pdf_id, status, total_pages=None, total_chunks=None, error_msg=None):
    """更新 PDF 处理状态"""
    db = get_db()
    
    updates = {"indexing_status": status}
    
    if total_pages is not None:
        updates["total_pages"] = total_pages
        
    if total_chunks is not None:
        updates["total_chunks"] = total_chunks
        
    if error_msg:
        updates["error_message"] = error_msg
        
    if status in ['completed', 'failed']:
        updates["last_indexed"] = datetime.datetime.utcnow().isoformat()
        
    try:
        # Check if pdf_id is ObjectId or string. In our case we use ObjectId string.
        db.avid_pdfs.update_one({"_id": ObjectId(pdf_id)}, {"$set": updates})
    except Exception as e:
        logger.error(f"Error updating pdf status: {e}")

def get_all_pdfs():
    """获取所有 PDF 记录"""
    db = get_db()
    
    # Sort by upload_date DESC
    cursor = db.avid_pdfs.find().sort("upload_date", -1)
    
    pdfs = []
    for doc in cursor:
        doc["id"] = str(doc.pop("_id"))
        pdfs.append(doc)
        
    return pdfs

def get_pdf_by_id(pdf_id):
    """根据 ID 获取 PDF"""
    db = get_db()
    
    try:
        doc = db.avid_pdfs.find_one({"_id": ObjectId(pdf_id)})
        if doc:
            doc["id"] = str(doc.pop("_id"))
            return doc
    except Exception as e:
        logger.error(f"Error getting pdf: {e}")
        
    return None

def delete_pdf(pdf_id):
    """删除 PDF 记录"""
    db = get_db()
    
    try:
        doc = db.avid_pdfs.find_one({"_id": ObjectId(pdf_id)})
        file_path = doc.get("file_path") if doc else None
        
        db.avid_pdfs.delete_one({"_id": ObjectId(pdf_id)})
        
        # 删除文件
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                logger.error(f"Error deleting file {file_path}: {e}")
                
        return True
    except Exception as e:
        logger.error(f"Error deleting pdf record: {e}")
        return False

if __name__ == "__main__":
    init_pdf_tables()
