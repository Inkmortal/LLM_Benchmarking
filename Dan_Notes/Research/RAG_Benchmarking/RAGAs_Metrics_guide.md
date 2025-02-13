# 📊 Ragas Metrics Documentation Guide

## Overview
Ragas provides a comprehensive suite of evaluation metrics tailored to assess various aspects of Large Language Model (LLM) applications, particularly in Retrieval Augmented Generation (RAG) systems. This document details each available metric, its use case, and how to implement it effectively.

---

## 🚀 Retrieval Augmented Generation (RAG) Metrics

These metrics evaluate the effectiveness of systems that combine retrieval mechanisms with generative models.

### 📌 Context Precision
- **Purpose**: Measures how many of the retrieved documents are actually relevant to the query.
- **Use Case**: Helps fine-tune retrieval algorithms by ensuring relevant context is provided.
- **Implementation Example**:
  
  ```python
  from ragas.metrics import ContextPrecision
  
  metric = ContextPrecision(llm=evaluator_llm)
  score = await metric.single_turn_ascore(sample)
  ```

### 📌 Context Recall
- **Purpose**: Measures how many of the relevant documents were retrieved compared to the total relevant documents available.
- **Use Case**: Ensures the retrieval system does not miss out on important documents.
- **Implementation Example**:

  ```python
  from ragas.metrics import ContextRecall
  
  metric = ContextRecall(llm=evaluator_llm)
  score = await metric.single_turn_ascore(sample)
  ```

### 📌 Context Entity Recall
- **Purpose**: Evaluates how well entity information is preserved in the retrieved context.
- **Use Case**: Useful in cases where entity consistency is crucial (e.g., medical or legal applications).
- **Implementation Example**:

  ```python
  from ragas.metrics import ContextEntityRecall
  
  metric = ContextEntityRecall(llm=evaluator_llm)
  score = await metric.single_turn_ascore(sample)
  ```

### 📌 Noise Sensitivity
- **Purpose**: Measures how much irrelevant data affects the retrieval system’s performance.
- **Use Case**: Ensures robustness against noisy data in retrieval.
- **Implementation Example**:

  ```python
  from ragas.metrics import NoiseSensitivity
  
  metric = NoiseSensitivity(llm=evaluator_llm)
  score = await metric.single_turn_ascore(sample)
  ```

### 📌 Response Relevancy
- **Purpose**: Assesses how relevant the system's response is to the user's query.
- **Use Case**: Ensures generated responses align with user intent.
- **Implementation Example**:

  ```python
  from ragas.metrics import ResponseRelevancy
  
  metric = ResponseRelevancy(llm=evaluator_llm, embeddings=evaluator_embeddings)
  score = await metric.single_turn_ascore(sample)
  ```

### 📌 Faithfulness
- **Purpose**: Evaluates the factual accuracy of the response based on retrieved documents.
- **Use Case**: Critical for fact-based systems (e.g., news generation, legal assistance).
- **Implementation Example**:

  ```python
  from ragas.metrics import Faithfulness
  
  metric = Faithfulness(llm=evaluator_llm)
  score = await metric.single_turn_ascore(sample)
  ```

---

## 🛠️ SQL Metrics

These metrics help evaluate the correctness of SQL-related responses.

### 📌 Execution-based Datacompy Score
- **Purpose**: Compares data outputs to ensure consistency between expected and actual results.
- **Use Case**: Used for verifying SQL query outputs.
- **Implementation Example**:

  ```python
  from ragas.metrics import ExecutionBasedDatacompyScore
  
  metric = ExecutionBasedDatacompyScore(llm=evaluator_llm)
  score = await metric.single_turn_ascore(sample)
  ```

### 📌 SQL Query Equivalence
- **Purpose**: Determines if two SQL queries produce the same results.
- **Use Case**: Useful for validating different SQL query formulations that should yield identical results.
- **Implementation Example**:

  ```python
  from ragas.metrics import SQLQueryEquivalence
  
  metric = SQLQueryEquivalence(llm=evaluator_llm)
  score = await metric.single_turn_ascore(sample)
  ```

---

## 📚 Other Available Metrics

### 📌 Topic Adherence
- **Purpose**: Measures how well the model adheres to a given topic.
- **Use Case**: Ensures focused responses in domain-specific applications.
- **Implementation Example**:

  ```python
  from ragas.metrics import TopicAdherenceScore
  
  metric = TopicAdherenceScore(llm=evaluator_llm, mode="precision")
  score = await metric.multi_turn_ascore(sample)
  ```

### 📌 Tool Call Accuracy
- **Purpose**: Evaluates how accurately the system invokes external tools or APIs.
- **Use Case**: Helps improve tool usage in AI assistants.
- **Implementation Example**:

  ```python
  from ragas.metrics import ToolCallAccuracy
  
  metric = ToolCallAccuracy(llm=evaluator_llm)
  score = await metric.multi_turn_ascore(sample)
  ```

### 📌 Factual Correctness
- **Purpose**: Ensures the generated response aligns with a reference text.
- **Use Case**: Vital for accuracy in knowledge-based systems.
- **Implementation Example**:

  ```python
  from ragas.metrics import FactualCorrectness
  
  metric = FactualCorrectness(llm=evaluator_llm)
  score = await metric.single_turn_ascore(sample)
  ```

### 📌 Semantic Similarity
- **Purpose**: Measures how semantically close a response is to the reference.
- **Use Case**: Ensures paraphrased responses maintain meaning.
- **Implementation Example**:

  ```python
  from ragas.metrics import SemanticSimilarity
  
  metric = SemanticSimilarity(embeddings=evaluator_embeddings)
  score = await metric.single_turn_ascore(sample)
  ```

### 📌 BLEU Score
- **Purpose**: Evaluates response quality based on n-gram precision.
- **Use Case**: Commonly used in translation and summarization evaluation.
- **Implementation Example**:

  ```python
  from ragas.metrics import BleuScore
  
  metric = BleuScore()
  score = await metric.single_turn_ascore(sample)
  ```

### 📌 ROUGE Score
- **Purpose**: Measures the overlap of n-grams between response and reference.
- **Use Case**: Used in text summarization evaluations.
- **Implementation Example**:

  ```python
  from ragas.metrics import RougeScore
  
  metric = RougeScore()
  score = await metric.single_turn_ascore(sample)
  ```

---

## 📥 Importing Ragas Metrics

To use any metric from Ragas, install the package and import the required metric:

```bash
pip install ragas
```

Then, import and use the metric in your Python script:

```python
from ragas.metrics import ContextPrecision, Faithfulness
```

---

## 🎯 Conclusion

This guide provides a detailed overview of Ragas metrics, particularly focusing on RAG and SQL evaluation tools. Implement these metrics in your evaluation pipeline to ensure high-quality and factually accurate LLM applications.
