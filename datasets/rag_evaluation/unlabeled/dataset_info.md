# Unlabeled RAG Evaluation Datasets

## Overview
This directory contains unlabeled datasets for evaluating RAG implementations using RAGAs' non-reference-based evaluation capabilities.

## Dataset Structure
For unlabeled evaluation, we only need:
```python
{
    "query": str,                    # The question being asked
    "contexts": List[str],          # Retrieved context passages
    "response": str                 # Generated response to evaluate
}
```

## Evaluation with RAGAs
RAGAs provides metrics that don't require reference answers:

```python
from ragas.metrics import (
    faithfulness,          # Measures if response is supported by context
    context_precision,     # Evaluates relevance of retrieved contexts
    context_recall,       # Estimates if important information was retrieved
    context_relevancy     # Assesses context alignment with query
)

# Evaluate without reference answers
results = evaluate(
    dataset=unlabeled_dataset,
    metrics=[
        faithfulness,
        context_precision,
        context_relevancy
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
         "domain": "Domain/topic area",
         "size": {
             "documents": 100,
             "queries": 50
         }
     }
     ```
   - README.md with:
     - Dataset description
     - Domain coverage
     - Any specific evaluation considerations

2. Naming Convention:
   - Directories: `{domain}_{type}`
   - Files: `{name}_v{version}.json`

## Evaluation Strategies
1. **Confidence Scoring**
   - Use LLM-based self-evaluation
   - Assess response consistency
   - Check factual consistency within context

2. **Context Analysis**
   - Evaluate context relevance to query
   - Measure information coverage
   - Assess context coherence

3. **Response Quality**
   - Check response structure
   - Evaluate answer completeness
   - Assess response clarity

## Usage Notes
1. Rate Limiting Considerations:
   ```python
   # Configure evaluation with rate limiting
   results = await evaluator.arun(
       batch_size=20,
       sleep_time_in_seconds=1
   )
   ```

2. Best Practices:
   - Use diverse query types
   - Include edge cases
   - Test with varying context lengths
   - Document any domain-specific considerations
