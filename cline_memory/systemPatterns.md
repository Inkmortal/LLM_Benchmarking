# System Patterns

## Code Organization

### 1. Component-Based Architecture
- Each RAG implementation has its own directory
- Complex implementations split into focused components
- Components grouped by functionality
- Shared utilities in central utils directory

### 2. Directory Structure
```
rag_implementations/
├── baseline_rag/
│   ├── implementation.ipynb
│   └── ingestion.ipynb
└── graph_rag/
    ├── implementation.ipynb
    ├── ingestion.ipynb
    └── components/
        ├── document_processor.py
        ├── graph_store.py
        ├── vector_store.py
        ├── hybrid_search.py
        ├── response_generator.py
        └── metrics.py
```

### 3. Implementation-Specific Code
- Keep implementation-specific code within implementation directory
- Avoid polluting shared utils with specialized code
- Allow independent evolution of implementations

### 4. Shared Utilities
- Common functionality in utils directory
- AWS service wrappers
- Generic metrics and evaluation
- Dataset handling
- Visualization tools

## Design Patterns

### 1. Component Separation
- Each component has a single responsibility
- Clear interfaces between components
- Minimal dependencies between components
- Easy to test and maintain

### 2. Configuration Management
- Configuration passed through constructors
- Default values for common settings
- Clear documentation of options
- Validation of critical parameters

### 3. Resource Management
- Proper initialization and cleanup
- Resource pooling where appropriate
- Error handling and recovery
- Cleanup on failure

### 4. Data Flow
- Clear data transformation steps
- Consistent data structures
- Error handling at boundaries
- Progress tracking and logging

## Implementation Patterns

### 1. Document Processing
- Robust file type handling
- Configurable chunking
- Metadata preservation
- Batch processing support

### 2. Vector Operations
- Efficient vector storage
- Multiple search strategies
- Score normalization
- Batch operations

### 3. Graph Operations
- Entity and relation extraction
- Graph construction and updates
- Hybrid search capabilities
- Graph-specific metrics

### 4. Response Generation
- Context preparation
- Prompt engineering
- Error handling
- Rate limiting

## Testing Patterns

### 1. Evaluation Framework
- Standard metrics across implementations
- Implementation-specific metrics
- Visualization tools
- Result persistence

### 2. Benchmarking
- Consistent dataset handling
- Resource monitoring
- Performance metrics
- Error tracking

### 3. Example Queries
- Representative test cases
- Edge case handling
- Performance validation
- Quality checks

## Documentation Patterns

### 1. Code Documentation
- Clear function signatures
- Parameter descriptions
- Return value documentation
- Usage examples

### 2. Notebook Structure
- Clear sections and flow
- Configuration documentation
- Progress tracking
- Result visualization

### 3. Component Documentation
- Purpose and responsibility
- Configuration options
- Usage patterns
- Dependencies

### 4. Memory Bank Updates
- Active context tracking
- System pattern evolution
- Implementation decisions
- Future improvements
