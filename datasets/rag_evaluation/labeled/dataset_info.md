# Labeled RAG Evaluation Datasets

## Overview
This directory contains labeled datasets for evaluating RAG implementations. We use LlamaIndex for dataset loading and RAGAs for evaluation.

## Dataset Structure and Loading
Datasets can be loaded using LlamaIndex's dataset utilities:

```python
from llama_index.core.llama_dataset import download_llama_dataset

# Download and load dataset
rag_dataset, documents = download_llama_dataset(
    "DatasetName",  # e.g., "OriginOfCovid19Dataset"
    "./data"
)
```

Dataset format follows LlamaIndex structure:
```python
{
    "query": str,                    # The question being asked
    "reference_contexts": str,       # The relevant context passages
    "reference_answer": str,         # The ground truth answer
    "reference_answer_by": str,      # Model/source that provided reference answer
    "query_by": str                  # Model/source that generated query
}
```

## Evaluation with RAGAs
We use RAGAs for comprehensive evaluation:

```python
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    context_precision,
    answer_relevance,
    answer_correctness
)

# Evaluate using RAGAs
results = evaluate(
    dataset=rag_dataset,
    metrics=[
        faithfulness,
        context_precision,
        answer_relevance,
        answer_correctness
    ]
)
```

## Dataset Organization
1. Each dataset should be in its own subdirectory containing:
   - Dataset files
   - `dataset_config.json` with:
     ```json
     {
         "name": "dataset_name",
         "version": "1.0",
         "description": "Dataset description",
         "source": "Dataset source/origin",
         "size": {
             "documents": 100,
             "queries": 50
         }
     }
     ```
   - README.md with usage examples

2. Naming Convention:
   - Directories: `{domain}_{type}`
   - Files: `{name}_v{version}.json`

## Available Datasets
(To be populated as datasets are added)

## Usage Notes
1. For OpenAI API rate limiting:
   ```python
   # Example with rate limiting
   results = await evaluator.arun(
       batch_size=20,              # Batch API calls
       sleep_time_in_seconds=1     # Sleep between calls
   )
   
   # For lower tier API access (e.g., Tier 1):
   results = await evaluator.arun(
       batch_size=5,
       sleep_time_in_seconds=15
   )
   ```

2. When adding new datasets:
   - Verify format compatibility
   - Include source documentation
   - Test with both LlamaIndex loading and RAGAs evaluation
   - Document any preprocessing steps
