import subprocess
import time
import platform
import os
import csv
import json
from datetime import datetime
from typing import Dict, Optional, Tuple

class EnergyMonitor:
    def __init__(self, log_dir: str = None):
        """
        Initialize the energy monitor for tracking resource usage
        
        Args:
            log_dir: Directory to store energy usage logs (defaults to ~/.energy_logs)
        """
        self.start_power = None
        self.start_time = None
        self.end_power = None
        self.end_time = None
        self.system = platform.system()  # 'Darwin' for macOS, 'Linux' for Linux, 'Windows' for Windows
        self.powermetrics_process = None
        self.power_readings = []
        
        # Set up logging directory
        if log_dir is None:
            self.log_dir = os.path.expanduser("~/.energy_logs")
        else:
            self.log_dir = log_dir
        
        # Create log directory if it doesn't exist
        os.makedirs(self.log_dir, exist_ok=True)
        
        # Define log files
        self.json_log_file = os.path.join(self.log_dir, "energy_usage.json")
        self.csv_log_file = os.path.join(self.log_dir, "energy_usage.csv")
        
        # Initialize CSV file with headers if it doesn't exist
        if not os.path.exists(self.csv_log_file):
            with open(self.csv_log_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp', 'model', 'prompt_length', 'response_length', 
                    'duration_seconds', 'energy_joules', 'energy_wh', 
                    'avg_power_watts', 'system_type'
                ])
    
    def _check_nvidia_smi(self) -> bool:
        """Check if nvidia-smi is available"""
        try:
            result = subprocess.run(
                ["nvidia-smi"], 
                capture_output=True, 
                text=True, 
                check=False
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False
    
    def _get_power_usage(self) -> Optional[Dict]:
        """
        Get current resource usage.
        Returns a dictionary with available metrics or None if not available.
        """
        # Try NVIDIA GPU if available
        if self._check_nvidia_smi():
            try:
                result = subprocess.run(
                    ["nvidia-smi", "--query-gpu=power.draw", "--format=csv,noheader"],
                    capture_output=True,
                    text=True,
                    check=True
                )
                power_usage = result.stdout.strip().split('\n')
                power_usage = [float(x.split()[0]) for x in power_usage if x]
                if power_usage:
                    avg_power = sum(power_usage) / len(power_usage)
                    return {
                        'type': 'nvidia_gpu',
                        'power_watts': avg_power
                    }
            except Exception as e:
                print(f"Error getting NVIDIA metrics: {e}")
                pass
        
        # For macOS
        if self.system == 'Darwin':
            try:
                power_value = self._get_macos_power_reading()
                cpu_usage = self._get_cpu_usage()
                memory_usage = self._get_memory_usage()
                
                return {
                    'type': 'macos',
                    'cpu_utilization': cpu_usage,
                    'memory_utilization': memory_usage,
                    'power_watts': power_value
                }
            except Exception as e:
                print(f"Error getting macOS metrics: {e}")
                
        return {
            'type': 'generic',
            'timestamp': datetime.now().isoformat()
        }
        
    def _get_macos_power_reading(self) -> Optional[float]:
        """Get CPU power reading on macOS using powermetrics"""
        try:
            # Use a simpler powermetrics command that doesn't require elevated privileges
            result = subprocess.run(
                ["powermetrics", "--samplers", "cpu_power", "-n", "1", "-i", "100"],
                capture_output=True,
                text=True,
                check=False,
                timeout=3  # Timeout after 3 seconds
            )
            
            if result.returncode != 0:
                # Try alternate approach with smc command if available
                try:
                    # Some Macs have smc command available
                    smc_result = subprocess.run(
                        ["smc", "-k", "PCPT", "-r"],
                        capture_output=True,
                        text=True,
                        check=False
                    )
                    
                    if smc_result.returncode == 0 and "PCPT" in smc_result.stdout:
                        power_parts = smc_result.stdout.strip().split()
                        for i, part in enumerate(power_parts):
                            if part == "PCPT" and i + 2 < len(power_parts):
                                try:
                                    power_value = float(power_parts[i+2])
                                    return power_value
                                except ValueError:
                                    pass
                except (subprocess.SubprocessError, FileNotFoundError):
                    # If smc also fails, try using top to estimate CPU load
                    top_result = subprocess.run(
                        ["top", "-l", "1", "-n", "0", "-stats", "cpu"],
                        capture_output=True,
                        text=True,
                        check=True
                    )
                    
                    # Extract CPU usage and roughly estimate power
                    cpu_usage = None
                    for line in top_result.stdout.split('\n'):
                        if 'CPU usage' in line:
                            parts = line.split(':')[1].strip().split(',')
                            user = float(parts[0].strip().replace('%', '').replace('user', '').strip())
                            sys = float(parts[1].strip().replace('%', '').replace('sys', '').strip())
                            cpu_usage = user + sys
                            
                            # Rough estimate: 10W at 100% CPU for laptops, scale linearly
                            # This is a very rough approximation!
                            return (cpu_usage / 100.0) * 10.0
                
                # If all else fails, return None
                return None
            
            # Parse powermetrics output if successful
            power_value = None
            for line in result.stdout.split('\n'):
                if 'CPU Power' in line:
                    # Extract power value (in mW, convert to W)
                    parts = line.split(':')
                    if len(parts) >= 2:
                        power_str = parts[1].strip().split()[0]  # Get the number part
                        try:
                            power_value = float(power_str) / 1000.0  # Convert mW to W
                            return power_value
                        except (ValueError, IndexError):
                            pass
            return None
        except (subprocess.SubprocessError, subprocess.TimeoutExpired) as e:
            print(f"Warning: Could not get power data: {e}")
            # Fallback to CPU usage as rough estimate
            try:
                top_result = subprocess.run(
                    ["top", "-l", "1", "-n", "0", "-stats", "cpu"],
                    capture_output=True,
                    text=True,
                    check=True
                )
                
                # Extract CPU usage and roughly estimate power
                for line in top_result.stdout.split('\n'):
                    if 'CPU usage' in line:
                        parts = line.split(':')[1].strip().split(',')
                        user = float(parts[0].strip().replace('%', '').replace('user', '').strip())
                        sys = float(parts[1].strip().replace('%', '').replace('sys', '').strip())
                        cpu_usage = user + sys
                        
                        # Rough estimate: 10W at 100% CPU for laptops, scale linearly
                        return (cpu_usage / 100.0) * 10.0
            except:
                pass
            return None
    
    def _get_cpu_usage(self) -> Optional[float]:
        """Get CPU usage percentage"""
        try:
            top_result = subprocess.run(
                ["top", "-l", "1", "-n", "0", "-stats", "cpu"],
                capture_output=True,
                text=True,
                check=True
            )
            
            for line in top_result.stdout.split('\n'):
                if 'CPU usage' in line:
                    parts = line.split(':')[1].strip().split(',')
                    user = float(parts[0].strip().replace('%', '').replace('user', '').strip())
                    sys = float(parts[1].strip().replace('%', '').replace('sys', '').strip())
                    return user + sys
        except:
            pass
        return None
        
    def _get_memory_usage(self) -> Optional[float]:
        """Get memory usage percentage"""
        try:
            if self.system == 'Darwin':
                vm_stat = subprocess.run(
                    ["vm_stat"],
                    capture_output=True,
                    text=True,
                    check=True
                )
                
                page_size = 4096
                free_pages = 0
                total_pages = 0
                
                for line in vm_stat.stdout.split('\n'):
                    if 'Pages free' in line:
                        free_pages = int(line.split(':')[1].strip().replace('.', ''))
                    elif any(x in line for x in ['Pages active', 'Pages inactive', 'Pages speculative', 'Pages wired down']):
                        total_pages += int(line.split(':')[1].strip().replace('.', ''))
                
                total_pages += free_pages
                return (total_pages - free_pages) / total_pages * 100 if total_pages > 0 else 0
        except:
            pass
        return None

    def _start_continuous_power_monitoring(self):
        """Start continuous power monitoring in the background (for macOS)"""
        if self.system == 'Darwin':
            try:
                # Create a directory to store the readings if it doesn't exist
                os.makedirs(os.path.expanduser("~/.power_monitor"), exist_ok=True)
                output_file = os.path.expanduser("~/.power_monitor/power_readings.txt")
                
                # Clear any existing file
                with open(output_file, 'w') as f:
                    f.write("")
                
                # Use top command to monitor CPU usage instead of powermetrics
                # This avoids permission issues
                cmd = f"top -l 86400 -s 1 -stats cpu | grep 'CPU usage' > {output_file} &"
                subprocess.Popen(cmd, shell=True)
                return True
            except Exception as e:
                print(f"Error starting continuous power monitoring: {e}")
                return False
        return False
    
    def _stop_continuous_power_monitoring(self):
        """Stop continuous power monitoring and collect average power"""
        if self.system == 'Darwin':
            try:
                # Kill the monitoring process
                subprocess.run(
                    ["pkill", "-f", "top -l 86400"],
                    capture_output=True,
                    check=False
                )
                
                # Read the CPU usage readings and estimate power
                output_file = os.path.expanduser("~/.power_monitor/power_readings.txt")
                if os.path.exists(output_file):
                    power_values = []
                    with open(output_file, 'r') as f:
                        for line in f:
                            if 'CPU usage' in line:
                                parts = line.split(':')[1].strip().split(',')
                                try:
                                    user = float(parts[0].strip().replace('%', '').replace('user', '').strip())
                                    sys = float(parts[1].strip().replace('%', '').replace('sys', '').strip())
                                    cpu_usage = user + sys
                                    
                                    # Rough estimate: 10W at 100% CPU for laptops, scale linearly
                                    power_values.append((cpu_usage / 100.0) * 10.0)
                                except (ValueError, IndexError):
                                    pass
                    
                    # Calculate average power
                    if power_values:
                        return sum(power_values) / len(power_values)
            except Exception as e:
                print(f"Error stopping continuous power monitoring: {e}")
        return None
    
    def start_monitoring(self) -> Dict:
        """Start monitoring resource usage"""
        self.start_time = datetime.now()
        self.power_readings = []  # Reset readings
        
        # Get initial power reading
        self.start_power = self._get_power_usage()
        
        # Start continuous monitoring on macOS
        if self.system == 'Darwin':
            self._start_continuous_power_monitoring()
        
        result = {
            'timestamp': self.start_time.isoformat()
        }
        
        if self.start_power:
            result.update(self.start_power)
            
        return result
    
    def end_monitoring(self) -> Dict:
        """End monitoring and return resource usage statistics"""
        self.end_time = datetime.now()
        
        # Get final power reading
        self.end_power = self._get_power_usage()
        
        # Get average power from continuous monitoring
        avg_power = None
        if self.system == 'Darwin':
            avg_power = self._stop_continuous_power_monitoring()
        
        duration_seconds = (self.end_time - self.start_time).total_seconds() if self.start_time else 0
        
        result = {
            'start_timestamp': self.start_time.isoformat() if self.start_time else None,
            'end_timestamp': self.end_time.isoformat(),
            'duration_seconds': duration_seconds,
            'system_type': self.system
        }
        
        # Add specific metrics based on what's available
        if self.start_power and self.end_power:
            start_type = self.start_power.get('type')
            end_type = self.end_power.get('type')
            
            # Only compare metrics if the same monitoring type was used
            if start_type == end_type:
                if start_type == 'nvidia_gpu':
                    avg_power = (self.start_power.get('power_watts', 0) + self.end_power.get('power_watts', 0)) / 2
                    result.update({
                        'start_power_watts': self.start_power.get('power_watts'),
                        'end_power_watts': self.end_power.get('power_watts'),
                        'avg_power_watts': avg_power,
                        'energy_joules': avg_power * duration_seconds,
                        'energy_wh': avg_power * duration_seconds / 3600 if avg_power is not None else None
                    })
                elif start_type == 'macos' or start_type == 'linux':
                    result.update({
                        'start_cpu_utilization': self.start_power.get('cpu_utilization'),
                        'end_cpu_utilization': self.end_power.get('cpu_utilization'),
                        'start_memory_utilization': self.start_power.get('memory_utilization'),
                        'end_memory_utilization': self.end_power.get('memory_utilization')
                    })
                    
                    # Use continuous monitoring average power if available
                    power_start = self.start_power.get('power_watts')
                    power_end = self.end_power.get('power_watts')
                    
                    if avg_power is not None:
                        result.update({
                            'start_power_watts': power_start,
                            'end_power_watts': power_end,
                            'avg_power_watts': avg_power,
                            'energy_joules': avg_power * duration_seconds,
                            'energy_wh': avg_power * duration_seconds / 3600 if avg_power is not None else None
                        })
                    elif power_start is not None and power_end is not None:
                        avg_p = (power_start + power_end) / 2
                        result.update({
                            'start_power_watts': power_start,
                            'end_power_watts': power_end,
                            'avg_power_watts': avg_p,
                            'energy_joules': avg_p * duration_seconds,
                            'energy_wh': avg_p * duration_seconds / 3600
                        })
        
        return result
    
    def log_energy_usage(self, energy_data: Dict, model: str = None, prompt: str = None, response: str = None) -> None:
        """
        Log energy usage data for dashboard and analysis
        
        Args:
            energy_data: Dictionary with energy usage data
            model: Model name (e.g., llama3.2)
            prompt: User prompt
            response: LLM response
        """
        # Skip logging if no energy data
        if not energy_data:
            return
        
        timestamp = datetime.now().isoformat()
        
        # Prepare log entry
        log_entry = {
            'timestamp': timestamp,
            'energy_data': energy_data,
            'model': model,
            'prompt_length': len(prompt) if prompt else None,
            'response_length': len(response) if response else None,
            'system_info': {
                'system': platform.system(),
                'machine': platform.machine(),
                'version': platform.version()
            }
        }
        
        # Log to JSON file (append)
        try:
            existing_data = []
            if os.path.exists(self.json_log_file):
                try:
                    with open(self.json_log_file, 'r') as f:
                        existing_data = json.load(f)
                except json.JSONDecodeError:
                    existing_data = []
            
            if not isinstance(existing_data, list):
                existing_data = []
                
            existing_data.append(log_entry)
            
            with open(self.json_log_file, 'w') as f:
                json.dump(existing_data, f, indent=2)
        except Exception as e:
            print(f"Error logging energy data to JSON: {e}")
        
        # Log to CSV file (append)
        try:
            energy_joules = energy_data.get('energy_joules')
            energy_wh = energy_data.get('energy_wh')
            avg_power = energy_data.get('avg_power_watts')
            duration = energy_data.get('duration_seconds')
            system_type = energy_data.get('system_type')
            
            with open(self.csv_log_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    timestamp,
                    model,
                    log_entry['prompt_length'],
                    log_entry['response_length'],
                    duration,
                    energy_joules,
                    energy_wh,
                    avg_power,
                    system_type
                ])
        except Exception as e:
            print(f"Error logging energy data to CSV: {e}")
    
    def get_energy_summary(self, model: str = None, days: int = 7) -> Dict:
        """
        Get summary of energy usage
        
        Args:
            model: Filter by specific model
            days: Number of days to include in summary
            
        Returns:
            Dictionary with energy usage summary
        """
        try:
            if not os.path.exists(self.csv_log_file):
                return {"error": "No energy data available"}
                
            # Read CSV file
            data = []
            with open(self.csv_log_file, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    data.append(row)
            
            # Filter by time period
            cutoff_date = datetime.now().timestamp() - (days * 24 * 60 * 60)  # days in seconds
            filtered_data = []
            
            for entry in data:
                try:
                    entry_time = datetime.fromisoformat(entry['timestamp']).timestamp()
                    
                    # Filter by time and model (if specified)
                    if entry_time >= cutoff_date:
                        if model is None or entry['model'] == model:
                            filtered_data.append(entry)
                except (ValueError, KeyError):
                    continue
            
            # Calculate statistics
            total_energy_joules = 0
            total_energy_wh = 0
            total_duration = 0
            count = len(filtered_data)
            
            for entry in filtered_data:
                try:
                    if entry.get('energy_joules') and entry['energy_joules'] != '':
                        total_energy_joules += float(entry['energy_joules'])
                    
                    if entry.get('energy_wh') and entry['energy_wh'] != '':
                        total_energy_wh += float(entry['energy_wh'])
                    
                    if entry.get('duration_seconds') and entry['duration_seconds'] != '':
                        total_duration += float(entry['duration_seconds'])
                except (ValueError, KeyError, TypeError):
                    continue
            
            # Group by model
            models = {}
            for entry in filtered_data:
                model_name = entry.get('model', 'unknown')
                
                if model_name not in models:
                    models[model_name] = {
                        'count': 0,
                        'energy_joules': 0,
                        'energy_wh': 0,
                        'duration': 0
                    }
                
                models[model_name]['count'] += 1
                
                try:
                    if entry.get('energy_joules') and entry['energy_joules'] != '':
                        models[model_name]['energy_joules'] += float(entry['energy_joules'])
                    
                    if entry.get('energy_wh') and entry['energy_wh'] != '':
                        models[model_name]['energy_wh'] += float(entry['energy_wh'])
                    
                    if entry.get('duration_seconds') and entry['duration_seconds'] != '':
                        models[model_name]['duration'] += float(entry['duration_seconds'])
                except (ValueError, KeyError, TypeError):
                    continue
            
            return {
                'total_queries': count,
                'total_energy_joules': total_energy_joules,
                'total_energy_wh': total_energy_wh,
                'total_duration_seconds': total_duration,
                'average_energy_per_query_joules': total_energy_joules / count if count > 0 else 0,
                'average_energy_per_query_wh': total_energy_wh / count if count > 0 else 0,
                'average_duration_seconds': total_duration / count if count > 0 else 0,
                'by_model': models,
                'days': days
            }
            
        except Exception as e:
            return {"error": f"Error generating energy summary: {e}"}
