from sentence_transformers import SentenceTransformer
import time

def test_model():
    print("Testing SentenceTransformer model download...")
    start = time.time()
    import os
    local_model_path = os.path.join(os.getcwd(), "data", "all-MiniLM-L6-v2")
    model_identifier = local_model_path if os.path.exists(local_model_path) else "all-MiniLM-L6-v2"
    model = SentenceTransformer(model_identifier)
    print(f"Model loaded in {time.time() - start:.2f} seconds.")
    
    emb = model.encode("Hello world")
    print(f"Embedding shape: {emb.shape}")

if __name__ == "__main__":
    test_model()
