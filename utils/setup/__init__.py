"""Setup utilities for installing packages and creating directories."""

import sys
import subprocess
import pkg_resources
from pathlib import Path

def install_requirements(requirements_file: str):
    """Install packages from requirements file if not already installed."""
    with open(requirements_file) as f:
        requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    
    installed = {pkg.key for pkg in pkg_resources.working_set}
    missing = [pkg for pkg in requirements if pkg.split('==')[0] not in installed]
    
    if missing:
        print("📦 Installing packages...")
        try:
            # Capture output to suppress verbose pip messages
            result = subprocess.run(
                [sys.executable, '-m', 'pip', 'install', '--quiet'] + missing,
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                print("✅ Installation complete!")
            else:
                print("❌ Installation failed with errors:")
                # Only show error messages, not the full output
                for line in result.stderr.split('\n'):
                    if 'ERROR:' in line:
                        print(f"  {line.strip()}")
        except Exception as e:
            print(f"❌ Installation failed: {str(e)}")
    else:
        print("✅ All required packages are already installed!")

def setup_directories():
    """Create necessary directories if they don't exist."""
    directories = [
        'results',
        'datasets/rag_evaluation/labeled/data',
        'datasets/rag_evaluation/unlabeled/data',
        'rag_implementations/baseline_rag',
        'rag_implementations/graph_rag/graph_store'
    ]
    
    for directory in directories:
        path = Path(directory)
        if not path.exists():
            path.mkdir(parents=True)
            print(f"✅ Created directory: {directory}")
        else:
            print(f"✓ Directory exists: {directory}")

def test_imports():
    """Test importing all required modules."""
    try:
        # Core utilities
        import utils_setup
        from utils import RAGMetricsEvaluator, BenchmarkVisualizer, notebook_to_module
        print("✅ Core utilities imported successfully!")
        
        # Data science packages
        import pandas as pd
        import numpy as np
        import matplotlib.pyplot as plt
        import seaborn as sns
        print("✅ Data science packages imported successfully!")
        
        # AWS packages
        import boto3
        from botocore.exceptions import ClientError
        print("✅ AWS packages imported successfully!")
        
        # RAGAS packages
        from ragas import evaluate
        from ragas.metrics import (
            response_relevancy,
            context_precision,
            context_recall,
            faithfulness,
            ContextEntityRecall  # Using correct class name
        )
        print("✅ RAGAs evaluation framework imported successfully!")
        
        return True
    except Exception as e:
        print("❌ Error importing packages:")
        print(str(e))
        return False
