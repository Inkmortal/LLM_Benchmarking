"""
Utilities for LLM benchmarking, including metrics, visualization, and notebook imports.
"""

# Defer imports until after setup is complete
__all__ = []

def _setup_imports():
    """Import utilities after requirements are installed."""
    global __all__
    try:
        from utils.metrics.rag_metrics import RAGMetricsEvaluator
        from utils.visualization.comparison_plots import BenchmarkVisualizer
        from utils.notebook_utils.importable import notebook_to_module, NotebookLoader
        
        __all__ = [
            'RAGMetricsEvaluator',
            'BenchmarkVisualizer',
            'notebook_to_module',
            'NotebookLoader'
        ]
    except ImportError:
        # During setup, these imports may fail which is expected
        pass

_setup_imports()
