"""
Setup script to make utils package importable from anywhere.
Run this at the start of your notebooks:

import utils_setup
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.absolute()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Import commonly used utilities
from utils.metrics.rag_metrics import RAGMetricsEvaluator
from utils.visualization.comparison_plots import BenchmarkVisualizer
from utils.notebook_utils.importable import notebook_to_module, NotebookLoader

# Make utilities available at module level
__all__ = [
    'RAGMetricsEvaluator',
    'BenchmarkVisualizer',
    'notebook_to_module',
    'NotebookLoader'
]
