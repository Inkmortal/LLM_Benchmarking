# Benchmarking RAG Pipelines with a `LabelledRagDataset`

Evaluating Retrieval-Augmented Generation (RAG) systems is essential to ensure their effectiveness across various configurations, such as different Large Language Models (LLMs), similarity thresholds, and chunk sizes. The `LabelledRagDataset` provides a structured approach to this evaluation by pairing queries with reference answers and contexts, similar to traditional machine learning datasets where features predict a ground-truth label.

## Overview

A `LabelledRagDataset` consists of multiple `LabelledRagDataExample` instances. Each example includes:

- **Query**: The input question or prompt.
- **Reference Answer**: The ground-truth answer to the query.
- **Reference Contexts**: The contexts or documents used to generate the reference answer.

This structure allows for systematic evaluation of RAG pipelines by comparing the system's generated responses to the reference answers.

## Creating a `LabelledRagDataExample`

To construct a `LabelledRagDataExample`, follow these steps:

1. **Install Necessary Libraries**:

   ```bash
   pip install llama-index-llms-openai
   pip install llama-index-readers-wikipedia
   ```

2. **Import Required Classes**:

   ```python
   from llama_index.core.llama_dataset import (
       LabelledRagDataExample,
       CreatedByType,
       CreatedBy,
   )
   ```

3. **Define the Example Components**:

   ```python
   # Define the query and its origin
   query = "This is a test query, is it not?"
   query_by = CreatedBy(type=CreatedByType.AI, model_name="gpt-4")

   # Define the reference answer and its origin
   reference_answer = "Yes, it is."
   reference_answer_by = CreatedBy(type=CreatedByType.HUMAN)

   # Define the reference contexts
   reference_contexts = ["This is a sample context"]
   ```

4. **Create the `LabelledRagDataExample` Instance**:

   ```python
   rag_example = LabelledRagDataExample(
       query=query,
       query_by=query_by,
       reference_contexts=reference_contexts,
       reference_answer=reference_answer,
       reference_answer_by=reference_answer_by,
   )
   ```

## Constructing a `LabelledRagDataset`

After creating individual examples, you can aggregate them into a `LabelledRagDataset`:

```python
from llama_index.core.llama_dataset import LabelledRagDataset

# Create additional examples as needed
rag_dataset = LabelledRagDataset(examples=[rag_example])
```

To visualize the dataset:

```python
import pandas as pd

# Convert to a pandas DataFrame
df = rag_dataset.to_pandas()
print(df)
```

## Generating Synthetic Datasets

For large-scale evaluations, manually creating datasets can be labor-intensive. Instead, you can generate synthetic datasets using powerful LLMs like GPT-4. Here's how:

```python
import nest_asyncio
from llama_index.core.llama_dataset.generator import RagDatasetGenerator
from llama_index.llms.openai import OpenAI

nest_asyncio.apply()

# Load Your Documents
documents = [...]  # Load your documents here

# Initialize the LLM
llm = OpenAI(model="gpt-4")

# Create the Dataset Generator
dataset_generator = RagDatasetGenerator.from_documents(
    documents=documents,
    llm=llm,
    num_questions_per_chunk=10,
)

# Generate the Dataset
rag_dataset = dataset_generator.generate_dataset_from_nodes()
```

## Evaluating a RAG Pipeline

Once you have a `LabelledRagDataset`, you can evaluate your RAG system by:

1. **Generating Responses**: Use your RAG pipeline to generate answers for each query in the dataset.
2. **Comparing Responses**: Assess the generated answers against the reference answers to determine correctness, relevancy, and faithfulness.

For streamlined evaluation, consider using the `RagEvaluatorPack`:

```python
from llama_index.core.llama_pack import download_llama_pack

# Download the evaluator pack
RagEvaluatorPack = download_llama_pack("RagEvaluatorPack", "./pack")

# Initialize the evaluator
rag_evaluator = RagEvaluatorPack(
    query_engine=query_engine,
    rag_dataset=rag_dataset,
)

# Run the evaluation
benchmark_df = await rag_evaluator.run()
```

The resulting `benchmark_df` will provide metrics such as correctness, relevancy, faithfulness, and context similarity, offering a comprehensive evaluation of your RAG system's performance.

## Accessing and Contributing Datasets

You can find existing `LabelledRagDataset`s on [LlamaHub](https://llamahub.ai). To download a dataset:

```bash
# Using the CLI
llamaindex-cli download-llamadataset DatasetName --download-dir ./data
```

Or in Python:

```python
from llama_index.core.llama_dataset import download_llama_dataset

# Download the dataset and source documents
rag_dataset, documents = download_llama_dataset("DatasetName", "./data")
```

To contribute your own dataset, follow the guidelines provided in the [LlamaDataset Submission Template Notebook](https://docs.llamaindex.ai/en/stable/examples/llama_dataset/ragdataset_submission_template/).

By leveraging `LabelledRagDataset`s, you can systematically benchmark and enhance your RAG pipelines, ensuring robust and accurate performance across various scenarios.

