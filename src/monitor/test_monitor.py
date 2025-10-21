"""
Unit tests for the Monitor module.
Tests cover CPU, RAM, and GPU monitoring with mocks to simulate hardware.
"""

import unittest
from unittest.mock import patch
from monitor import Monitor
import os

class TestMonitor(unittest.TestCase): #extension of unittest.TestCase
    """Test suite for Monitor class functionality."""
    
    def setUp(self):
        """Initialize a basic monitor instance for testing (CPU and RAM only)."""
        self.monitor = Monitor(output_file="test_metrics.csv", interval=0.1, log_console=False, export_json=False, metrics=("cpu", "ram"), max_duration=0.3)

    def tearDown(self):
        """Clean up test files after each test.""" 
        if os.path.exists("test_metrics.csv"):
            os.remove("test_metrics.csv")
        if os.path.exists("test_metrics.json"):
            os.remove("test_metrics.json")
        if os.path.exists("test_gpu_metrics.csv"):
            os.remove("test_gpu_metrics.csv")

    def test_csv_output(self):
        """Test that CSV file is created and contains data."""
        self.monitor.run()
        self.assertTrue(os.path.exists("test_metrics.csv"))
        with open("test_metrics.csv") as f:
            lines = f.readlines()
        self.assertGreaterEqual(len(lines), 2)  # header + at least one row

    @patch("psutil.cpu_percent", return_value=40.0) # Simulate CPU usage at 40%
    @patch("psutil.virtual_memory")                 # Simulate RAM usage at 2 MB
    def test_metrics_values(self, mock_vm, mock_cpu):
        """Test that CPU and RAM values are correctly written to CSV."""
        mock_vm.return_value.used = 1024 * 1024 * 2  # 2 MB
        self.monitor.run()
        with open("test_metrics.csv") as f:
            last_line = f.readlines()[-1]
        self.assertIn("40.0", last_line)  # CPU percent
        self.assertIn("2", last_line)     # RAM in MB

    @patch("subprocess.check_output") # Checks for number of GPUs
    def test_gpu_count(self, mock_subprocess):
        """Test GPU detection and counting via mocked nvidia-smi."""
        # Mock nvidia-smi output for 2 GPUs
        mock_subprocess.return_value = "GPU 0\nGPU 1\n"
        monitor = Monitor(output_file="test_gpu_metrics.csv", interval=0.1, log_console=False, 
                         export_json=False, metrics=("gpu",), max_duration=0.3)
        self.assertEqual(monitor.gpu_count, 2)

    @patch("subprocess.check_output") # Mock GPU metrics retrieval
    def test_gpu_metrics(self, mock_subprocess):
        """Test GPU utilization and memory metrics with mocked nvidia-smi output."""
        # Mock nvidia-smi to return GPU count and then metrics
        def side_effect(*args, **kwargs):
            if "--query-gpu=name" in args[0]:
                return "Tesla V100\nTesla V100\n"
            elif "--query-gpu=utilization.gpu,memory.used" in args[0]:
                return "85, 12000\n90, 15000\n"
            return ""
        
        mock_subprocess.side_effect = side_effect
        monitor = Monitor(output_file="test_gpu_metrics.csv", interval=0.1, log_console=False,
                         export_json=False, metrics=("gpu",), max_duration=0.3)
        monitor.run()
        
        with open("test_gpu_metrics.csv") as f:
            lines = f.readlines()
            header = lines[0].strip()
            data_line = lines[1].strip()
        
        # Check header contains GPU columns for both GPUs
        self.assertIn("gpu0_util", header)
        self.assertIn("gpu0_mem_used", header)
        self.assertIn("gpu1_util", header)
        self.assertIn("gpu1_mem_used", header)
        
        # Check data contains GPU values (85% util, 12000 MB for GPU 0)
        self.assertIn("85", data_line)
        self.assertIn("12000", data_line)

    @patch("subprocess.check_output")
    def test_gpu_not_available(self, mock_subprocess):
        """Test behavior when nvidia-smi is not available (e.g., on Mac)."""
        # Simulate nvidia-smi not available
        mock_subprocess.side_effect = Exception("nvidia-smi not found")
        monitor = Monitor(output_file="test_gpu_metrics.csv", interval=0.1, log_console=False,
                         export_json=False, metrics=("gpu",), max_duration=0.3)
        self.assertEqual(monitor.gpu_count, 0)

    @patch("subprocess.check_output")
    @patch("psutil.cpu_percent", return_value=50.0)
    @patch("psutil.virtual_memory")
    def test_combined_metrics(self, mock_vm, mock_cpu, mock_subprocess):
        """Test monitoring all metrics together: GPU + CPU + RAM."""
        # Mock all metrics
        def side_effect(*args, **kwargs):
            if "--query-gpu=name" in args[0]:
                return "Tesla V100\n"
            elif "--query-gpu=utilization.gpu,memory.used" in args[0]:
                return "75, 10000\n"
            return ""
        
        mock_subprocess.side_effect = side_effect
        mock_vm.return_value.used = 1024 * 1024 * 4  # 4 MB
        
        monitor = Monitor(output_file="test_gpu_metrics.csv", interval=0.1, log_console=False,
                         export_json=False, metrics=("gpu", "cpu", "ram"), max_duration=0.3)
        monitor.run()
        
        with open("test_gpu_metrics.csv") as f:
            lines = f.readlines()
            header = lines[0].strip()
            data_line = lines[1].strip()
        
        # Check all metrics are present in header
        self.assertIn("gpu0_util", header)
        self.assertIn("cpu_percent", header)
        self.assertIn("ram_used_MB", header)
        # Check all values are present in data
        self.assertIn("75", data_line)    # GPU util for GPU 0
        self.assertIn("50.0", data_line)  # CPU percent
        self.assertIn("4", data_line)     # RAM in MB

if __name__ == "__main__":
    unittest.main()
