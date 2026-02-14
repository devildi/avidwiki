from sentence_transformers import SentenceTransformer
import time

def test_model():
    print("Testing SentenceTransformer model download...")
    start = time.time()
    model = SentenceTransformer("all-MiniLM-L6-v2")
    print(f"Model loaded in {time.time() - start:.2f} seconds.")
    
    emb = model.encode("Hello world")
    print(f"Embedding shape: {emb.shape}")

if __name__ == "__main__":
    test_model()
