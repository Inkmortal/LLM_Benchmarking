# RAG Benchmarking Project Roadmap

## High-Level Goals
- [x] Create a flexible framework for evaluating RAG implementations
- [ ] Implement and compare baseline RAG vs GraphRAG
- [x] Establish metrics and evaluation pipelines for both labeled and unlabeled datasets
- [ ] Enable parameter tuning and optimization capabilities

## Key Features
- [x] Modular RAG implementations with standardized interfaces
- [x] Comprehensive evaluation pipelines
- [x] Support for both labeled and unlabeled datasets
- [ ] Parameter tuning capabilities
- [x] Visualization and comparison tools

## Completion Criteria
- [x] RAG implementations can be imported and used as libraries
- [x] Evaluation pipelines can compare different implementations
- [ ] Support for both implementation comparison and parameter tuning
- [x] Clear documentation and examples

## Progress Tracking
### Phase 1: Infrastructure Setup ✅
- [x] Create project directory structure
- [x] Set up documentation
- [x] Implement core utilities
- [x] Configure AWS services

### Phase 2: RAG Implementations 🔄
- [x] Implement baseline RAG with ingestion
  - [x] OpenSearch integration
  - [x] Bedrock integration
  - [x] Generic document processing
  - [x] Batch ingestion support
- [ ] Implement GraphRAG with ingestion
  - [ ] Neptune integration
  - [ ] Hybrid search setup
  - [ ] Entity extraction
  - [ ] Graph-based ingestion
- [x] Create standardized interfaces

### Phase 3: Evaluation Framework ✅
- [x] Set up dataset organization
  - [x] Support for Llama datasets
  - [x] Automatic downloading
  - [x] Caching system
- [x] Implement evaluation metrics
  - [x] RAGAs integration with async support
  - [x] Support for labeled/unlabeled data
  - [x] Performance metrics
  - [x] Result aggregation
- [x] Create visualization utilities
  - [x] Multiple plot types (bar, radar, heatmap)
  - [x] Report generation
  - [x] Time series support
- [x] Create comparison pipelines
- [x] Create tuning pipelines

### Phase 4: Testing and Documentation 🔄
- [ ] Test with sample datasets
  - [x] Origin of Covid-19 dataset
  - [ ] Additional Llama datasets
  - [ ] Custom datasets
- [ ] Document usage examples
  - [x] Basic RAG usage
  - [x] Dataset handling
  - [ ] Parameter tuning
- [x] Create visualization utilities

## Completed Tasks
- [x] Initial project planning
- [x] Architecture design
- [x] Core infrastructure setup
- [x] Documentation framework
- [x] Evaluation pipeline templates
- [x] Baseline RAG implementation
- [x] Dataset integration
- [x] Benchmarking setup

## Current Focus
1. Testing baseline RAG with Covid-19 dataset
2. Implementing GraphRAG components
3. Setting up comparison framework

## Next Milestones
1. Complete GraphRAG implementation
2. Run comprehensive benchmarks
3. Document findings and insights
4. Optimize performance
