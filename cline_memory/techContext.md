# Technical Context

## Development Environment
- Python 3.8+
- Jupyter notebooks
- AWS SageMaker for development and testing

## Core Technologies

### AWS Services
1. Amazon Bedrock
   - Claude 3.5 Sonnet for LLM responses
   - Cohere Embed English v3 for embeddings
2. Amazon OpenSearch
   - Vector storage and similarity search
   - t3.small.search instance type
   - 10GB gp3 EBS storage
   - Identity-based access control
   - Configurable verbosity for setup and management

### Document Processing
1. Langchain
   - Document loaders for multiple formats
     - PyPDFLoader for PDFs
     - TextLoader for text files
     - Docx2txtLoader for Word docs
     - UnstructuredFileLoader as fallback
   - RecursiveCharacterTextSplitter for chunking
     - Configurable chunk size and overlap
     - Smart separator handling
     - Context preservation

2. Configuration
   - Default chunk size: 500 words (≈2000 chars)
   - Default overlap: 50 words
   - Chunking enabled by default
   - Batch processing: 100 docs per batch

### Python Libraries
1. boto3 for AWS interactions
2. opensearchpy for vector operations
3. requests_aws4auth for authentication
4. tqdm for progress tracking
5. langchain-community for document processing
6. pypdf for PDF handling
7. python-magic for file type detection
8. docx2txt for Word document processing

## Development Tools

### Utility Modules
1. utils.aws.opensearch_utils
   - OpenSearchManager for domain lifecycle
   - Automatic identity detection
   - Configurable verbosity
   - Resource cleanup management

2. utils.notebook_utils
   - dataset_utils for data loading
   - document_utils for text processing
   - importable for notebook imports

3. utils.metrics
   - RAG evaluation metrics
   - Benchmark comparisons

4. utils.visualization
   - Comparison plots
   - Results visualization

### Development Utilities
1. dev_utils.ipynb
   - Automatic module discovery
   - Dynamic reloading
   - Test cases
   - Debug workflows

## Infrastructure

### OpenSearch Configuration
1. Domain Settings
   - OpenSearch 2.11
   - Single node deployment
   - No dedicated master
   - No zone awareness

2. Storage
   - EBS gp3 volumes
   - 10GB per instance
   - 3000 IOPS
   - 125 MB/s throughput

3. Security
   - Identity-based access
   - IAM role/user authentication
   - Resource-level permissions

4. Management
   - Automatic setup
   - Status monitoring
   - Resource cleanup
   - Configurable verbosity

### Vector Store
1. Index Configuration
   - knn_vector field type
   - 1024-dimension vectors
   - Cosine similarity

2. Document Storage
   - Text content
   - Metadata fields
   - Vector embeddings

## Development Patterns

### Code Organization
1. Utilities by function
   - AWS interactions
   - Data processing
   - Evaluation metrics
   - Visualization

2. Notebook Structure
   - Configuration
   - Setup
   - Processing
   - Evaluation
   - Cleanup

### Testing
1. Unit Tests
   - Utility functions
   - Data processing
   - Metrics calculation

2. Integration Tests
   - RAG pipeline
   - OpenSearch operations
   - AWS service interactions

## Deployment

### SageMaker Setup
1. Environment
   - Python dependencies
   - AWS credentials
   - Environment variables

2. Resource Management
   - OpenSearch domain lifecycle
   - Vector store cleanup
   - Cost optimization

### Local Development
1. Setup
   - Python environment
   - AWS configuration
   - Local dependencies

2. Testing
   - Unit tests
   - Integration tests
   - Benchmark runs
