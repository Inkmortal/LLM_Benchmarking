# System Patterns and Architecture

## Code Organization

### Directory Structure
```
project/
├── datasets/
│   └── rag_evaluation/
│       ├── labeled/
│       └── unlabeled/
├── development/
│   └── notebooks/
├── evaluation_pipelines/
│   └── rag_evaluations/
├── rag_implementations/
│   └── baseline_rag/
└── utils/
    ├── aws/
    ├── metrics/
    ├── notebook_utils/
    ├── setup/
    └── visualization/
```

### Implementation Patterns
1. Notebook Organization
   - Split implementation into ingestion and core logic
   - Follow evaluation template structure
   - Extract utilities to Python modules
   - Document with markdown cells

2. Code Modularity
   - Separate concerns by functionality
   - Implement standardized interfaces
   - Use type hints where beneficial
   - Maintain comprehensive docstrings

3. Development Workflow
   - Local development first
   - SageMaker deployment ready
   - Automated environment setup
   - Consistent error handling

## Architectural Patterns

### RAG Implementation
1. Document Processing
   ```python
   class BaselineRAG:
       def ingest_documents(self, documents: List[Dict[str, Any]], batch_size: int = 100):
           """Ingest documents into vector store with batching
           
           Args:
               documents: List of dicts with 'content' and optional 'metadata'
               batch_size: Number of documents per batch
           """
           # Generate embeddings
           # Store in OpenSearch with metadata
           # Handle batching for performance
   ```

2. Vector Storage and Search
   ```python
   class BaselineRAG:
       def _create_index_if_not_exists(self):
           """Create OpenSearch index with KNN vector mapping"""
           mapping = {
               "mappings": {
                   "properties": {
                       "content": {"type": "text"},
                       "metadata": {"type": "object"},
                       "embedding": {
                           "type": "knn_vector",
                           "dimension": 1024
                       }
                   }
               }
           }
           
       def semantic_search(self, query: str, k: int = 3):
           """Search using cosine similarity"""
           # Generate query embedding
           # Use script_score for cosine similarity
           # Return top-k matches with content and metadata
   ```

3. Response Generation
   ```python
   class BaselineRAG:
       def generate_response(self, query: str, context: List[Dict[str, Any]]):
           """Generate response using Claude"""
           # Format context and query into prompt
           # Call Claude with appropriate parameters
           # Return formatted response
           
       def query(self, query: str, k: int = 3):
           """Complete RAG pipeline"""
           # Get relevant documents
           # Generate response
           # Return query, context, and response
   ```

### Evaluation Framework
1. Metrics Pipeline
   ```python
   class RAGMetricsEvaluator:
       def __init__(self, batch_size: int = 20, sleep_time: int = 1):
           """Initialize with rate limiting"""
           # Set up RAGAs metrics:
           # - Faithfulness
           # - Context Precision
           # - Response Relevancy
           # - Context Recall
           # - Context Entity Recall
           # - Noise Sensitivity
           
       async def evaluate_labeled(self, queries, contexts, generated_answers, reference_answers):
           """Evaluate with ground truth"""
           # Run comprehensive metrics suite
           # Handle batching and rate limits
           # Return detailed scores
           
       async def evaluate_unlabeled(self, queries, contexts, generated_answers):
           """Evaluate without ground truth"""
           # Run subset of applicable metrics
           # Focus on response quality
           # Return available scores
   ```

2. Visualization System
   ```python
   class BenchmarkVisualizer:
       def plot_comparison(self, data, comparison_type, plot_type, title):
           """Create comparison visualizations"""
           # Support multiple plot types:
           # - Bar charts
           # - Radar plots
           # - Time series
           # Format for clear comparison
   ```

## Best Practices

### AWS Integration
1. Error Handling
   ```python
   try:
       response = bedrock.invoke_model(...)
   except ClientError as e:
       handle_aws_error(e)
   ```

2. Rate Limiting
   ```python
   @rate_limit(calls=10, period=1)
   def make_api_call():
       # API call implementation
   ```

3. Resource Management
   ```python
   class ResourceManager:
       def __init__(self):
           self.initialize_connections()
           
       def cleanup(self):
           self.close_connections()
   ```

### Data Management
1. Dataset Handling
   ```python
   class DatasetManager:
       def download(self):
           # Cache if not exists
           # Verify integrity
           # Return processed data
   ```

2. Caching Strategy
   ```python
   class CacheManager:
       def get_or_compute(self, key, compute_fn):
           if key in cache:
               return cache[key]
           result = compute_fn()
           cache[key] = result
           return result
   ```

## Implementation Guidelines

### Code Style
1. Function Design
   - Clear single responsibility
   - Descriptive naming
   - Type hints where helpful
   - Comprehensive docstrings

2. Error Handling
   - Specific exception types
   - Informative error messages
   - Proper cleanup in finally blocks
   - Logging for debugging

3. Performance
   - Batch operations where possible
   - Caching for expensive operations
   - Async for I/O-bound tasks
   - Resource monitoring

### Testing Strategy
1. Unit Tests
   - Test core functionality
   - Mock external services
   - Check edge cases
   - Validate error handling

2. Integration Tests
   - Test service interactions
   - Verify data flow
   - Check end-to-end paths
   - Monitor performance

## Documentation Standards

### Code Documentation
1. Module Level
   ```python
   """
   Module: document_processor.py
   Purpose: Handles document processing for RAG
   Components:
   - DocumentProcessor: Main processing class
   - TextCleaner: Text normalization
   """
   ```

2. Class Level
   ```python
   class DocumentProcessor:
       """
       Processes documents for RAG implementation.
       
       Attributes:
           chunk_size (int): Size of text chunks
           overlap (int): Overlap between chunks
       
       Methods:
           process(): Process documents
           clean(): Clean text
       """
   ```

3. Function Level
   ```python
   def process_document(doc: Document) -> List[Chunk]:
       """
       Process a single document into chunks.
       
       Args:
           doc (Document): Input document
           
       Returns:
           List[Chunk]: Processed chunks
           
       Raises:
           ProcessingError: If processing fails
       """
   ```

### Project Documentation
1. README Structure
   - Project overview
   - Setup instructions
   - Usage examples
   - API documentation
   - Contributing guidelines

2. Notebook Documentation
   - Purpose and goals
   - Dependencies
   - Usage instructions
   - Example outputs
