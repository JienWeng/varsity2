import os
# Set tokenizers parallelism environment variable to avoid warnings
os.environ["TOKENIZERS_PARALLELISM"] = "false"

from chatbot_app import ChatbotApp
from energy_dashboard import EnergyDashboard
import argparse
import platform

def main():
    parser = argparse.ArgumentParser(
        description="Eco-Friendly AI Chatbot with semantic caching"
    )
    
    parser.add_argument(
        "--model", 
        type=str, 
        default="llama3.2:latest", 
        help="Ollama model to use (default: llama3.2:latest)"
    )
    
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.85,
        help="Semantic similarity threshold (0.5-1.0)"
    )
    
    parser.add_argument(
        "--ollama-url",
        type=str,
        default="http://localhost:11434",
        help="URL for Ollama API"
    )
    
    parser.add_argument(
        "--disable-monitoring",
        action="store_true",
        help="Disable resource usage monitoring"
    )
    
    # Add system-specific default setting for monitoring
    system = platform.system()
    default_monitoring_message = ""
    if system == 'Darwin':  # macOS
        default_monitoring_message = " (uses powermetrics for energy monitoring on macOS)"
    elif system == 'Linux':
        default_monitoring_message = " (uses CPU/memory monitoring on Linux)"
    elif system == 'Windows':
        default_monitoring_message = " (limited support on Windows)"
    
    parser.add_argument(
        "--monitoring-level",
        type=str,
        choices=["basic", "detailed"],
        default="basic",
        help=f"Resource monitoring detail level{default_monitoring_message}"
    )
    
    parser.add_argument(
        "--continuous-monitoring",
        action="store_true",
        help="Enable continuous power monitoring during inference (macOS only)"
    )
    
    parser.add_argument(
        "--log-dir",
        type=str,
        default=os.path.expanduser("~/.energy_logs"),
        help="Directory to store energy usage logs"
    )
    
    parser.add_argument(
        "--dashboard-only",
        action="store_true",
        help="Launch energy dashboard without starting the chatbot"
    )
    
    parser.add_argument(
        "--enable-ab-testing",
        action="store_true",
        help="Enable A/B testing to compare cached vs non-cached responses"
    )
    
    parser.add_argument(
        "--comparison-mode",
        action="store_true",
        help="Launch in side-by-side cache comparison mode"
    )

    args = parser.parse_args()
    
    # Try to initialize Ollama connector first to validate model
    try:
        from ollama_connector import OllamaConnector
        connector = OllamaConnector(model=args.model, base_url=args.ollama_url)
        if not connector.is_available():
            print(f"Error: Model {args.model} not available. Please check your Ollama installation.")
            return
    except Exception as e:
        print(f"Error connecting to Ollama: {e}")
        return

    # If comparison mode is selected
    if args.comparison_mode:
        app = ChatbotApp(
            semantic_threshold=args.threshold,
            ollama_model=args.model,
            ollama_url=args.ollama_url,
            enable_monitoring=not args.disable_monitoring,
            monitoring_level=args.monitoring_level,
            continuous_monitoring=args.continuous_monitoring,
            log_dir=args.log_dir,
            comparison_mode=True
        )
        print("Starting in comparison mode...")
        app.launch_comparison_interface()
        return

    # If dashboard only mode is selected
    if args.dashboard_only:
        print(f"Launching energy usage dashboard using logs from: {args.log_dir}")
        dashboard = EnergyDashboard(log_dir=args.log_dir)
        dashboard.launch_dashboard()
        return
    
    app = ChatbotApp(
        semantic_threshold=args.threshold,
        ollama_model=args.model,
        ollama_url=args.ollama_url,
        enable_monitoring=not args.disable_monitoring,
        monitoring_level=args.monitoring_level,
        continuous_monitoring=args.continuous_monitoring,
        log_dir=args.log_dir,
        enable_ab_testing=args.enable_ab_testing  # Add this line
    )
    
    print(f"Starting chatbot with model: {args.model}")
    print(f"Semantic similarity threshold: {args.threshold}")
    print(f"A/B Testing: {'Enabled' if args.enable_ab_testing else 'Disabled'}")

    monitoring_status = "Disabled"
    if not args.disable_monitoring:
        monitoring_status = f"Enabled ({args.monitoring_level})"
        if system == 'Darwin':
            monitoring_status += f", using powermetrics"
        
    print(f"Resource monitoring: {monitoring_status}")
    print(f"Energy logs directory: {args.log_dir}")
    print(f"Running on: {platform.system()} {platform.release()}")
    print(f"Run with '--dashboard-only' to view energy usage dashboard")
    
    app.launch_interface()

if __name__ == "__main__":
    main()
