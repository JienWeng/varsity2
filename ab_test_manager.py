import json
import os
import pandas as pd
from datetime import datetime
from typing import Dict, Optional, List, Tuple
from energy_monitor import EnergyMonitor

class ABTestManager:
    def __init__(self, log_dir: str = None):
        self.log_dir = log_dir or os.path.expanduser("~/.energy_logs")
        self.ab_test_file = os.path.join(self.log_dir, "ab_test_results.json")
        self.energy_monitor = EnergyMonitor(log_dir=log_dir)
        
        # Carbon emission factors (gCO2/kWh) for different energy sources
        self.carbon_factors = {
            'global_average': 475,  # Global average
            'renewable': 50,        # Renewable energy
            'usa_average': 417,     # USA average
        }
        
        # Initialize results file if it doesn't exist
        if not os.path.exists(self.ab_test_file):
            self._save_results([])
    
    def run_comparison(self, prompt: str, cached_response: Tuple[str, Dict], 
                      uncached_response: Tuple[str, Dict]) -> Dict:
        """Compare cached vs uncached response metrics"""
        cached_text, cached_metrics = cached_response
        uncached_text, uncached_metrics = uncached_response
        
        # Calculate energy savings
        cached_energy = cached_metrics.get('energy_wh', 0)
        uncached_energy = uncached_metrics.get('energy_wh', 0)
        energy_saved = max(0, uncached_energy - cached_energy)
        
        # Calculate carbon savings (using global average)
        carbon_saved = energy_saved * (self.carbon_factors['global_average'] / 1000)  # Convert to kg CO2
        
        result = {
            'timestamp': datetime.now().isoformat(),
            'prompt_length': len(prompt),
            'cached_response_length': len(cached_text),
            'uncached_response_length': len(uncached_text),
            'cached_duration': cached_metrics.get('duration_seconds', 0),
            'uncached_duration': uncached_metrics.get('duration_seconds', 0),
            'cached_energy_wh': cached_energy,
            'uncached_energy_wh': uncached_energy,
            'energy_saved_wh': energy_saved,
            'carbon_saved_kg': carbon_saved,
            'cached_power_watts': cached_metrics.get('avg_power_watts', 0),
            'uncached_power_watts': uncached_metrics.get('avg_power_watts', 0)
        }
        
        # Save result
        self._append_result(result)
        return result
    
    def get_summary_stats(self, days: int = 7) -> Dict:
        """Get summary statistics for A/B test results"""
        results = self._load_results()
        if not results:
            return {}
            
        df = pd.DataFrame(results)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Filter by days
        cutoff = pd.Timestamp.now() - pd.Timedelta(days=days)
        df = df[df['timestamp'] > cutoff]
        
        if df.empty:
            return {}
        
        total_saved = {
            'energy_wh': df['energy_saved_wh'].sum(),
            'carbon_kg': df['carbon_saved_kg'].sum(),
            'time_seconds': (df['uncached_duration'] - df['cached_duration']).sum(),
            'queries': len(df)
        }
        
        averages = {
            'energy_saved_per_query_wh': df['energy_saved_wh'].mean(),
            'carbon_saved_per_query_kg': df['carbon_saved_kg'].mean(),
            'time_saved_per_query_s': (df['uncached_duration'] - df['cached_duration']).mean(),
            'cache_power_reduction_pct': ((df['uncached_power_watts'] - df['cached_power_watts']) / 
                                        df['uncached_power_watts'] * 100).mean()
        }
        
        return {
            'total_saved': total_saved,
            'averages': averages,
            'equivalent_to': self._get_environmental_equivalents(total_saved['carbon_kg'])
        }
    
    def _get_environmental_equivalents(self, carbon_kg: float) -> Dict:
        """Convert carbon savings to relatable equivalents"""
        return {
            'trees_days': carbon_kg * 1.2,  # Days of oxygen from one tree
            'car_km': carbon_kg * 6.3,      # Kilometers not driven by average car
            'phone_charges': carbon_kg * 121 # Smartphone charges
        }
    
    def _load_results(self) -> List[Dict]:
        """Load saved test results"""
        try:
            with open(self.ab_test_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []
    
    def _save_results(self, results: List[Dict]):
        """Save test results to file"""
        os.makedirs(os.path.dirname(self.ab_test_file), exist_ok=True)
        with open(self.ab_test_file, 'w') as f:
            json.dump(results, f, indent=2)
    
    def _append_result(self, result: Dict):
        """Append a new test result"""
        results = self._load_results()
        results.append(result)
        self._save_results(results)
