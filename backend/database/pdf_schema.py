"""
PDF 文档数据库表结构
"""
import sqlite3
import os

DB_PATH = os.getenv("DATABASE_PATH", "backend/crawler/forums.db")


def init_pdf_tables():
    """初始化 PDF 相关数据表"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # PDF 文档表
    c.execute('''CREATE TABLE IF NOT EXISTS pdf_documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT UNIQUE NOT NULL,
        original_name TEXT NOT NULL,
        file_path TEXT NOT NULL,
        file_size INTEGER,
        total_pages INTEGER,
        total_chunks INTEGER,
        upload_date TEXT DEFAULT CURRENT_TIMESTAMP,
        last_indexed TEXT,
        indexing_status TEXT DEFAULT 'pending',
        error_message TEXT,
        doc_type TEXT DEFAULT 'manual'
    )''')

    conn.commit()
    conn.close()
    print("PDF database tables initialized.")


def add_pdf_record(filename, original_name, file_path, file_size, doc_type='manual'):
    """添加 PDF 记录"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    try:
        c.execute('''INSERT INTO pdf_documents
            (filename, original_name, file_path, file_size, doc_type, indexing_status)
            VALUES (?, ?, ?, ?, ?, 'pending')''',
            (filename, original_name, file_path, file_size, doc_type))
        conn.commit()
        pdf_id = c.lastrowid
    except sqlite3.IntegrityError:
        # 文件已存在
        pdf_id = None
    finally:
        conn.close()

    return pdf_id


def update_pdf_status(pdf_id, status, total_pages=None, total_chunks=None, error_msg=None):
    """更新 PDF 处理状态"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    updates = ["indexing_status = ?"]
    values = [status]

    if total_pages is not None:
        updates.append("total_pages = ?")
        values.append(total_pages)

    if total_chunks is not None:
        updates.append("total_chunks = ?")
        values.append(total_chunks)

    if error_msg:
        updates.append("error_message = ?")
        values.append(error_msg)

    if status in ['completed', 'failed']:
        updates.append("last_indexed = ?")
        values.append(os.getenv('LAST_INDEXED', 'now'))

    values.append(pdf_id)

    c.execute(f'''UPDATE pdf_documents SET {', '.join(updates)} WHERE id = ?''', values)
    conn.commit()
    conn.close()


def get_all_pdfs():
    """获取所有 PDF 记录"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute('''SELECT id, filename, original_name, file_size,
                        total_pages, total_chunks, upload_date,
                        last_indexed, indexing_status, error_message
                 FROM pdf_documents
                 ORDER BY upload_date DESC''')
    rows = c.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_pdf_by_id(pdf_id):
    """根据 ID 获取 PDF"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute('SELECT * FROM pdf_documents WHERE id = ?', (pdf_id,))
    row = c.fetchone()
    conn.close()

    return dict(row) if row else None


def delete_pdf(pdf_id):
    """删除 PDF 记录"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 获取文件路径
    c.execute('SELECT file_path FROM pdf_documents WHERE id = ?', (pdf_id,))
    row = c.fetchone()
    file_path = row[0] if row else None

    # 删除数据库记录
    c.execute('DELETE FROM pdf_documents WHERE id = ?', (pdf_id,))
    conn.commit()
    conn.close()

    # 删除文件
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception as e:
            print(f"Error deleting file {file_path}: {e}")

    return True


if __name__ == "__main__":
    init_pdf_tables()
