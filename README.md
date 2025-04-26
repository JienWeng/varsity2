# Eco-Friendly AI Chatbot

This project implements a Gradio-based AI chatbot with semantic caching, energy usage tracking, and integration with locally hosted Ollama LLMs.

## Features

- **Semantic Caching**: Uses sentence-transformers to cache similar prompts
- **Local Prompt History**: Maintains history of prompts and responses
- **Energy Monitoring**: Tracks power usage on various platforms
- **Energy Dashboard**: Visualize and analyze energy consumption
- **Ollama Integration**: Connects to locally hosted Ollama models
- **Gradio UI**: User-friendly interface with model selection and cache controls

## Installation

```bash
git clone [repository-url]
cd [repository-name]
pip install -r requirements.txt
```

## Usage

### Starting the Chatbot

```bash
python main.py --model llama2 --threshold 0.85
```

Arguments:
- `--model`: The Ollama model to use (default: llama2)
- `--threshold`: Semantic similarity threshold (default: 0.85)
- `--ollama-url`: URL for Ollama API (default: http://localhost:11434)
- `--monitoring-level`: Detail level for resource monitoring (basic/detailed)
- `--continuous-monitoring`: Enable continuous power monitoring
- `--log-dir`: Directory for energy usage logs

### Accessing the Energy Dashboard

Launch the dashboard in standalone mode:
```bash
python main.py --dashboard-only
```

Or access it while running the chatbot at:
```
http://localhost:7860/dashboard
```

The dashboard provides:
- Daily energy consumption graphs
- Model comparison charts
- Energy usage statistics
- Filtering by time period and model

### Energy Monitoring Features

The system supports multiple monitoring approaches:
- macOS: Uses powermetrics/smc for power readings
- NVIDIA GPUs: Uses nvidia-smi for power data
- Linux: Estimates based on CPU usage
- Fallback: CPU-based estimation when direct measurement isn't available

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-cov

# Add project root to PYTHONPATH
export PYTHONPATH=$PYTHONPATH:/path/to/varsity2

# Run tests
pytest tests/

# Run tests with coverage report
pytest tests/ --cov=./ --cov-report=term-missing
```

## Energy Data Analysis

Energy usage data is stored in:
- JSON format: `~/.energy_logs/energy_usage.json`
- CSV format: `~/.energy_logs/energy_usage.csv`

The data includes:
- Timestamp
- Model used
- Query details
- Energy consumption (joules/watt-hours)
- System metrics (CPU, memory usage)

## A/B Testing & Energy Comparison

### Dashboard Layout

The A/B testing dashboard is available at `http://localhost:7860/dashboard` and consists of four main panels:

1. **Top Left: Real-time Energy Comparison**
   ```
   ┌──────────────────────────┐
   │     Energy Usage (Wh)    │
   │                          │
   │  Cached    vs  Uncached  │
   │   3.2 Wh      7.8 Wh    │
   │   [Green]     [Red]      │
   └──────────────────────────┘
   ```

2. **Top Right: Response Time Graph**
   ```
   ┌──────────────────────────┐
   │    Response Time (ms)    │
   │                          │
   │     [Line Graph]         │
   │  Cached: ~500ms         │
   │  Uncached: ~1200ms      │
   └──────────────────────────┘
   ```

3. **Bottom Left: Environmental Impact**
   ```
   ┌──────────────────────────┐
   │   Carbon Savings         │
   │                          │
   │   Total: 0.5 kg CO2     │
   │   [Progress Chart]       │
   │   Trees Equivalent: 2.3  │
   └──────────────────────────┘
   ```

4. **Bottom Right: Cache Statistics**
   ```
   ┌──────────────────────────┐
   │   Cache Performance      │
   │                          │
   │   Hit Rate: 65%         │
   │   Energy Saved: 58%     │
   │   Time Saved: 62%       │
   └──────────────────────────┘
   ```

### Viewing A/B Test Results

1. Start the chatbot with A/B testing enabled:
   ```bash
   python main.py --enable-ab-testing --continuous-monitoring
   ```

2. Access the dashboard in one of two ways:
   - Open a new browser tab to `http://localhost:7860/dashboard`
   - Use dashboard-only mode: `python main.py --dashboard-only`

3. Use the dashboard controls:
   - Time Range Selector: [Last Hour | Day | Week | Month]
   - Model Filter: Select specific models to compare
   - Metrics Toggle: [Energy | Time | Carbon | All]
   - Export Data: Download CSV/JSON reports

### Real-time Monitoring Example

When you send a prompt:
```
User: "What is Python?"

Dashboard Updates:
- Cache Miss → Full LLM query: ~7.8 Wh
- Next similar query → Cache Hit: ~3.2 Wh
- Savings displayed in real-time
- Carbon impact calculated instantly
```

### Keyboard Shortcuts

- `Ctrl/Cmd + R`: Refresh dashboard
- `Ctrl/Cmd + E`: Export current view
- `Space`: Toggle between cached/uncached views
- `T`: Switch time ranges

### Side-by-Side Comparison Mode

Launch the chatbot in side-by-side comparison mode to directly compare cached vs. non-cached performance:

```bash
python main.py --comparison-mode
```

This provides:
- Two chat interfaces side by side
- Real-time energy usage monitoring for each
- Direct performance comparison
- Same prompts can be tested with and without caching

Example comparison:
```
┌─────────────────┐ ┌─────────────────┐
│   With Cache    │ │  Without Cache  │
│                 │ │                 │
│ [Chat Interface]│ │ [Chat Interface]│
│                 │ │                 │
│ Energy: 3.2 Wh  │ │ Energy: 7.8 Wh  │
│ Time: 0.5s     │ │ Time: 1.2s     │
└─────────────────┘ └─────────────────┘
```

## Contributing

1. Fork the repository
2. Create your feature branch
3. Add tests for new features
4. Submit a pull request

## License

[Your chosen license]
