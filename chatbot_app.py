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
            "percentage_saved": round((uncached_stats.get('energy_wh', 0) - cached_stats.get('energy_wh', 0)) / 
                                   uncached_stats.get('energy_wh', 1) * 100, 1)
        }

    def _create_comparison_chart(self, cached_stats: Dict, uncached_stats: Dict) -> go.Figure:
        """Create a minimalist energy comparison visualization"""
        total_cached = sum(q['energy_wh'] for q in self.query_stats['cached'])
        total_uncached = sum(q['energy_wh'] for q in self.query_stats['uncached'])
        
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=['Energy Usage'],
            y=[total_cached],
            name='With Cache',
            marker_color='#34c759',
            text=[f"{total_cached:.3f} Wh"],
            textposition='auto',
            width=0.4
        ))
        
        fig.add_trace(go.Bar(
            x=['Energy Usage'],
            y=[total_uncached],
            name='Without Cache',
            marker_color='#ff3b30',
            text=[f"{total_uncached:.3f} Wh"],
            textposition='auto',
            width=0.4
        ))
        
        fig.update_layout(
            template='plotly_white',
            showlegend=True,
            legend=dict(orientation="h", y=1.1),
            margin=dict(l=40, r=40, t=60, b=40),
            yaxis_title="Energy (Wh)",
            plot_bgcolor='rgba(0,0,0,0)'
        )
        
        return fig

    def _create_savings_info(self) -> Tuple[str, str, str]:
        """Create formatted savings info for cards"""
        total_cached = sum(q['energy_wh'] for q in self.query_stats['cached'])
        total_uncached = sum(q['energy_wh'] for q in self.query_stats['uncached'])
        energy_saved = total_uncached - total_cached
        carbon_saved = energy_saved * 475 / 1000  # grams CO2
        
        # Calculate money saved (using average US electricity rate of $0.14/kWh)
        money_saved = (energy_saved / 1000) * 0.14  # Convert Wh to kWh then multiply by rate
        
        energy_text = f"### 💡 Energy Saved\n{energy_saved:.3f} Wh"
        carbon_text = f"### 🌍 Carbon Reduced\n{carbon_saved:.2f}g CO2"
        money_text = f"### 💰 Cost Saved\n${money_saved:.4f}"
        
        return energy_text, carbon_text, money_text

    def launch_comparison_interface(self):
        with gr.Blocks(title="Energy Usage Comparison", theme="soft") as interface:
            gr.Markdown("# Energy Usage Comparison")
            
            # Chat interfaces
            with gr.Row():
                with gr.Column():
                    gr.Markdown("### With Cache")
                    cached_chat = gr.Chatbot(
                        label="Cached Chat",
                        type="messages",
                        show_copy_button=True
                    )
                    cached_msg = gr.Textbox(
                        placeholder="Enter message...",
                        show_label=False
                    )
                    cached_send = gr.Button("Send", variant="primary")
                
                with gr.Column():
                    gr.Markdown("### Without Cache")
                    uncached_chat = gr.Chatbot(
                        label="Uncached Chat",
                        type="messages",
                        show_copy_button=True
                    )
                    uncached_msg = gr.Textbox(
                        placeholder="Enter message...",
                        show_label=False
                    )
                    uncached_send = gr.Button("Send", variant="primary")
            
            # Control buttons - moved up before usage
            clear_btn = gr.Button("Clear All", variant="secondary")
            
            # Visualization and cards
            comparison_chart = gr.Plot(label="Energy Impact")
            
            with gr.Row():
                with gr.Column(scale=1):
                    energy_card = gr.Markdown()
                with gr.Column(scale=1):
                    carbon_card = gr.Markdown()
                with gr.Column(scale=1):
                    trees_card = gr.Markdown()

            def update_interface(message, history, is_cached=True):
                if is_cached:
                    msg, new_history = self.process_cached_only(message, history)
                else:
                    msg, new_history = self.process_uncached_only(message, history)
                
                chart = self._create_comparison_chart(
                    self._latest_cached_stats,
                    self._latest_uncached_stats
                )
                
                energy_text, carbon_text, money_text = self._create_savings_info()
                return msg, new_history, chart, energy_text, carbon_text, money_text
            
            # Update event handlers
            cached_send.click(
                fn=lambda m, h: update_interface(m, h, True),
                inputs=[cached_msg, cached_chat],
                outputs=[cached_msg, cached_chat, comparison_chart, 
                        energy_card, carbon_card, trees_card]
            )
            
            uncached_send.click(
                fn=lambda m, h: update_interface(m, h, False),
                inputs=[uncached_msg, uncached_chat],
                outputs=[uncached_msg, uncached_chat, comparison_chart,
                        energy_card, carbon_card, trees_card]
            )
            
            # Initialize cards
            energy_text, carbon_text, money_text = self._create_savings_info()
            energy_card.value = energy_text
            carbon_card.value = carbon_text
            trees_card.value = money_text
            
            # Update clear handler to show money instead of trees
            clear_btn.click(
                fn=lambda: ("", [], "", [], None, "### 💡 Energy Saved\n0.000 Wh",
                           "### 🌍 Carbon Reduced\n0.00g CO2",
                           "### 💰 Cost Saved\n$0.0000"),
                outputs=[cached_msg, cached_chat, uncached_msg, uncached_chat,
                        comparison_chart, energy_card, carbon_card, trees_card]
            )

        interface.launch(share=True)

if __name__ == "__main__":
    app = ChatbotApp()
    app.launch_interface()
