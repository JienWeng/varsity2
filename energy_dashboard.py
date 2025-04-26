import os
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Optional
import gradio as gr
from energy_monitor import EnergyMonitor
from ab_test_manager import ABTestManager

class EnergyDashboard:
    def __init__(self, log_dir: str = None):
        """Initialize the dashboard with energy monitor and AB test manager"""
        self.log_dir = log_dir or os.path.expanduser("~/.energy_logs")
        self.energy_monitor = EnergyMonitor(log_dir=self.log_dir)
        self.ab_test_manager = ABTestManager(log_dir=self.log_dir)
    
    def create_dashboard_layout(self):
        """Create the main dashboard layout"""
        with gr.Blocks(title="Energy Usage Dashboard") as dashboard:
            gr.Markdown("# 🌱 AI Energy Usage Dashboard")
            
            with gr.Row():
                with gr.Column(scale=1):
                    time_range = gr.Dropdown(
                        choices=["Hour", "Day", "Week", "Month"],
                        value="Day",
                        label="Time Range"
                    )
                    model_filter = gr.Dropdown(
                        choices=self._get_available_models(),
                        value="all",
                        label="Model Filter"
                    )
                refresh_btn = gr.Button("🔄 Refresh")
            
            with gr.Row():
                with gr.Column(scale=1):
                    energy_plot = gr.Plot(
                        value=self._create_energy_comparison_plot(),
                        label="Energy Usage"
                    )
                with gr.Column(scale=1):
                    response_plot = gr.Plot(
                        value=self._create_response_time_plot(),
                        label="Response Time"
                    )
            
            with gr.Row():
                with gr.Column(scale=1):
                    impact_plot = gr.Plot(
                        value=self._create_environmental_impact_plot(),
                        label="Environmental Impact"
                    )
                with gr.Column(scale=1):
                    stats_box = gr.JSON(
                        value=self._get_cache_statistics(),
                        label="Cache Performance"
                    )
            
            # Update plots when controls change
            def update_plots(time_period, model):
                days = {"Hour": 0.042, "Day": 1, "Week": 7, "Month": 30}[time_period]
                return (
                    self._create_energy_comparison_plot(days, model),
                    self._create_response_time_plot(days, model),
                    self._create_environmental_impact_plot(days, model),
                    self._get_cache_statistics(days, model)
                )
            
            time_range.change(update_plots, [time_range, model_filter], 
                            [energy_plot, response_plot, impact_plot, stats_box])
            model_filter.change(update_plots, [time_range, model_filter],
                              [energy_plot, response_plot, impact_plot, stats_box])
            refresh_btn.click(update_plots, [time_range, model_filter],
                            [energy_plot, response_plot, impact_plot, stats_box])
        
        return dashboard
    
    def launch_dashboard(self):
        """Launch the dashboard interface"""
        dashboard = self.create_dashboard_layout()
        dashboard.launch(share=False)
    
    def _get_available_models(self) -> list:
        """Get list of available models from logs"""
        try:
            df = pd.read_csv(os.path.join(self.log_dir, "energy_usage.csv"))
            models = df['model'].unique().tolist()
            return ['all'] + [m for m in models if pd.notna(m)]
        except:
            return ['all']
    
    def _create_energy_comparison_plot(self, days: float = 1, model: str = 'all') -> go.Figure:
        """Create energy usage comparison plot"""
        try:
            # Read energy usage data
            df = pd.read_csv(os.path.join(self.log_dir, "energy_usage.csv"))
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Filter by time and model
            cutoff = pd.Timestamp.now() - pd.Timedelta(days=days)
            df = df[df['timestamp'] > cutoff]
            if model != 'all':
                df = df[df['model'] == model]
            
            if df.empty:
                return self._create_empty_plot("No data available for selected period")
            
            # Create comparison plot
            fig = go.Figure()
            
            # Add cached responses trace
            cached_data = df[df['prompt_length'] < df['response_length']]  # Assumption for cache hits
            fig.add_trace(go.Bar(
                name='Cached',
                x=cached_data['timestamp'],
                y=cached_data['energy_wh'],
                marker_color='green',
                hovertemplate='%{y:.3f} Wh<br>%{text}',
                text=cached_data['model']
            ))
            
            # Add non-cached responses trace
            uncached_data = df[df['prompt_length'] >= df['response_length']]  # Assumption for cache misses
            fig.add_trace(go.Bar(
                name='Non-cached',
                x=uncached_data['timestamp'],
                y=uncached_data['energy_wh'],
                marker_color='red',
                hovertemplate='%{y:.3f} Wh<br>%{text}',
                text=uncached_data['model']
            ))
            
            fig.update_layout(
                title='Energy Usage Comparison',
                xaxis_title='Time',
                yaxis_title='Energy (Wh)',
                barmode='group'
            )
            
            return fig
        except Exception as e:
            print(f"Error creating energy plot: {e}")
            return self._create_empty_plot("Error creating energy comparison plot")

    def _create_response_time_plot(self, days: float = 1, model: str = 'all') -> go.Figure:
        """Create response time comparison plot"""
        try:
            df = pd.read_csv(os.path.join(self.log_dir, "energy_usage.csv"))
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            cutoff = pd.Timestamp.now() - pd.Timedelta(days=days)
            df = df[df['timestamp'] > cutoff]
            if model != 'all':
                df = df[df['model'] == model]
            
            if df.empty:
                return self._create_empty_plot("No data available for selected period")
            
            fig = go.Figure()
            
            # Add cached responses timing
            cached_data = df[df['prompt_length'] < df['response_length']]
            fig.add_trace(go.Scatter(
                name='Cached',
                x=cached_data['timestamp'],
                y=cached_data['duration_seconds'],
                mode='lines+markers',
                line=dict(color='green'),
                hovertemplate='%{y:.2f} seconds'
            ))
            
            # Add non-cached responses timing
            uncached_data = df[df['prompt_length'] >= df['response_length']]
            fig.add_trace(go.Scatter(
                name='Non-cached',
                x=uncached_data['timestamp'],
                y=uncached_data['duration_seconds'],
                mode='lines+markers',
                line=dict(color='red'),
                hovertemplate='%{y:.2f} seconds'
            ))
            
            fig.update_layout(
                title='Response Time Comparison',
                xaxis_title='Time',
                yaxis_title='Duration (seconds)'
            )
            
            return fig
        except Exception as e:
            print(f"Error creating response time plot: {e}")
            return self._create_empty_plot("Error creating response time plot")

    def _create_environmental_impact_plot(self, days: float = 1, model: str = 'all') -> go.Figure:
        """Create environmental impact visualization"""
        try:
            df = pd.read_csv(os.path.join(self.log_dir, "energy_usage.csv"))
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            cutoff = pd.Timestamp.now() - pd.Timedelta(days=days)
            df = df[df['timestamp'] > cutoff]
            if model != 'all':
                df = df[df['model'] == model]
            
            if df.empty:
                return self._create_empty_plot("No data available for selected period")
            
            # Calculate cumulative energy savings
            df['energy_saved'] = df.apply(
                lambda x: x['energy_wh'] if x['prompt_length'] < x['response_length'] else 0, 
                axis=1
            )
            df['cumulative_savings'] = df['energy_saved'].cumsum()
            
            # Convert to environmental impact
            carbon_factor = 0.475  # kgCO2/kWh (global average)
            df['carbon_saved'] = df['cumulative_savings'] * carbon_factor / 1000
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=df['timestamp'],
                y=df['carbon_saved'],
                fill='tozeroy',
                name='Carbon Saved',
                line=dict(color='green'),
                hovertemplate='%{y:.3f} kg CO2'
            ))
            
            fig.update_layout(
                title='Cumulative Environmental Impact',
                xaxis_title='Time',
                yaxis_title='Carbon Saved (kg CO2)'
            )
            
            return fig
        except Exception as e:
            print(f"Error creating impact plot: {e}")
            return self._create_empty_plot("Error creating environmental impact plot")

    def _get_cache_statistics(self, days: float = 1, model: str = 'all') -> Dict:
        """Get cache performance statistics"""
        try:
            df = pd.read_csv(os.path.join(self.log_dir, "energy_usage.csv"))
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            cutoff = pd.Timestamp.now() - pd.Timedelta(days=days)
            df = df[df['timestamp'] > cutoff]
            if model != 'all':
                df = df[df['model'] == model]
            
            if df.empty:
                return {"error": "No data available"}
            
            total_queries = len(df)
            cache_hits = len(df[df['prompt_length'] < df['response_length']])
            
            total_energy = df['energy_wh'].sum()
            cached_energy = df[df['prompt_length'] < df['response_length']]['energy_wh'].sum()
            
            total_time = df['duration_seconds'].sum()
            cached_time = df[df['prompt_length'] < df['response_length']]['duration_seconds'].sum()
            
            return {
                "hit_rate": (cache_hits / total_queries * 100) if total_queries > 0 else 0,
                "energy_savings": ((total_energy - cached_energy) / total_energy * 100) if total_energy > 0 else 0,
                "time_savings": ((total_time - cached_time) / total_time * 100) if total_time > 0 else 0,
                "total_queries": total_queries,
                "cache_hits": cache_hits,
                "total_energy_wh": total_energy,
                "cached_energy_wh": cached_energy,
                "carbon_saved_kg": (total_energy - cached_energy) * 0.475 / 1000  # Using global average carbon factor
            }
        except Exception as e:
            print(f"Error calculating statistics: {e}")
            return {"error": str(e)}

    def _create_empty_plot(self, message: str) -> go.Figure:
        """Create an empty plot with a message"""
        fig = go.Figure()
        fig.add_annotation(
            text=message,
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False
        )
        return fig
