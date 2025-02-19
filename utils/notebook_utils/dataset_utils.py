"""Dataset utilities for downloading, loading, and examining LlamaIndex datasets."""

import json
import shutil
from pathlib import Path
from typing import Dict, Any, Tuple, List, Optional
from llama_index.llama_dataset import LabelledRagDataset, download_llama_dataset
from llama_index import SimpleDirectoryReader
from ragas import SingleTurnSample, EvaluationDataset

DATASET_REGISTRY = {
    'OriginOfCovid19Dataset': {
        'name': 'OriginOfCovid19Dataset',
        'description': 'Dataset about the origins of COVID-19',
        'type': 'labeled'
    },
    'PaulGrahamEssaysDataset': {
        'name': 'PaulGrahamEssaysDataset',
        'description': 'Collection of Paul Graham essays',
        'type': 'labeled'
    }
}

def download_dataset(dataset_name: str, output_dir: Path) -> Path:
    """Download a dataset from the LlamaIndex repository.
    
    Args:
        dataset_name: Name of dataset from DATASET_REGISTRY
        output_dir: Directory to save dataset
        
    Returns:
        Path to downloaded dataset directory
    """
    if dataset_name not in DATASET_REGISTRY:
        raise ValueError(f"Unknown dataset: {dataset_name}. Available datasets: {list(DATASET_REGISTRY.keys())}")
    
    print(f"Downloading {dataset_name}...")
    dataset_info = DATASET_REGISTRY[dataset_name]
    
    # Map dataset names to directory names
    dir_name_map = {
        'OriginOfCovid19Dataset': 'covid19_origin',
        'PaulGrahamEssaysDataset': 'paul_graham_essays'
    }
    
    # Create dataset directory using consistent naming
    dir_name = dir_name_map.get(dataset_name, dataset_name.lower())
    dataset_dir = output_dir / dir_name
    dataset_dir.mkdir(parents=True, exist_ok=True)
    
    # Download dataset with proper directory
    dataset, documents = download_llama_dataset(dataset_name, str(dataset_dir))
    
    # Save dataset
    dataset.save_json(str(dataset_dir / "rag_dataset.json"))
    
    # Save source documents
    source_dir = dataset_dir / "source_files"
    source_dir.mkdir(exist_ok=True)
    
    for i, doc in enumerate(documents):
        with open(source_dir / f"doc_{i}.txt", 'w', encoding='utf-8') as f:
            f.write(doc.text)
    
    print(f"Dataset saved to {dataset_dir}")
    return dataset_dir

def load_labeled_dataset(dataset_dir: Path, download_if_missing: bool = True) -> Tuple[LabelledRagDataset, List[Any]]:
    """Load a labeled dataset and its source documents.
    
    Args:
        dataset_dir: Path to dataset directory containing:
            - rag_dataset.json
            - source_files/
    
    Returns:
        Tuple of (dataset, documents)
    """
    dataset_file = dataset_dir / "rag_dataset.json"
    source_dir = dataset_dir / "source_files"
    
    # Check if dataset exists
    if not dataset_file.exists() or not source_dir.exists():
        if download_if_missing:
            # Extract base name and convert to proper format
            base_name = dataset_dir.name.lower()
            if base_name == "covid19_origin":
                dataset_name = "OriginOfCovid19Dataset"
            else:
                # Default case - convert snake_case to PascalCase and add Dataset suffix
                parts = base_name.split('_')
                dataset_name = ''.join(word.capitalize() for word in parts) + 'Dataset'
            print(f"Dataset not found. Downloading {dataset_name}...")
            download_dataset(dataset_name, dataset_dir.parent)
        else:
            raise FileNotFoundError(f"Dataset not found at {dataset_dir}")
    
    # Load dataset
    dataset = LabelledRagDataset.from_json(str(dataset_file))
    documents = SimpleDirectoryReader(str(source_dir)).load_data()
    
    return dataset, documents

def examine_dataset_structure(dataset: LabelledRagDataset, documents: List[Any]) -> Dict[str, Any]:
    """Examine and return dataset structure information.
    
    Args:
        dataset: Loaded LabelledRagDataset
        documents: List of loaded documents
    
    Returns:
        Dictionary containing dataset information
    """
    # Get example structure
    example = dataset.examples[0]
    example_data = {
        'query': example.query,
        'reference_answer': example.reference_answer,
        'reference_contexts': example.reference_contexts[:1]  # Show first context only
    }
    
    # Get document structure
    doc = documents[0]
    doc_preview = {
        'text_preview': doc.text[:200] + '...',
        'metadata': doc.metadata
    }
    
    # Compile dataset info
    dataset_info = {
        'num_examples': len(dataset.examples),
        'num_documents': len(documents),
        'example_format': example_data,
        'document_format': doc_preview
    }
    
    return dataset_info

def prepare_documents_for_rag(documents: List[Any], dataset_name: str) -> List[Dict[str, Any]]:
    """Prepare documents for RAG ingestion.
    
    Args:
        documents: List of loaded documents
        dataset_name: Name of dataset for metadata
    
    Returns:
        List of dictionaries with content and metadata
    """
    return [
        {
            'content': doc.text,
            'metadata': {
                'dataset': dataset_name,
                **doc.metadata
            }
        }
        for doc in documents
    ]

def save_dataset_info(dataset_info: Dict[str, Any], output_path: Path) -> None:
    """Save dataset information to file.
    
    Args:
        dataset_info: Dictionary of dataset information
        output_path: Path to save the info file
    """
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(dataset_info, f, indent=2)

def convert_to_ragas_dataset(llama_dataset: LabelledRagDataset, contexts: List[str]) -> EvaluationDataset:
    """Convert a LlamaIndex dataset to a RAGAs evaluation dataset.
    
    Args:
        llama_dataset: LlamaIndex LabelledRagDataset
        contexts: List of retrieved contexts for each query
        
    Returns:
        RAGAs EvaluationDataset
    """
    samples = []
    for example in llama_dataset.examples:
        sample = SingleTurnSample(
            user_input=example.query,
            retrieved_contexts=contexts,
            response=example.reference_answer,  # Using reference as response for now
            reference=example.reference_answer
        )
        samples.append(sample)
    
    return EvaluationDataset(samples=samples)
