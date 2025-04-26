import json
import os
from typing import Dict, List, Optional
from datetime import datetime

class PromptHistory:
    def __init__(self, history_path: str = "cache"):
        """
        Initialize the prompt history manager.
        
        Args:
            history_path: Directory to save/load history data
        """
        self.history_path = history_path
        self.history_file = os.path.join(history_path, "prompt_history.json")
        self.history = []
        
        # Create history directory if it doesn't exist
        os.makedirs(history_path, exist_ok=True)
        
        # Load history if it exists
        self.load_history()
    
    def add_interaction(self, prompt: str, response: str, metadata: Dict = None):
        """
        Add a prompt-response interaction to the history.
        
        Args:
            prompt: User input prompt
            response: AI-generated response
            metadata: Additional information like timestamps, energy usage, etc.
        """
        if metadata is None:
            metadata = {}
            
        # Add timestamp if not provided
        if 'timestamp' not in metadata:
            metadata['timestamp'] = datetime.now().isoformat()
            
        entry = {
            'prompt': prompt,
            'response': response,
            'metadata': metadata
        }
        
        self.history.append(entry)
        self.save_history()
    
    def get_last_n_interactions(self, n: int = 5) -> List[Dict]:
        """Get the last n interactions from the history"""
        return self.history[-n:] if self.history else []
    
    def find_exact_prompt(self, prompt: str) -> Optional[Dict]:
        """Find an exact match for a prompt in the history"""
        for entry in reversed(self.history):
            if entry['prompt'] == prompt:
                return entry
        return None
    
    def save_history(self):
        """Save the history to disk"""
        with open(self.history_file, 'w') as f:
            json.dump(self.history, f, indent=2)
    
    def load_history(self):
        """Load the history from disk if it exists"""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r') as f:
                    self.history = json.load(f)
            except Exception as e:
                print(f"Error loading history: {e}")
                self.history = []
