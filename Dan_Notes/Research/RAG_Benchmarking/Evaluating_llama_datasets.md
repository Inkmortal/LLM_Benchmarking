# Evaluating with `LabelledRagDataset`

Evaluating Retrieval-Augmented Generation (RAG) systems is crucial for ensuring their robustness and effectiveness across various domains. The `LabelledRagDataset` abstraction in LlamaIndex facilitates this evaluation by providing structured datasets for benchmarking.

## Overview

A `LabelledRagDataset` consists of examples where each example includes:

- **Query**: The input question or prompt.
- **Reference Answer**: The ground-truth answer corresponding to the query.
- **Reference Contexts**: A list of contexts used to generate the reference answer.

The primary purpose of using a `LabelledRagDataset` is to test a RAG system's performance by:

1. Predicting a response to the given query.
2. Comparing the predicted response to the reference answer.

## Building a `LabelledRagDataset`

While you can manually construct a `LabelledRagDataset` by creating `LabelledRagDataExample` instances, this process can be tedious. Alternatively, you can generate datasets using strong Large Language Models (LLMs).

LlamaIndex provides the `RagDatasetGenerator` to generate a `LabelledRagDataset` from a set of source documents.

**Example:**

```python
from llama_index.core.llama_dataset.generator import RagDatasetGenerator
from llama_index.llms.openai import OpenAI
import nest_asyncio

nest_asyncio.apply()

# Load your documents
documents = [...]  # Replace with your document loading logic

# Initialize the LLM
llm = OpenAI(model="gpt-4")

# Create the dataset generator
dataset_generator = RagDatasetGenerator.from_documents(
    documents=documents,
    llm=llm,
    num_questions_per_chunk=10,  # Number of questions per node
)

# Generate the dataset
rag_dataset = dataset_generator.generate_dataset_from_nodes()
```

## Using a `LabelledRagDataset`

To evaluate a RAG system using a `LabelledRagDataset`:

1. **Make Predictions**: Generate responses for each query in the dataset using your RAG system.
2. **Evaluate Responses**: Compare the predicted responses to the reference answers and assess the retrieval component by comparing retrieved contexts to reference contexts.

LlamaIndex offers the `RagEvaluatorPack` to streamline this evaluation process.

**Example:**

```python
from llama_index.core.llama_pack import download_llama_pack

# Download the RagEvaluatorPack
RagEvaluatorPack = download_llama_pack("RagEvaluatorPack", "./pack")

# Initialize the evaluator
rag_evaluator = RagEvaluatorPack(
    query_engine=query_engine,  # Your RAG system's query engine
    rag_dataset=rag_dataset,
)

# Run the evaluation
benchmark_df = await rag_evaluator.run()
```

The resulting `benchmark_df` contains mean scores for evaluation metrics such as:

- **Correctness**: Accuracy of the generated answer compared to the reference answer.
- **Relevancy**: Relevance of the generated answer to the query.
- **Faithfulness**: Degree to which the answer is supported by the retrieved contexts.
- **Context Similarity**: Semantic similarity between the reference contexts and the contexts retrieved by the RAG system.

## Accessing `LabelledRagDataset`s

You can find various `LabelledRagDataset`s in the [LlamaHub](https://llamahub.ai/). To download a dataset and its source documents, use the `llamaindex-cli` or the `download_llama_dataset` utility function.

**Using CLI:**

```bash
llamaindex-cli download-llamadataset DatasetName --download-dir ./data
```

**Using Python:**

```python
from llama_index.core.llama_dataset import download_llama_dataset

# Download the dataset
rag_dataset, documents = download_llama_dataset("DatasetName", "./data")
```

## Contributing a `LabelledRagDataset`

To contribute a `LabelledRagDataset` to LlamaHub:

1. **Create the Dataset**: Build the `LabelledRagDataset` and save it as a JSON file.
2. **Submit**: Upload the JSON file and the source text files to the [llama-datasets GitHub repository](https://github.com/emptycrown/llama-datasets).
3. **Pull Request**: Submit a pull request to add the required metadata of the dataset to the [llama-hub GitHub repository](https://github.com/emptycrown/llama-hub).

For a detailed submission process, refer to the [LlamaDataset Submission Template Notebook](https://docs.llamaindex.ai/en/stable/module_guides/evaluating/contributing_llamadatasets/).

## Conclusion

Utilizing `LabelledRagDataset`s enhances the robustness and performance of LLM applications by providing structured evaluation frameworks. For further learning, explore the following resources:

- [Labelled RAG datasets](https://docs.llamaindex.ai/en/stable/examples/llama_dataset/labelled-rag-datasets/)
- [Downloading Llama datasets](https://docs.llamaindex.ai/en/stable/module_guides/evaluating/contributing_llamadatasets/)

By leveraging these tools and resources, you can build and evaluate more effective RAG systems.

