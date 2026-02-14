import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "forums.db")

def init_db():
    print(f"Initializing database at {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Threads table
    c.execute('''CREATE TABLE IF NOT EXISTS threads (
        id TEXT PRIMARY KEY,
        title TEXT,
        url TEXT UNIQUE,
        question_content TEXT,
        last_post_date TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        scraped_at TEXT,
        source_url TEXT
    )''')

    # Migration: Add source_url column if it doesn't exist
    try:
        c.execute("ALTER TABLE threads ADD COLUMN source_url TEXT")
        print("Migrated: Added source_url column to threads table")
    except sqlite3.OperationalError:
        # Column likely already exists
        pass
    
    # Posts table (Commented out per user request)
    # c.execute('''CREATE TABLE IF NOT EXISTS posts (
    #     id INTEGER PRIMARY KEY AUTOINCREMENT,
    #     thread_id TEXT,
    #     author TEXT,
    #     content TEXT,
    #     post_date TEXT,
    #     is_op BOOLEAN,
    #     FOREIGN KEY(thread_id) REFERENCES threads(id),
    #     UNIQUE(thread_id, author, content, post_date)
    # )''')
    
    # Sources table
    c.execute('''CREATE TABLE IF NOT EXISTS sources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        url TEXT UNIQUE,
        display_name TEXT,
        last_updated TEXT
    )''')
    
    # Initialize default sources if not exists
    default_sources = [
        # Professional Video Editing
        ('https://community.avid.com/forums/398.aspx', 'Media Composer Error Messages'),
        ('https://community.avid.com/forums/48.aspx', 'Avid Media Composer - Mac'),
        ('https://community.avid.com/forums/49.aspx', 'Avid Media Composer - PC'),
        ('https://community.avid.com/forums/299.aspx', 'Media Composer: Get Started Fast'),
        ('https://community.avid.com/forums/377.aspx', 'Media Composer | First Forum'),
        ('https://community.avid.com/forums/397.aspx', 'MC Titler+ Forum'),
        ('https://community.avid.com/forums/243.aspx', 'Share Your Experience'),
        ('https://community.avid.com/forums/376.aspx', 'Licensing Options'),
        ('https://community.avid.com/forums/381.aspx', 'Licensing Help'),
        ('https://community.avid.com/forums/394.aspx', 'Avid Link'),
        ('https://community.avid.com/forums/379.aspx', 'Avid | Artist Forum'),
        ('https://community.avid.com/forums/56.aspx', 'Avid Options Forum'),
        ('https://community.avid.com/forums/405.aspx', 'Avid Huddle'),
        ('https://community.avid.com/forums/347.aspx', 'Complete Your Suite'),
        ('https://community.avid.com/forums/36.aspx', 'Film and 24p'),
        # Professional Cloud-Based
        ('https://community.avid.com/forums/399.aspx', 'Edit on Demand: Get Started Fast'),
        ('https://community.avid.com/forums/400.aspx', 'Edit on Demand: Tech & Workflow Help'),
        # Storage
        ('https://community.avid.com/forums/378.aspx', 'NEXIS Storage & NEXIS | EDGE'),
        # Broadcast & Servers
        ('https://community.avid.com/forums/131.aspx', 'Avid MediaCentral Forum'),
        ('https://community.avid.com/forums/187.aspx', 'Broadcast Newsroom'),
        ('https://community.avid.com/forums/393.aspx', 'Avid FastServe Servers Forum'),
        # Education
        ('https://community.avid.com/forums/401.aspx', 'Media Composer for Students'),
        ('https://community.avid.com/forums/403.aspx', 'Teacher\'s Lounge')
    ]
    
    for url, topic in default_sources:
        c.execute("INSERT OR IGNORE INTO sources (url, display_name, last_updated) VALUES (?, ?, '')", (url, topic))

    conn.commit()
    conn.close()
    print("Database initialized.")

if __name__ == "__main__":
    init_db()
