# Technical Context

## Core Technology Stack

### Development Environment
- Python 3.x with Conda environment management
- Jupyter Notebooks for development
- VSCode as primary editor
- Git for version control
- PowerShell for CLI operations

### AWS Services
#### Amazon Bedrock
- LLM: Claude 3.5 Sonnet
  - Purpose: Response generation
  - Model ID: anthropic.claude-3-5-sonnet-20240620-v1:0
- Embeddings: Cohere Embed English
  - Purpose: Document and query embeddings
  - Model ID: cohere.embed-english-v3
  - Dimension: 1024

#### Amazon OpenSearch
- Purpose: Vector storage and similarity search
- Features:
  - KNN vector search
  - Cosine similarity scoring
  - Batch document ingestion
  - Metadata storage
- Configuration:
  - Engine: OpenSearch 2.11
  - Instance: t3.small.search
  - Storage: 10GB gp3 EBS
  - Single node (no replication)
  - Public access with IAM auth
- Management:
  - Automatic domain creation
  - Default cleanup enabled
  - Duplicate document detection
  - Cost monitoring
  - Endpoint auto-detection (VPC/non-VPC)

#### Amazon Neptune (Planned)
- Purpose: Graph database for GraphRAG
- Features:
  - Entity storage
  - Relationship mapping
  - Graph traversal
  - Hybrid search integration

## Implementation Architecture

### RAG Components
#### Baseline Implementation
- Document Processing:
  - Text cleaning and normalization
  - Configurable chunking
  - Metadata preservation
  - Batch processing support
  - Duplicate detection
- Vector Storage:
  - OpenSearch integration
  - Embedding caching
  - Similarity search optimization
  - Resource cleanup
- Response Generation:
  - Context retrieval
  - Prompt engineering
  - LLM integration

#### GraphRAG (Planned)
- Graph Database:
  - Entity extraction
  - Relationship mapping
  - Graph traversal
- Hybrid Search:
  - Vector similarity
  - Graph-based ranking
  - Result fusion

### Evaluation Framework
- RAGAs Integration:
  - Faithfulness: Measures response accuracy against context
  - Context Precision: Evaluates relevance of retrieved contexts
  - Response Relevancy: Assesses answer relevance to query
  - Context Recall: Measures coverage of reference information
  - Context Entity Recall: Tracks entity preservation
  - Noise Sensitivity: Tests robustness to context noise

- Dataset Support:
  - Labeled Evaluation:
    - Uses ground truth answers
    - Comprehensive metric suite
    - Accuracy benchmarking
  - Unlabeled Evaluation:
    - No reference answers needed
    - Focus on response quality
    - Consistency checking
  - Batch Processing:
    - Configurable batch sizes
    - Rate limiting (20 calls/batch)
    - Sleep time between batches (1s default)

- Implementation Comparison:
  - Cross-implementation metrics:
    - Standardized scoring
    - Multiple comparison dimensions
    - Performance deltas
  - Aggregated Scoring:
    - Weighted metric averaging
    - Overall performance index
    - Trend analysis
  - Statistical Analysis:
    - Confidence intervals
    - Significance testing
    - Distribution analysis

- Performance Monitoring:
  - Resource Tracking:
    - API call monitoring
    - Memory usage tracking
    - Processing time logs
    - OpenSearch cost tracking
  - Response Timing:
    - Query latency
    - Context retrieval speed
    - Generation time
  - Batch Statistics:
    - Success rates
    - Error patterns
    - Throughput metrics

## Development Infrastructure

### Environment Configuration
- Conda environment: rag_bench
- Python version: 3.x
- Package management: conda/pip

### AWS Setup
- Configuration via setup.ipynb:
  - AWS credentials verification
  - Service permissions check
  - Environment variable setup
- Required Permissions:
  - Bedrock: invoke_model
  - OpenSearch: full access
  - Neptune: full access (planned)

### Core Dependencies
- AWS Integration:
  - boto3: AWS SDK
  - requests-aws4auth: Authentication
  - opensearchpy: OpenSearch client
- RAG Components:
  - llama-index: Dataset/document management
  - RAGAs: Evaluation metrics
- Utilities:
  - tqdm: Progress tracking
  - pandas: Data manipulation
  - numpy: Numerical operations
  - matplotlib/plotly: Visualization

### Development Workflow
1. Local Development:
   - Code writing and testing
   - AWS profile configuration
   - Local environment setup
2. SageMaker Deployment:
   - Notebook environment setup
   - Instance role configuration
   - Dependency installation
3. Production Pipeline:
   - Automated testing
   - Performance monitoring
   - Resource optimization
   - Cost tracking

## System Requirements
- AWS account with service access
- Python 3.x environment
- Sufficient storage for datasets
- Memory for batch processing
- Network access for API calls
- OpenSearch domain capacity
