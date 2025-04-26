import pytest
import os
import sys
import csv
import json
import platform
from datetime import datetime
from unittest.mock import patch, MagicMock

# Ensure the parent directory is in the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from energy_monitor import EnergyMonitor

@pytest.fixture
def mock_power_data():
    return {
        'type': 'macos',
        'cpu_utilization': 50.0,
        'memory_utilization': 70.0,
        'power_watts': 15.0
    }

@pytest.fixture
def energy_monitor():
    # Use a temporary directory for test logs
    test_log_dir = "/tmp/energy_test_logs"
    monitor = EnergyMonitor(log_dir=test_log_dir)
    yield monitor
    # Cleanup after tests
    if os.path.exists(test_log_dir):
        import shutil
        shutil.rmtree(test_log_dir)

@patch('energy_monitor.EnergyMonitor._get_power_usage')
def test_monitor_initialization(mock_power, energy_monitor):
    assert energy_monitor.start_power is None
    assert energy_monitor.end_power is None
    assert os.path.exists(energy_monitor.log_dir)
    assert os.path.exists(energy_monitor.csv_log_file)

@patch('energy_monitor.EnergyMonitor._get_power_usage')
def test_power_monitoring_cycle(mock_power, energy_monitor, mock_power_data):
    mock_power.return_value = mock_power_data
    
    # Test full monitoring cycle
    start_data = energy_monitor.start_monitoring()
    assert 'timestamp' in start_data
    assert start_data.get('power_watts') == 15.0
    
    # Simulate some work
    import time
    time.sleep(1)
    
    end_data = energy_monitor.end_monitoring()
    assert 'duration_seconds' in end_data
    assert end_data['duration_seconds'] >= 1.0
    assert end_data['system_type'] == platform.system()

@patch('energy_monitor.EnergyMonitor._get_power_usage')
def test_energy_logging(mock_power, energy_monitor, mock_power_data):
    mock_power.return_value = mock_power_data
    
    # Test logging functionality
    test_data = {
        'duration_seconds': 1.0,
        'energy_joules': 10.0,
        'energy_wh': 0.00277,
        'avg_power_watts': 10.0,
        'system_type': 'test'
    }
    
    energy_monitor.log_energy_usage(
        test_data,
        model="test_model",
        prompt="test prompt",
        response="test response"
    )
    
    # Verify CSV log - use correct attribute name
    assert os.path.exists(energy_monitor.csv_log_file)
    with open(energy_monitor.csv_log_file, 'r') as f:
        content = f.read()
        assert 'test_model' in content
        assert 'test' in content

@patch('energy_monitor.EnergyMonitor._get_power_usage')
def test_energy_summary(mock_power, energy_monitor, mock_power_data):
    mock_power.return_value = mock_power_data
    
    # Add some test data first
    test_data = {
        'duration_seconds': 1.0,
        'energy_joules': 10.0,
        'energy_wh': 0.00277,
        'avg_power_watts': 10.0,
        'system_type': 'test'
    }
    
    energy_monitor.log_energy_usage(
        test_data,
        model="test_model",
        prompt="test prompt",
        response="test response"
    )
    
    # Test summary generation
    summary = energy_monitor.get_energy_summary(days=1)
    assert isinstance(summary, dict)
    assert 'total_queries' in summary
    assert summary['total_queries'] > 0
