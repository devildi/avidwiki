import os

DOCS_DIR = "data/docs"

def ingest_documents():
    print(f"Scanning {DOCS_DIR} for documents...")
    
    if not os.path.exists(DOCS_DIR):
        print(f"Directory {DOCS_DIR} does not exist. Creating it.")
        os.makedirs(DOCS_DIR)
        
    files = [f for f in os.listdir(DOCS_DIR) if f.endswith('.pdf')]
    
    if not files:
        print("No PDF files found. Please place your docs in 'data/docs/'.")
        return

    print(f"Found {len(files)} documents: {files}")
    
    for file in files:
        path = os.path.join(DOCS_DIR, file)
        process_file(path)

def process_file(path):
    print(f"Processing {path}...")
    # TODO: Implement PDF text extraction (e.g. using pypdf or pdfplumber)
    # TODO: Chunk text
    # TODO: Send to Vector Store
    print(f"Finished {path} (Mock)")

if __name__ == "__main__":
    ingest_documents()
