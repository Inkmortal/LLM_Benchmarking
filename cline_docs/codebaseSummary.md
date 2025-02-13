# Codebase Summary

## Project Structure
```
LLM_Benchmarking/
├── datasets/
│   ├── rag_evaluation/
│   │   ├── labeled/                     # Labeled datasets for RAG evaluation
│   │   │   ├── dataset_info.md         # Documentation of dataset structure
│   │   │   └── covid19_origin/         # Origin of Covid-19 dataset
│   │   │       ├── rag_dataset.json    # Dataset examples (git-ignored)
│   │   │       └── source_files/       # Source documents (git-ignored)
│   │   └── unlabeled/                  # Unlabeled datasets for RAG evaluation
│   │       └── dataset_info.md
│
├── rag_implementations/
│   ├── baseline_rag/
│   │   ├── implementation.ipynb        # Core baseline RAG implementation
│   │   └── ingestion.ipynb            # Generic document ingestion
│   │
│   └── graph_rag/                      # Future GraphRAG implementation
│       ├── implementation.ipynb
│       ├── ingestion.ipynb
│       └── graph_store/               # For storing processed graph data
│
├── evaluation_pipelines/
│   ├── templates/
│   │   ├── rag_comparison.ipynb       # Template for comparing RAG implementations
│   │   └── rag_tuning.ipynb          # Template for single implementation tuning
│   │
│   └── rag_evaluations/
│       └── baseline_rag_benchmark.ipynb # Baseline RAG evaluation with dataset examination
│
└── utils/
    ├── metrics/
    │   └── rag_metrics.py            # RAG evaluation metrics with RAGAs
    │
    ├── notebook_utils/
    │   ├── importable.py             # Makes notebooks importable as modules
    │   ├── dataset_utils.py          # Dataset downloading and examination
    │   └── document_utils.py         # Document preprocessing and ingestion
    │
    └── visualization/
        └── comparison_plots.py       # Visualization utilities
```

## Key Components and Their Interactions

### 1. Baseline RAG Implementation
- Generic document ingestion with:
  - Text cleaning and normalization
  - Configurable chunking
  - Metadata preservation
  - Batch processing
- AWS service integration:
  - OpenSearch for vector storage
  - Bedrock for embeddings and LLM
- Standardized interfaces for evaluation

### 2. Dataset Management
- Support for Llama datasets:
  - Automatic downloading
  - Local caching
  - Source file management
- Vector store integration:
  - Document ingestion tracking
  - Embedding caching
  - Batch processing

### 3. Evaluation Framework
- Comprehensive metrics using RAGAs:
  - Faithfulness scoring
  - Context precision and recall
  - Response relevancy
  - Context entity recall
  - Noise sensitivity
- Support for:
  - Labeled dataset evaluation
  - Unlabeled dataset evaluation
  - Batch processing with rate limiting
  - Custom query testing
- Document preprocessing:
  - Text cleaning and normalization
  - Smart chunking with overlap
  - Metadata preservation
  - Batch ingestion
- Results visualization:
  - Multiple plot types (bar, radar, heatmap)
  - Automated report generation
  - Time series support

## Data Flow

### 1. Dataset Handling
```
Llama Dataset Download → Local Storage → Document Processing → Vector Store
```

### 2. RAG Pipeline
```
Query → Vector Search → Context Retrieval → LLM Response Generation
```

### 3. Evaluation Flow
```
Test Queries → RAG Processing → Metric Calculation → Results Storage → Visualization
```

## External Dependencies
- AWS Services:
  - Bedrock for LLM (Claude 3.5 Sonnet)
  - Bedrock for embeddings (Cohere Embed English)
  - OpenSearch for vector storage
- Python Libraries:
  - llama-index for dataset management
  - RAGAs for evaluation metrics
  - Visualization tools

## Recent Changes
- Implemented baseline RAG
- Added Llama dataset support
- Created benchmarking pipeline
- Updated documentation

## Notes
- Vector stores and datasets are git-ignored
- AWS services require proper configuration
- Notebooks handle dependencies automatically
- All implementations are dataset-agnostic
