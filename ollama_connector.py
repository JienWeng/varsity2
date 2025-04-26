import requests
from typing import Optional, List, Dict

class OllamaConnector:
    def __init__(self, model: str = "llama3.2:latest", base_url: str = "http://localhost:11434"):
        self.base_url = base_url.rstrip('/')
        self.available_models = self._get_available_models()
        self.model = self._validate_model(model)

    def _get_available_models(self) -> List[str]:
        """Get list of available models"""
        try:
            response = requests.get(f"{self.base_url}/api/tags")
            if response.status_code == 200:
                return [model['name'] for model in response.json().get('models', [])]
            return []
        except Exception:
            return []

    def _validate_model(self, requested_model: str) -> str:
        """Validate and return appropriate model name"""
        if not self.available_models:
            print("Warning: No models available. Please check Ollama installation.")
            return requested_model

        if requested_model in self.available_models:
            return requested_model

        # Try to find a matching model (case insensitive)
        for model in self.available_models:
            if model.lower().startswith(requested_model.lower()):
                print(f"Using available model '{model}' instead of '{requested_model}'")
                return model

        # Fallback to first available model
        fallback = self.available_models[0]
        print(f"Model '{requested_model}' not found. Using '{fallback}' instead.")
        return fallback

    def is_available(self) -> bool:
        """Check if Ollama is running and available"""
        try:
            response = requests.get(f"{self.base_url}/api/tags")
            return response.status_code == 200
        except requests.RequestException:
            return False
    
    def get_available_models(self) -> list:
        """Get list of available models from Ollama"""
        return self.available_models
    
    def generate_response(self, prompt: str, params: Dict = None) -> Optional[str]:
        """
        Generate a response from Ollama.
        
        Args:
            prompt: The user prompt
            params: Additional parameters for the model
            
        Returns:
            The generated response or None if there was an error
        """
        if params is None:
            params = {}
            
        default_params = {
            "model": self.model,
            "prompt": prompt,
            "stream": False
        }
        
        # Merge default params with custom params
        request_params = {**default_params, **params}
        
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=request_params,
                timeout=120  # 2-minute timeout
            )
            
            if response.status_code == 200:
                return response.json().get("response", "")
            else:
                print(f"Error from Ollama API: {response.status_code}")
                print(response.text)
                return None
                
        except requests.RequestException as e:
            print(f"Error connecting to Ollama: {e}")
            return None
    
    def set_model(self, model: str):
        """Change the model being used"""
        self.model = self._validate_model(model)
