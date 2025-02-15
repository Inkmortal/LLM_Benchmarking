# Active Context

## Current Focus
- RAG Evaluation System
- RAGAs Framework Integration
- Visualization Improvements

## Recent Changes

### RAG Evaluation System Updates (2024-02-14)
1. BedrockLLM Integration
   - Created custom BedrockLLM wrapper for RAGAs
   - Updated to Claude 3 Sonnet model
   - Added temperature and max tokens config
   - Improved error handling

2. RAGAs Integration
   - Implemented RAGMetricsEvaluator class
   - Added support for labeled/unlabeled datasets
   - Integrated visualization components
   - Added progress tracking

3. Visualization Enhancements
   - Added BenchmarkVisualizer class
   - Multiple plot types supported:
     - Bar plots
     - Radar charts
     - Heatmaps
     - Line plots
   - Customizable report generation
   - Split view for retrieval vs generation metrics

### Key Components
1. RAG Metrics Implementation
   ```python
   class RAGMetricsEvaluator:
       def __init__(
           self,
           region_name: str = "us-west-2",
           llm_model_id: str = "anthropic.claude-3-sonnet-20240229-v1:0",
           embedding_model_id: str = "cohere.embed-english-v3",
           temperature: float = 0.0
       ):
           # Initialize Bedrock models
           evaluator_llm = LangchainLLMWrapper(...)
           evaluator_embeddings = LangchainEmbeddingsWrapper(...)
           
           # Initialize metrics
           self.metrics = [
               ContextPrecision(llm=evaluator_llm),
               ContextRecall(llm=evaluator_llm),
               ContextEntityRecall(llm=evaluator_llm),
               NoiseSensitivity(llm=evaluator_llm),
               Faithfulness(llm=evaluator_llm),
               ResponseRelevancy(llm=evaluator_llm, embeddings=evaluator_embeddings)
           ]
   ```

2. Metrics Configuration
   - Context Retrieval:
     - Precision: How many retrieved documents are relevant
     - Recall: How many relevant documents were retrieved
     - Entity Recall: How well important entities are preserved
     - Noise Sensitivity: Robustness against irrelevant data
   - Answer Generation:
     - Faithfulness: How factual the answers are
     - Answer Relevancy: How relevant answers are to questions

3. Visualization System
   ```python
   class BenchmarkVisualizer:
       def plot_comparison(
           self,
           data: Union[Dict[str, Dict[str, float]], pd.DataFrame],
           comparison_type: str = "metrics",
           plot_type: str = "bar",
           title: Optional[str] = None,
           save_path: Optional[str] = None
       ):
           # Create comparison plots
           plt.figure(figsize=(12, 6))
           
           # Plot retrieval metrics
           plt.subplot(1, 2, 1)
           sns.barplot(...)
           
           # Plot generation metrics
           plt.subplot(1, 2, 2)
           sns.barplot(...)
   ```

## Active Decisions
1. Using BedrockLLM wrapper for RAGAs compatibility
2. Split visualization between retrieval and generation metrics
3. Support for both labeled and unlabeled evaluation
4. Customizable report generation

## Next Steps
1. Add batch processing for large evaluations
2. Implement custom metrics for specific use cases
3. Add caching for repeated evaluations
4. Enhance error analysis and reporting

## Known Issues
1. Large batch evaluations can hit rate limits
2. Need to optimize memory usage for big datasets
3. Some metrics require significant compute time
4. Error handling needs improvement for edge cases

## Optimization Opportunities
1. Batch Processing
   - Implement smart batching
   - Add progress tracking
   - Handle rate limits
   - Cache intermediate results

2. Memory Management
   - Optimize data structures
   - Clear unused resources
   - Stream large datasets
   - Monitor memory usage

3. Error Handling
   - Add retry mechanisms
   - Improve error messages
   - Handle edge cases
   - Add logging system

4. Performance
   - Cache embeddings
   - Parallel processing
   - Resource monitoring
   - Cost optimization
