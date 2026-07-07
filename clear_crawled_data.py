import os
import sys
import sqlite3
from pymongo import MongoClient
import chromadb
from dotenv import load_dotenv

# Load env
load_dotenv()

def clear_data():
    print("🧹 开始清空爬虫数据...")
    print("=" * 60)

    # 1. 清空 MongoDB 中的已爬取数据 (avid 集合)
    try:
        MONGO_URI = os.getenv("MONGO_URI", "mongodb://woody:41538bc6dd@127.0.0.1/davinci")
        client = MongoClient(MONGO_URI)
        db = client.get_database()
        
        # 获取原始计数
        crawled_count = db.avid.count_documents({})
        print(f"🔹 MongoDB (avid 集合): 发现 {crawled_count} 条数据")
        
        if crawled_count > 0:
            db.avid.delete_many({})
            print("   ✅ 已成功清空 MongoDB 里的已爬取数据")
            
        # 重置 avid_sources 爬虫状态
        db.avid_sources.update_many(
            {},
            {"$set": {"last_updated": "", "current_page": 1}}
        )
        print("   ✅ 已成功重置 MongoDB 中的所有爬虫源状态 (last_updated='', current_page=1)")
        
    except Exception as e:
        print(f"❌ 清空 MongoDB 数据失败: {e}")

    # 2. 清空 SQLite 中的已爬取数据 (threads 表)
    DB_PATH = "backend/crawler/forums.db"
    if os.path.exists(DB_PATH):
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # 获取原始计数
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [t[0] for t in cursor.fetchall()]
            
            if "threads" in tables:
                cursor.execute("SELECT COUNT(*) FROM threads")
                count = cursor.fetchone()[0]
                print(f"\n🔹 SQLite (threads 表): 发现 {count} 条数据")
                
                if count > 0:
                    cursor.execute("DELETE FROM threads")
                    conn.commit()
                    print("   ✅ 已成功清空 SQLite 中的已爬取数据")
            else:
                print("\n🔹 SQLite: 数据库中不存在 threads 表")
                
            if "sources" in tables:
                # 重置 sources 表的最后更新时间
                cursor.execute("UPDATE sources SET last_updated = ''")
                conn.commit()
                print("   ✅ 已成功重置 SQLite 中的所有数据源状态")
            
            conn.close()
        except Exception as e:
            print(f"❌ 清空 SQLite 数据失败: {e}")
    else:
        print(f"\n🔹 SQLite: 数据库文件不存在于 {DB_PATH}，跳过")

    # 3. 从 ChromaDB 中删除对应的向量
    CHROMA_PATH = os.getenv("CHROMA_PATH", "data/chroma_db")
    if os.path.exists(CHROMA_PATH):
        try:
            chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
            # 获取已存在的集合
            try:
                collection = chroma_client.get_collection("avid_posts")
                # 查询 forum 来源的向量数
                results = collection.get(where={"source": "forum"})
                forum_ids = results.get("ids", [])
                print(f"\n🔹 ChromaDB (avid_posts 集合): 发现 {len(forum_ids)} 个论坛相关向量")
                
                if len(forum_ids) > 0:
                    # 分批删除，防止 IDs 过多报错
                    batch_size = 100
                    for i in range(0, len(forum_ids), batch_size):
                        batch_ids = forum_ids[i:i + batch_size]
                        collection.delete(ids=batch_ids)
                    print(f"   ✅ 已成功删除 ChromaDB 中的所有论坛向量")
            except Exception as coll_err:
                print(f"\n🔹 ChromaDB: 集合 avid_posts 不存在或未初始化 ({coll_err})")
                
        except Exception as e:
            print(f"❌ 清空 ChromaDB 数据失败: {e}")
    else:
        print(f"\n🔹 ChromaDB: 向量库不存在于 {CHROMA_PATH}，跳过")

    print("=" * 60)
    print("🎉 爬虫数据清理完成！")

if __name__ == "__main__":
    clear_data()
