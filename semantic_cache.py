import numpy as np
import os
# Set tokenizers parallelism environment variable
if "TOKENIZERS_PARALLELISM" not in os.environ:
    os.environ["TOKENIZERS_PARALLELISM"] = "false"

from sentence_transformers import SentenceTransformer
import pickle
import os
from typing import Dict, List, Tuple, Optional

class SemanticCache:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2", similarity_threshold: float = 0.85, cache_path: str = "cache"):
        """
        Initialize the semantic cache with a sentence transformer model.
        
        Args:
            model_name: The sentence transformer model to use
            similarity_threshold: Threshold above which prompts are considered similar
            cache_path: Directory to save/load cache data
        """
        self.model = SentenceTransformer(model_name)
        self.embeddings = {}  # Dict of prompt: embedding
        self.responses = {}   # Dict of prompt: response
        self.similarity_threshold = similarity_threshold
        self.cache_path = cache_path
        
        # Create cache directory if it doesn't exist
        os.makedirs(cache_path, exist_ok=True)
        self.cache_file = os.path.join(cache_path, "semantic_cache.pkl")
        
        # Load cache if it exists
        self.load_cache()
    
    def embed_prompt(self, prompt: str) -> np.ndarray:
        """Generate embedding for a prompt"""
        return self.model.encode(prompt)
    
    def find_similar_prompt(self, prompt: str) -> Optional[str]:
        """
        Find a semantically similar prompt in the cache.
        Returns the original prompt if found, None otherwise.
        """
        if not self.embeddings:
            return None
            
        query_embedding = self.embed_prompt(prompt)
        
        # Calculate cosine similarity with all stored embeddings
        max_similarity = -1
        most_similar_prompt = None
        
        for cached_prompt, cached_embedding in self.embeddings.items():
            similarity = np.dot(query_embedding, cached_embedding) / (
                np.linalg.norm(query_embedding) * np.linalg.norm(cached_embedding)
            )
            
            if similarity > max_similarity:
                max_similarity = similarity
                most_similar_prompt = cached_prompt
        
        if max_similarity >= self.similarity_threshold:
            return most_similar_prompt
        return None
    
    def add_to_cache(self, prompt: str, response: str):
        """Add a prompt and its response to the cache"""
        self.embeddings[prompt] = self.embed_prompt(prompt)
        self.responses[prompt] = response
        self.save_cache()
    
    def get_response(self, prompt: str) -> Optional[str]:
        """Get the cached response for a prompt"""
        similar_prompt = self.find_similar_prompt(prompt)
        if similar_prompt:
            return self.responses[similar_prompt]
        return None
    
    def save_cache(self):
        """Save the cache to disk"""
        with open(self.cache_file, 'wb') as f:
            pickle.dump({
                'embeddings': self.embeddings,
                'responses': self.responses
            }, f)
    
    def load_cache(self):
        """Load the cache from disk if it exists"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'rb') as f:
                    data = pickle.load(f)
                    self.embeddings = data['embeddings']
                    self.responses = data['responses']
            except Exception as e:
                print(f"Error loading cache: {e}")
