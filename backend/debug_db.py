import sqlite3
import os

# Adjust path if running from project root or backend dir
DB_PATH = "backend/crawler/forums.db"
if not os.path.exists(DB_PATH):
    # Try local path if running from backend/crawler
    DB_PATH = "forums.db" 

if not os.path.exists(DB_PATH):
    print(f"Error: Database not found at {DB_PATH}")
    exit(1)

def inspect_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print(f"📦 Database: {DB_PATH}")
    print("=" * 60)
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    
    for table_info in tables:
        table_name = table_info[0]
        
        # Get row count
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        
        print(f"\n📋 Table: {table_name}")
        print(f"   Count: {count} rows")
        
        # Get column names
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [col[1] for col in cursor.fetchall()]
        print(f"   Columns: {', '.join(columns)}")
        
        # Show last 3 rows
        if count > 0:
            print("   Latest 3 entries:")
            try:
                cursor.execute(f"SELECT * FROM {table_name} ORDER BY id DESC LIMIT 3")
                rows = cursor.fetchall()
                for row in rows:
                    # Truncate long fields for display
                    display_row = []
                    for item in row:
                        s = str(item)
                        if len(s) > 50:
                            s = s[:47] + "..."
                        display_row.append(s)
                    print(f"     - {display_row}")
            except Exception as e:
                print(f"     (Could not fetch rows by ID: {e})")
                # Fallback: just get any 3 rows
                try:
                    cursor.execute(f"SELECT * FROM {table_name} LIMIT 3")
                    rows = cursor.fetchall()
                    for row in rows:
                        print(f"     - {row}")
                except:
                    pass
        else:
            print("   (Empty)")
            
        print("-" * 60)

    conn.close()

if __name__ == "__main__":
    inspect_db()
