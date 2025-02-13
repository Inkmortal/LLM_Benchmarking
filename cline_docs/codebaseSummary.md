# Codebase Summary

## Project Structure
```
LLM_Benchmarking/
├── datasets/
│   ├── rag_evaluation/
│   │   ├── labeled/                     # Labeled datasets for RAG evaluation
│   │   │   └── dataset_info.md          # Documentation of dataset structure
│   │   └── unlabeled/                   # Unlabeled datasets for RAG evaluation
│   │       └── dataset_info.md
│   │
│   └── sql_evaluation/                  # Future SQL evaluation datasets
│       ├── labeled/
│       └── unlabeled/
│
├── rag_implementations/
│   ├── baseline_rag/
│   │   ├── implementation.ipynb         # Core baseline RAG implementation
│   │   └── ingestion.ipynb             # Data ingestion and preprocessing
│   │
│   └── graph_rag/
│       ├── implementation.ipynb         # Core GraphRAG implementation
│       ├── ingestion.ipynb             # Graph-specific ingestion
│       └── graph_store/                # For storing processed graph data
│
├── evaluation_pipelines/
│   ├── templates/
│   │   ├── rag_comparison.ipynb        # Template for comparing RAG implementations
│   │   └── rag_tuning.ipynb           # Template for single implementation tuning
│   │
│   ├── rag_evaluations/
│   │   ├── implementation_comparisons/
│   │   │   └── baseline_vs_graph/      # Example using comparison template
│   │   │       ├── comparison.ipynb    
│   │   │       └── results/
│   │   │
│   │   └── implementation_tuning/
│   │       ├── baseline_rag_tuning/    # Tuning baseline RAG parameters
│   │       │   ├── tuning.ipynb
│   │       │   └── results/
│   │       │
│   │       └── graph_rag_tuning/       # Tuning GraphRAG parameters
│   │           ├── tuning.ipynb
│   │           └── results/
│   │
│   └── sql_evaluations/                # Future SQL evaluation pipelines
│
└── utils/
    ├── metrics/
    │   ├── rag_metrics.py              # RAG evaluation metrics
    │   └── sql_metrics.py              # Future SQL metrics
    │
    ├── notebook_utils/
    │   └── importable.py               # Makes notebooks importable as modules
    │
    └── visualization/
        └── comparison_plots.py         # Visualization utilities
```

## Key Components and Their Interactions

### 1. RAG Implementations
- Separate ingestion and implementation notebooks
- AWS service integration:
  - OpenSearch for vector storage
  - Neptune for graph database
  - Bedrock for LLM and embeddings
- Standardized interfaces for evaluation

### 2. Evaluation Pipelines
- Templates for comparison and tuning
- Support for different evaluation scenarios
- Results storage and visualization
- CloudWatch integration for performance monitoring

### 3. Datasets
- Organized by evaluation type (RAG, SQL)
- Separated labeled and unlabeled data
- S3 integration for data storage

### 4. Utilities
- Metrics calculation using RAGAs
- AWS service integration utilities
- Visualization tools
- Notebook import functionality

## Data Flow

### 1. Data Ingestion
- Raw documents → S3 storage
- Processing through AWS services:
  - Text extraction and chunking
  - Vector embedding via Bedrock
  - Storage in OpenSearch/Neptune

### 2. Evaluation Flow
- Load implementations
- Process test datasets
- Calculate metrics via RAGAs
- Store results and visualizations
- Monitor performance with CloudWatch

## External Dependencies
- AWS Services (Bedrock, OpenSearch, Neptune, S3)
- RAGAs evaluation framework
- Python utilities and visualization libraries

## Recent Changes
- Initial project setup
- Architecture design
- Documentation creation

## Notes
- All AWS services should be configured in the same account
- Proper IAM roles and permissions required
- Notebooks should include AWS credentials management
