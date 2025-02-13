"""Setup utilities for installing packages and creating directories."""

import sys
import subprocess
import pkg_resources
from pathlib import Path
from tqdm import tqdm

def install_requirements(requirements_file: str):
    """Install packages from requirements file if not already installed."""
    with open(requirements_file) as f:
        requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    
    installed = {pkg.key for pkg in pkg_resources.working_set}
    missing = [pkg for pkg in requirements if pkg.split('==')[0] not in installed]
    
    if missing:
        print("📦 Installing missing packages...")
        print(f"[DEBUG] Found {len(missing)} missing packages")
        
        for package in missing:
            print(f"\nInstalling {package}...")
            try:
                # Create progress bar for current package
                with tqdm(total=1, desc=f"Progress", leave=False) as pbar:
                    result = subprocess.run(
                        [sys.executable, '-m', 'pip', 'install', '--progress-bar', 'off', package],
                        capture_output=True,
                        text=True
                    )
                    pbar.update(1)  # Complete the progress bar
                    
                if result.returncode != 0:
                    print(f"❌ Failed to install {package}:")
                    for line in result.stderr.split('\n'):
                        if 'ERROR:' in line:
                            print(f"  {line.strip()}")
                    print("[DEBUG] Returning False due to non-zero return code")
                    return False
                    
            except Exception as e:
                print(f"❌ Installation failed for {package}: {str(e)}")
                print("[DEBUG] Returning False due to exception")
                return False
                
        print("\n📦 Successfully installed all missing packages!")
        print("[DEBUG] Returning True after installing packages")
        return True
    else:
        print("📦 All required packages are already installed!")
        print("[DEBUG] Returning True as no packages need installing")
        return True

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
            ResponseRelevancy,
            ContextPrecision,
            ContextRecall,
            Faithfulness,
            ContextEntityRecall
        )
        print("✅ RAGAs evaluation framework imported successfully!")
        
        # Only import utils after all requirements are installed
        import utils
        print("✅ Core utilities imported successfully!")
        
        return True
    except Exception as e:
        print("❌ Error importing packages:")
        print(str(e))
        return False
