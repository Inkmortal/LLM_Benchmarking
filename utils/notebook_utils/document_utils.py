"""Document preprocessing utilities for RAG implementations."""

import os
from typing import List, Dict, Any, Optional, Generator
from tqdm import tqdm

class DocumentPreprocessor:
    """Handles document preprocessing for RAG ingestion"""
    
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        """Initialize preprocessor
        
        Args:
            chunk_size: Maximum number of words per chunk (default 500 words ≈ 2000 chars)
            chunk_overlap: Number of words to overlap between chunks
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
    def clean_text(self, text: str) -> str:
        """Clean and normalize text
        
        Args:
            text: Raw text content
            
        Returns:
            Cleaned text
        """
        # Remove excessive whitespace
        text = ' '.join(text.split())
        
        # TODO: Add more cleaning steps as needed
        return text
    
    def chunk_text(self, text: str) -> List[str]:
        """Split text into overlapping chunks by words
        
        Args:
            text: Text to chunk
            
        Returns:
            List of text chunks
        """
        # Split into words
        words = text.split()
        chunks = []
        start = 0
        
        while start < len(words):
            # Find the end of the chunk
            end = min(start + self.chunk_size, len(words))
            
            # If we're not at the end, try to break at a sentence
            if end < len(words):
                # Look back up to 20 words for a sentence boundary
                for i in range(end-1, max(end-20, start), -1):
                    if words[i].endswith(('.', '!', '?')):
                        end = i + 1
                        break
            
            # Extract the chunk
            chunk = ' '.join(words[start:end]).strip()
            if chunk:  # Only add non-empty chunks
                chunks.append(chunk)
            
            # Move the start position, accounting for overlap
            start = end - self.chunk_overlap
        
        return chunks
    
    def process_document(self, content: str, metadata: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """Process a single document
        
        Args:
            content: Document text content
            metadata: Optional metadata to preserve
            
        Returns:
            List of processed chunks with metadata
        """
        # Clean text
        cleaned_text = self.clean_text(content)
        
        # Split into chunks
        chunks = self.chunk_text(cleaned_text)
        
        # Prepare documents for ingestion
        documents = []
        for i, chunk in enumerate(chunks):
            # Create metadata for chunk
            chunk_metadata = metadata.copy() if metadata else {}
            chunk_metadata.update({
                'chunk_index': i,
                'total_chunks': len(chunks)
            })
            
            documents.append({
                'content': chunk,
                'metadata': chunk_metadata
            })
        
        return documents
    
    def process_text_file(self, file_path: str, metadata: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """Process a text file
        
        Args:
            file_path: Path to text file
            metadata: Optional metadata to preserve
            
        Returns:
            List of processed chunks with metadata
        """
        # Add file info to metadata
        file_metadata = metadata.copy() if metadata else {}
        file_metadata.update({
            'source_file': file_path,
            'file_type': 'text'
        })
        
        # Read and process file
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return self.process_document(content, file_metadata)
    
    def process_directory(self, dir_path: str, metadata: Optional[Dict] = None) -> Generator[Dict[str, Any], None, None]:
        """Process all text files in a directory
        
        Args:
            dir_path: Path to directory
            metadata: Optional metadata to preserve
            
        Yields:
            Processed chunks with metadata
        """
        for root, _, files in os.walk(dir_path):
            for file in files:
                if file.endswith('.txt'):  # TODO: Add support for more file types
                    file_path = os.path.join(root, file)
                    
                    try:
                        documents = self.process_text_file(file_path, metadata)
                        for doc in documents:
                            yield doc
                    except Exception as e:
                        print(f"Error processing {file_path}: {str(e)}")
                        continue

def ingest_documents(source_path: str, rag_system: Any, metadata: Optional[Dict] = None, batch_size: int = 100):
    """Ingest documents from a file or directory into RAG system
    
    Args:
        source_path: Path to file or directory
        rag_system: Any RAG system with ingest_documents method
        metadata: Optional metadata to preserve
        batch_size: Number of documents to process in each batch
    """
    # Initialize preprocessor with system's chunking config if available
    if hasattr(rag_system, 'chunk_size') and hasattr(rag_system, 'chunk_overlap'):
        preprocessor = DocumentPreprocessor(
            chunk_size=rag_system.chunk_size,
            chunk_overlap=rag_system.chunk_overlap
        )
    else:
        preprocessor = DocumentPreprocessor()
    
    # Process and ingest documents
    if os.path.isfile(source_path):
        # Process single file
        documents = preprocessor.process_text_file(source_path, metadata)
        rag_system.ingest_documents(documents, batch_size=batch_size)
    
    elif os.path.isdir(source_path):
        # Process directory
        batch = []
        
        for doc in preprocessor.process_directory(source_path, metadata):
            batch.append(doc)
            
            if len(batch) >= batch_size:
                rag_system.ingest_documents(batch, batch_size=batch_size)
                batch = []
        
        # Ingest any remaining documents
        if batch:
            rag_system.ingest_documents(batch, batch_size=batch_size)
    
    else:
        raise ValueError(f"Invalid source path: {source_path}")
