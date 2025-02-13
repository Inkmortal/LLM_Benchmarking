# Technical Stack

## Core Technologies
- Python 3.x
- Jupyter Notebooks
- AWS Services
- Amazon Bedrock

## AWS Services
### Amazon Bedrock
- LLM: Claude 3.5 Sonnet
  - Used for: Response generation
  - Model ID: anthropic.claude-3-5-sonnet-20240620-v1:0
- Embeddings: Cohere Embed English
  - Used for: Document and query embeddings
  - Model ID: cohere.embed-english-v3
  - Dimension: 1024

### Amazon OpenSearch
- Used for: Vector storage and similarity search
- Features:
  - KNN vector search
  - Cosine similarity scoring
  - Batch document ingestion
  - Metadata storage

### Amazon Neptune (Planned)
- For: Graph database in GraphRAG implementation
- Features needed:
  - Entity storage
  - Relationship mapping
  - Graph traversal
  - Hybrid search with OpenSearch

## RAG Implementations
### Baseline RAG
- Document Processing:
  - Text cleaning and normalization
  - Configurable chunking
  - Metadata preservation
  - Batch processing
- Vector Storage:
  - OpenSearch integration
  - Embedding caching
  - Similarity search
- Response Generation:
  - Context retrieval
  - Prompt engineering
  - LLM integration

### GraphRAG (Planned)
- Graph Database:
  - Entity extraction
  - Relationship mapping
  - Graph traversal
- Hybrid Search:
  - Vector similarity
  - Graph-based ranking
  - Result fusion

## Evaluation Framework
### Metrics
- RAGAs integration:
  - Faithfulness scoring
  - Context precision and recall
  - Response relevancy
  - Context entity recall
  - Noise sensitivity
- Dataset support:
  - Labeled dataset evaluation
  - Unlabeled dataset evaluation
  - Batch processing with rate limiting
- Implementation comparison:
  - Cross-implementation metrics
  - Aggregated scoring
  - Statistical analysis
- Performance tracking:
  - Resource monitoring
  - Response timing
  - Batch processing stats

### Visualization
- Matplotlib/Seaborn for:
  - Multiple plot types:
    - Bar plots with error bars
    - Radar plots for metric comparison
    - Heatmaps for correlations
    - Line plots for time series
    - Scatter plots for relationships
  - Customizable styling and themes
  - Automated report generation
  - Time series visualization
  - Interactive plot support

## Development Tools
### Environment Management
- Conda for:
  - Python environment
  - Package management
  - Dependency isolation

### Version Control
- Git for:
  - Code versioning
  - Large file handling (.gitignore)
  - Collaboration

### Code Organization
- Jupyter notebooks for:
  - Implementation
  - Evaluation
  - Documentation
- Python modules for:
  - Utilities
  - Metrics
  - Visualization

### Documentation
- Markdown files for:
  - Project documentation
  - Code documentation
  - Usage examples

## Dependencies
### Core AWS Services
- boto3 for AWS SDK
- requests-aws4auth for authentication
- opensearchpy for OpenSearch

### RAG Components
- llama-index for:
  - Dataset management
  - Document loading
  - Text processing
- RAGAs for:
  - Evaluation metrics
  - Performance analysis

### Utilities
- tqdm for progress bars
- pandas for data handling
- numpy for numerical operations
- matplotlib/plotly for visualization

## Development Environment
### Python Environment
- Conda environment: rag_bench
- Python version: 3.x
- Package management: conda/pip

### AWS Configuration
- Automated setup via setup.ipynb:
  - AWS credentials verification
  - Service permissions check
  - Environment variable configuration
- Required permissions:
  - Bedrock: invoke_model
  - OpenSearch: full access
  - Neptune: full access (planned)
- Development workflow:
  - Local development with AWS profile
  - SageMaker deployment with instance role

### Code Organization
- Modular implementation
- Standardized interfaces
- Clear documentation
- Reproducible examples
