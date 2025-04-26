from typing import Dict, List, Tuple, Optional
import gradio as gr
import asyncio
from semantic_cache import SemanticCache
from prompt_history import PromptHistory
from energy_monitor import EnergyMonitor
from ollama_connector import OllamaConnector
from ab_test_manager import ABTestManager

import time
from typing import Dict, List, Tuple
import platform
import plotly.graph_objs as go
from datetime import datetime

class ChatbotApp:
    def __init__(self, *args, **kwargs):
        # Initialize the chatbot application.
        
        # Args:
            # semantic_threshold: Threshold for semantic similarity
            # ollama_model: Default Ollama model to use
            # ollama_url: URL for the Ollama API
            # enable_monitoring: Whether to enable resource monitoring
            # monitoring_level: Level of resource monitoring detail
            # continuous_monitoring: Whether to enable continuous power monitoring during inference
            # log_dir: Directory to store energy usage logs
        self.semantic_cache = SemanticCache(similarity_threshold=kwargs.get('semantic_threshold', 0.85))
        self.prompt_history = PromptHistory()
        
        # Initialize energy monitor
        self.energy_monitor = None
        if kwargs.get('enable_monitoring', True):
            self.energy_monitor = EnergyMonitor(log_dir=kwargs.get('log_dir', None))
        
        self.ollama = OllamaConnector(model=kwargs.get('ollama_model', "llama3.2:latest"), base_url=kwargs.get('ollama_url', "http://localhost:11434"))
        self.enable_monitoring = kwargs.get('enable_monitoring', True)
        self.monitoring_level = kwargs.get('monitoring_level', "basic")
        self.continuous_monitoring = kwargs.get('continuous_monitoring', False)
        self.system_info = {
            'system': platform.system(),
            'release': platform.release(),
            'version': platform.version(),
            'machine': platform.machine()
        }
        
        # Check if Ollama is available
        if not self.ollama.is_available():
            print("Warning: Ollama service not available. Make sure it's running.")
        
        self.comparison_mode = kwargs.get('comparison_mode', False)
        self.message_history = []
        self.processing_lock = asyncio.Lock()
        self._latest_cached_stats = {}
        self._latest_uncached_stats = {}
        self.cumulative_stats = {
            'cached': {'total_energy': 0, 'total_time': 0, 'queries': 0},
            'uncached': {'total_energy': 0, 'total_time': 0, 'queries': 0}
        }
        self.query_stats = {
            'cached': [],
            'uncached': []
        }

    def _update_cumulative_stats(self, energy_data: Dict, mode: str):
        """Update cumulative energy statistics"""
        if energy_data:
            self.cumulative_stats[mode]['total_energy'] += energy_data.get('energy_wh', 0)
            self.cumulative_stats[mode]['total_time'] += energy_data.get('duration_seconds', 0)
            self.cumulative_stats[mode]['queries'] += 1
            self.query_stats[mode].append({
                'timestamp': datetime.now(),
                'energy_wh': energy_data.get('energy_wh', 0),
                'power_watts': energy_data.get('avg_power_watts', 0),
                'duration_seconds': energy_data.get('duration_seconds', 0)
            })

    def process_cached_only(self, message: str, history: List[Dict]) -> Tuple[str, List[Dict]]:
        """Process message from cached side"""
        if not message.strip():
            return "", history

        try:
            # Always monitor energy for cached side
            if self.energy_monitor:
                self.energy_monitor.start_monitoring()
            
            # Try to get from cache first
            cached_response = self.semantic_cache.get_response(message)
            
            if not cached_response:
                # If not in cache, get new response
                cached_response = self.ollama.generate_response(message)
                if cached_response:
                    self.semantic_cache.add_to_cache(message, cached_response)
            
            # Always record energy under cached stats
            energy_data = self.energy_monitor.end_monitoring() if self.energy_monitor else {}
            
            if cached_response:
                new_history = history + [
                    {"role": "user", "content": message},
                    {"role": "assistant", "content": cached_response}
                ]
                # Always update cached stats regardless of cache hit/miss
                self._latest_cached_stats = {
                    "status": "cached_side",
                    "energy_wh": energy_data.get('energy_wh', 0),
                    "duration_seconds": energy_data.get('duration_seconds', 0),
                    "power_watts": energy_data.get('avg_power_watts', 0)
                }
                self._update_cumulative_stats(energy_data, 'cached')
                return "", new_history
            
            return "", history
            
        except Exception as e:
            print(f"Error in cached processing: {e}")
            return "", history

    def process_uncached_only(self, message: str, history: List[Dict]) -> Tuple[str, List[Dict]]:
        """Process message from uncached side"""
        if not message.strip():
            return "", history

        try:
            # Always monitor energy for uncached side
            if self.energy_monitor:
                self.energy_monitor.start_monitoring()
            
            # Always get fresh response without using cache
            response = self.ollama.generate_response(message)
            energy_data = self.energy_monitor.end_monitoring() if self.energy_monitor else {}
            
            if response:
                new_history = history + [
                    {"role": "user", "content": message},
                    {"role": "assistant", "content": response}
                ]
                # Always update uncached stats
                self._latest_uncached_stats = {
                    "status": "uncached_side",
                    "energy_wh": energy_data.get('energy_wh', 0),
                    "duration_seconds": energy_data.get('duration_seconds', 0),
                    "power_watts": energy_data.get('avg_power_watts', 0)
                }
                self._update_cumulative_stats(energy_data, 'uncached')
                return "", new_history
            
            return "", history
            
        except Exception as e:
            print(f"Error in uncached processing: {e}")
            return "", history

    def _calculate_savings(self, cached_stats: Dict, uncached_stats: Dict) -> Dict:
        """Calculate energy and carbon savings"""
        energy_saved = uncached_stats.get('energy_wh', 0) - cached_stats.get('energy_wh', 0)
        time_saved = uncached_stats.get('duration_seconds', 0) - cached_stats.get('duration_seconds', 0)
        
        # Convert Wh to CO2 (using average grid carbon intensity of 475g CO2/kWh)
        carbon_saved = energy_saved * 475 / 1000  # grams of CO2
        
        return {
            "energy_saved_wh": round(energy_saved, 3),
            "time_saved_seconds": round(time_saved, 2),
            "carbon_saved_g": round(carbon_saved, 2),
            "trees_equivalent": round(carbon_saved * 0.0085, 4),  # 1 tree absorbs ~117g CO2 per day
            "percentage_saved": round((uncached_stats.get('energy_wh', 0) - cached_stats.get('energy_wh', 0)) / 
                                   uncached_stats.get('energy_wh', 1) * 100, 1)
        }

    def _create_comparison_chart(self, cached_stats: Dict, uncached_stats: Dict) -> go.Figure:
        """Create visualization of total energy usage"""
        fig = go.Figure()
        
        # Calculate total energy usage (only count real LLM queries)
        total_cached = sum(q['energy_wh'] for q in self.query_stats['cached'])
        total_uncached = sum(q['energy_wh'] for q in self.query_stats['uncached'])
        
        # Create two bars for total energy
        fig = go.Figure(data=[
            go.Bar(
                x=['Total Energy Usage'],
                y=[total_cached],
                name='LLM Queries (Cached Side)',
                marker_color='green',
                text=[f"{total_cached:.3f} Wh"],
                textposition='auto',
                width=0.3
            ),
            go.Bar(
                x=['Total Energy Usage'],
                y=[total_uncached],
                name='LLM Queries (Uncached Side)',
                marker_color='red',
                text=[f"{total_uncached:.3f} Wh"],
                textposition='auto',
                width=0.3
            )
        ])
        
        # Calculate savings
        energy_saved = total_uncached - total_cached
        carbon_saved = energy_saved * 475 / 1000  # grams CO2
        
        # Add savings annotation
        fig.add_annotation(
            x=1.3,  # Position to the right of bars
            y=max(total_cached, total_uncached)/2,
            text=f"Carbon Saved:<br>{carbon_saved:.2f}g CO2<br>≈ {(carbon_saved * 0.0085):.3f} tree days",
            showarrow=False,
            font=dict(size=14),
            bgcolor='lightgreen',
            bordercolor='green',
            borderwidth=2,
            borderpad=4,
            align='center'
        )
        
        # Update layout
        fig.update_layout(
            title="Total Energy Consumption Comparison",
            showlegend=True,
            height=400,
            bargap=0.15,
            margin=dict(r=200),  # Make room for savings card
            yaxis_title="Energy (Wh)",
            template="plotly_white"
        )
        
        return fig

    def launch_comparison_interface(self):
        """Launch side-by-side comparison interface"""
        with gr.Blocks(title="Cache vs No-Cache Comparison") as interface:
            gr.Markdown("# 🔄 Cache vs No-Cache Comparison")
            
            with gr.Row():
                with gr.Column():
                    gr.Markdown("## With Cache")
                    cached_chat = gr.Chatbot(
                        label="Cached Responses",
                        type="messages",
                        show_copy_button=True
                    )
                    cached_msg = gr.Textbox(
                        placeholder="Type message here...",
                        label="Message (Cached Side)"
                    )
                    cached_send = gr.Button("Send (Cached)")
                
                with gr.Column():
                    gr.Markdown("## Without Cache")
                    uncached_chat = gr.Chatbot(
                        label="Uncached Responses",
                        type="messages",
                        show_copy_button=True
                    )
                    uncached_msg = gr.Textbox(
                        placeholder="Type message here...",
                        label="Message (Uncached Side)"
                    )
                    uncached_send = gr.Button("Send (Uncached)")
            
            with gr.Row():
                clear_btn = gr.Button("Clear Both")
            
            # Add comparison visualization
            comparison_chart = gr.Plot(label="Energy Impact")

            def update_visualization() -> go.Figure:
                return self._create_comparison_chart(
                    self._latest_cached_stats,
                    self._latest_uncached_stats
                )
            
            def process_cached_and_update(message: str, history: List[Dict]) -> Tuple[str, List[Dict], go.Figure]:
                msg, new_history = self.process_cached_only(message, history)
                return msg, new_history, self._create_comparison_chart(
                    self._latest_cached_stats,
                    self._latest_uncached_stats
                )
            
            def process_uncached_and_update(message: str, history: List[Dict]) -> Tuple[str, List[Dict], go.Figure]:
                msg, new_history = self.process_uncached_only(message, history)
                return msg, new_history, self._create_comparison_chart(
                    self._latest_cached_stats,
                    self._latest_uncached_stats
                )
            
            # Handle cached side
            cached_send.click(
                process_cached_and_update,
                [cached_msg, cached_chat],
                [cached_msg, cached_chat, comparison_chart]
            )
            
            # Handle uncached side
            uncached_send.click(
                process_uncached_and_update,
                [uncached_msg, uncached_chat],
                [uncached_msg, uncached_chat, comparison_chart]
            )
            
            # Simplify to just a refresh button
            with gr.Row():
                gr.Markdown("## Power Usage")
                refresh_btn = gr.Button("🔄 Update Stats", variant="secondary")

            def update_power_stats():
                """Update power stats"""
                if self.energy_monitor:
                    current_stats = self.energy_monitor._get_power_usage()
                    if current_stats:
                        self._latest_cached_stats.update({
                            'power_watts': current_stats.get('power_watts', 0)
                        })
                return self._create_comparison_chart(
                    self._latest_cached_stats,
                    self._latest_uncached_stats
                )

            # Manual refresh only
            refresh_btn.click(
                fn=update_power_stats,
                outputs=comparison_chart
            )

            # Clear everything
            clear_btn.click(
                lambda: ("", [], "", [], None),
                None,
                [cached_msg, cached_chat, uncached_msg, uncached_chat, comparison_chart]
            )

        interface.launch(share=True)  # Enable public sharing

if __name__ == "__main__":
    app = ChatbotApp()
    app.launch_interface()
