"""
semantic_search.py — Vector Similarity Matching Engine (Local Context Realization)
"""

import numpy as np
from sentence_transformers import SentenceTransformer

# Load a lightweight, highly accurate bilingual model (English/Arabic optimized)
base_model_cache = None

def get_embedding_model():
    global base_model_cache
    if base_model_cache is None:
        # 'paraphrase-multilingual-MiniLM-L12-v2' is excellent for cross-lingual Arabic mapping
        base_model_cache = SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')
    return base_model_cache

def calculate_embedding(text: str) -> list:
    """Converts a text string into a 384-dimensional dense vector."""
    model = get_embedding_model()
    embedding = model.encode(text, convert_to_numpy=True)
    return embedding.tolist()

def compute_cosine_similarity(vec_a: list, vec_b: list) -> float:
    """Calculates how close two meaning vectors are quickly using numpy."""
    a = np.asarray(vec_a, dtype=np.float32)
    b = np.asarray(vec_b, dtype=np.float32)
    
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
        
    return float(np.dot(a, b) / (norm_a * norm_b))