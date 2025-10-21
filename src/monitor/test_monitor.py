import unittest
from unittest.mock import patch, MagicMock
from monitor import Monitor
import os

class TestMonitor(unittest.TestCase):
    def setUp(self):
        self.monitor = Monitor(output_file="test_metrics.csv", interval=0.1, log_console=False, export_json=False, metrics=("cpu", "ram"), max_duration=0.3)

    def tearDown(self):
        # Clean up test files
        if os.path.exists("test_metrics.csv"):
            os.remove("test_metrics.csv")
        if os.path.exists("test_metrics.json"):
            os.remove("test_metrics.json")
        if os.path.exists("test_gpu_metrics.csv"):
            os.remove("test_gpu_metrics.csv")

    def test_csv_output(self):
        self.monitor.run()
        self.assertTrue(os.path.exists("test_metrics.csv"))
        with open("test_metrics.csv") as f:
            lines = f.readlines()
        self.assertGreaterEqual(len(lines), 2)  # header + at least one row

    @patch("psutil.cpu_percent", return_value=42.0)
    @patch("psutil.virtual_memory")
    def test_metrics_values(self, mock_vm, mock_cpu):
        mock_vm.return_value.used = 1024 * 1024 * 2  # 2 MB
        self.monitor.run()
        with open("test_metrics.csv") as f:
            last_line = f.readlines()[-1]
        self.assertIn("42.0", last_line)
        self.assertIn("2", last_line)

    @patch("subprocess.check_output")
    def test_gpu_count(self, mock_subprocess):
        # Mock nvidia-smi output for 2 GPUs
        mock_subprocess.return_value = "GPU 0\nGPU 1\n"
        monitor = Monitor(output_file="test_gpu_metrics.csv", interval=0.1, log_console=False, 
                         export_json=False, metrics=("gpu",), max_duration=0.3)
        self.assertEqual(monitor.gpu_count, 2)

    @patch("subprocess.check_output")
    def test_gpu_metrics(self, mock_subprocess):
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
        
        # Check header contains GPU columns
        self.assertIn("gpu0_util", header)
        self.assertIn("gpu0_mem_used", header)
        self.assertIn("gpu1_util", header)
        self.assertIn("gpu1_mem_used", header)
        
        # Check data contains GPU values
        self.assertIn("85", data_line)
        self.assertIn("12000", data_line)

    @patch("subprocess.check_output")
    def test_gpu_not_available(self, mock_subprocess):
        # Simulate nvidia-smi not available
        mock_subprocess.side_effect = Exception("nvidia-smi not found")
        monitor = Monitor(output_file="test_gpu_metrics.csv", interval=0.1, log_console=False,
                         export_json=False, metrics=("gpu",), max_duration=0.3)
        self.assertEqual(monitor.gpu_count, 0)

    @patch("subprocess.check_output")
    @patch("psutil.cpu_percent", return_value=50.0)
    @patch("psutil.virtual_memory")
    def test_combined_metrics(self, mock_vm, mock_cpu, mock_subprocess):
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
        
        # Check all metrics are present
        self.assertIn("gpu0_util", header)
        self.assertIn("cpu_percent", header)
        self.assertIn("ram_used_MB", header)
        self.assertIn("75", data_line)
        self.assertIn("50.0", data_line)
        self.assertIn("4", data_line)

if __name__ == "__main__":
    unittest.main()
