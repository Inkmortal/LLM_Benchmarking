"""Setup utilities for installing packages and creating directories."""

import sys
import subprocess
import pkg_resources
from pathlib import Path
from tqdm import tqdm

def install_spacy():
    """Install spacy and its dependencies separately."""
    print("📦 Installing spacy and dependencies...")
    try:
        # Install spacy core dependencies first
        dependencies = [
            "wasabi>=0.9.1",
            "srsly>=2.4.3",
            "catalogue>=2.0.6",
            "typer>=0.3.0",
            "pathy>=0.3.5",
            "smart-open>=5.2.1",
            "murmurhash>=1.0.2",
            "cymem>=2.0.2",
            "preshed>=3.0.2",
            "thinc>=8.1.0"
        ]
        
        for dep in dependencies:
            result = subprocess.run(
                [sys.executable, '-m', 'pip', 'install', '--progress-bar', 'off', dep],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                print(f"\n❌ Failed to install spacy dependency {dep}:")
                print(result.stderr)
                return False
                
        # Now install spacy
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'install', '--progress-bar', 'off', 'spacy==3.7.2'],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print("\n❌ Failed to install spacy:")
            print(result.stderr)
            return False
            
        print("✅ Successfully installed spacy and dependencies!")
        return True
        
    except Exception as e:
        print(f"\n❌ Failed to install spacy: {str(e)}")
        return False

def install_requirements(requirements_file: str):
    """Install packages from requirements file if not already installed."""
    print("[DEBUG] Starting install_requirements function")
    with open(requirements_file) as f:
        requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    
    print(f"[DEBUG] Found {len(requirements)} requirements in file")
    installed = {pkg.key for pkg in pkg_resources.working_set}
    
    # Filter out spacy and its dependencies as we'll handle them separately
    spacy_deps = {'spacy', 'wasabi', 'srsly', 'catalogue', 'typer', 'pathy', 
                 'smart-open', 'murmurhash', 'cymem', 'preshed', 'thinc'}
    missing = [pkg for pkg in requirements 
              if pkg.split('==')[0] not in installed 
              and pkg.split('==')[0] not in spacy_deps]
    
    if missing:
        print("📦 Installing missing packages...")
        print(f"[DEBUG] Found {len(missing)} missing packages")
        
        # Configure progress bar style
        with tqdm(
            total=len(missing),
            desc="Installing packages",
            unit="pkg",
            bar_format="{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}{postfix}]"
        ) as pbar:
            for package in missing:
                try:
                    result = subprocess.run(
                        [sys.executable, '-m', 'pip', 'install', '--progress-bar', 'off', package],
                        capture_output=True,
                        text=True
                    )
                    
                    if result.returncode != 0:
                        print(f"\n❌ Failed to install {package}:")
                        for line in result.stderr.split('\n'):
                            if 'ERROR:' in line:
                                print(f"  {line.strip()}")
                        print("[DEBUG] Returning False due to non-zero return code")
                        return False
                    
                    pbar.set_postfix_str(f"Installed {package}")
                    pbar.update(1)
                        
                except Exception as e:
                    print(f"\n❌ Installation failed for {package}: {str(e)}")
                    print("[DEBUG] Returning False due to exception")
                    return False
        
        # After installing other packages, handle spacy separately
        if not install_spacy():
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
