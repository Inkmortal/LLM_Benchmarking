# Amazon Bedrock Foundation Models Guide

Amazon Bedrock supports a variety of foundation models (FMs) from multiple providers. This guide categorizes the available models and highlights those best suited for tasks like Retrieval-Augmented Generation (RAG), SQL generation, and data analysis.

## 📌 **Best Models for Embeddings (RAG, SQL, Search, Recommendations)**
Embedding models are crucial for tasks like document search, semantic search, and vector databases.

| Provider | Model Name | Model ID | Supported Regions | Input Modalities | Output Modalities |
|----------|------------|----------|-------------------|------------------|------------------|
| **Cohere** | Embed English | `cohere.embed-english-v3` | Multiple | Text | Embedding |
| **Cohere** | Embed Multilingual | `cohere.embed-multilingual-v3` | Multiple | Text | Embedding |
| **Amazon** | Titan Text Embeddings V2 | `amazon.titan-embed-text-v2:0` | us-east-1, us-east-2, us-west-2, multiple others | Text | Embedding |

👉 **Best choice for RAG & SQL tasks**: 
- **Cohere Embed English** is great for English-only applications, while **Embed Multilingual** is suited for multi-language support.
- **Amazon Titan v2 can be a cheap option for embeddings, though Cohere models generally outperform it in benchmarks.** ([Source](https://www.tonic.ai/blog/rag-evaluation-series-validating-the-rag-performance-of-amazon-titan-vs-cohere-using-amazon-bedrock))

## 🤖 **Best Foundation Models for AI Agents (RAG, SQL Generation, Data Analysis)**
AI agents require foundation models capable of understanding text, executing SQL queries, and analyzing data.

| Provider | Model Name | Model ID | Supported Regions | Input Modalities | Output Modalities | Streaming |
|----------|------------|----------|-------------------|------------------|------------------|-----------|
| **Anthropic** | Claude 3.5 Sonnet | `anthropic.claude-3-5-sonnet-20240620-v1:0` | Multiple | Text, Image | Text, Chat | Yes |
| **Anthropic** | Claude 3.5 Haiku | `anthropic.claude-3-5-haiku-20241022-v1:0` | us-east-1, us-east-2, us-west-2 | Text, Image | Text, Chat | Yes |
| **Amazon** | Nova Lite | `amazon.nova-lite-v1:0` | us-east-1, us-east-2, us-west-2 | Text, Image, Video | Text | Yes |
| **Amazon** | Nova Pro | `amazon.nova-pro-v1:0` | us-east-1, us-east-2, us-west-2 | Text, Image, Video | Text | Yes |
| **Meta** | Llama 3.2 90B Instruct | `meta.llama3-2-90b-instruct-v1:0` | us-east-1, us-east-2, us-west-2 | Text, Image | Text, Chat | Yes |
| **Cohere** | Command R+ | `cohere.command-r-plus-v1:0` | us-east-1, us-west-2 | Text | Text, Chat | Yes |

👉 **Best choices for AI Agents**:
- **Claude 3.5 Sonnet** offers high intelligence for general-purpose tasks, making it excellent for RAG and SQL-based analysis but is more expensive.
- **Amazon Nova models, including Nova Pro, are a cheaper alternative to Claude but still inferior in raw capability.** ([Source](https://www.linkedin.com/pulse/copy-benchmark-battles-how-amazon-nova-compares-other-gottumukkala-lq5mc))
- **Llama 3.2 90B Instruct** is powerful for fine-tuning on SQL and data-related tasks.
- **Cohere Command R+** is optimized for reasoning and structured output, making it useful for SQL generation and data workflows.

## 📊 **Best Models for Image & Multimodal Tasks**
For multimodal applications (text-to-image, image generation, etc.), these models are ideal:

| Provider | Model Name | Model ID | Supported Regions | Input Modalities | Output Modalities |
|----------|------------|----------|-------------------|------------------|------------------|
| **Amazon** | Titan Image Generator G1 v2 | `amazon.titan-image-generator-v2:0` | us-east-1, us-west-2 | Text, Image | Image |
| **Amazon** | Nova Canvas | `amazon.nova-canvas-v1:0` | us-east-1 | Text, Image | Image |
| **Stability AI** | Stable Diffusion 3.5 Large | `stability.sd3-5-large-v1:0` | us-west-2 | Text, Image | Image |
| **Stability AI** | Stable Image Ultra 1.0 | `stability.stable-image-ultra-v1:0` | us-west-2 | Text | Image |

👉 **Best choices**:
- **Stable Diffusion 3.5 Large** is the best for high-quality image generation.
- **Nova Canvas** is a strong AWS-native model for text-to-image tasks.

---
## Summary of Key Models for Each Use Case

| Task | Recommended Models |
|------|--------------------|
| **Embeddings (RAG, SQL, Search)** | Cohere Embed English/Multilingual, Titan Text Embeddings V2 (budget option) |
| **AI Agents (RAG, SQL, Analysis)** | Claude 3.5 Sonnet, Llama 3.2 90B Instruct, Cohere Command R+, Nova Pro (budget option) |
| **Image Generation** | Stable Diffusion 3.5 Large, Nova Canvas |
| **Multimodal Analysis** | Nova Lite, Llama 3.2 90B Instruct |

By leveraging the right model for the right task, you can maximize Amazon Bedrock's capabilities in your AI applications while being mindful of cost and performance trade-offs.

