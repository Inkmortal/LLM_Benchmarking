"""Document processing and entity extraction for graph RAG ingestion."""

import os
import spacy
from pathlib import Path
from typing import List, Dict, Any, Optional
from langchain.document_loaders import (
    PyPDFLoader,
    TextLoader,
    Docx2txtLoader,
    UnstructuredFileLoader
)
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document

class DocumentProcessor:
    """Handles document loading, chunking, and entity extraction."""
    
    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        enable_chunking: bool = True,
        min_entity_freq: int = 2,
        max_relation_distance: int = 10
    ):
        """Initialize document processor.
        
        Args:
            chunk_size: Maximum number of characters per chunk
            chunk_overlap: Number of characters to overlap between chunks
            enable_chunking: Whether to split documents into chunks
            min_entity_freq: Minimum frequency for entity inclusion
            max_relation_distance: Maximum token distance for relationships
        """
        # Document processing config
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.enable_chunking = enable_chunking
        
        # Entity extraction config
        self.min_entity_freq = min_entity_freq
        self.max_relation_distance = max_relation_distance
        
        # Initialize components
        self._init_nlp()
        self._init_text_splitter()
    
    def _init_nlp(self):
        """Initialize SpaCy for entity and relation extraction."""
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            print("Downloading SpaCy model...")
            os.system("python -m spacy download en_core_web_sm")
            self.nlp = spacy.load("en_core_web_sm")
    
    def _init_text_splitter(self):
        """Initialize text splitter if chunking is enabled."""
        self.text_splitter = None
        if self.enable_chunking:
            self.text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
                length_function=len,
                separators=["\\n\\n", "\\n", " ", ""]
            )
    
    def process_files(
        self,
        file_paths: List[str],
        metadata: Optional[Dict] = None
    ) -> List[Dict[str, Any]]:
        """Process documents and extract entities/relations.
        
        Args:
            file_paths: List of paths to documents
            metadata: Optional metadata to add to all documents
            
        Returns:
            List of processed documents with extracted graph data
        """
        # Map file extensions to loaders
        loaders = {
            '.pdf': PyPDFLoader,
            '.txt': TextLoader,
            '.docx': Docx2txtLoader,
            '*': UnstructuredFileLoader
        }
        
        processed_docs = []
        for file_path in file_paths:
            try:
                # Get appropriate loader
                ext = Path(file_path).suffix.lower()
                loader_cls = loaders.get(ext, loaders['*'])
                
                # Load document
                loader = loader_cls(file_path)
                docs = loader.load()
                
                # Add file info to metadata
                file_metadata = metadata.copy() if metadata else {}
                file_metadata.update({
                    'source_file': file_path,
                    'file_type': ext,
                    'file_name': Path(file_path).name
                })
                
                # Add metadata to documents
                for doc in docs:
                    doc.metadata.update(file_metadata)
                
                if self.enable_chunking:
                    # Split into chunks
                    chunks = self.text_splitter.split_documents(docs)
                    
                    # Process each chunk
                    for i, chunk in enumerate(chunks):
                        chunk_metadata = chunk.metadata.copy()
                        chunk_metadata.update({
                            'chunk_index': i,
                            'total_chunks': len(chunks)
                        })
                        
                        # Extract entities and relations
                        graph_data = self._extract_entities_relations(chunk.page_content)
                        
                        processed_docs.append({
                            'content': chunk.page_content,
                            'metadata': chunk_metadata,
                            'graph_data': graph_data
                        })
                else:
                    # Process full documents
                    for doc in docs:
                        # Extract entities and relations
                        graph_data = self._extract_entities_relations(doc.page_content)
                        
                        processed_docs.append({
                            'content': doc.page_content,
                            'metadata': doc.metadata,
                            'graph_data': graph_data
                        })
                    
            except Exception as e:
                print(f"Error processing {file_path}: {str(e)}")
                continue
        
        return processed_docs
    
    def _extract_entities_relations(self, text: str) -> Dict[str, Any]:
        """Extract entities and relations from text.
        
        Args:
            text: Input text to process
            
        Returns:
            Dictionary containing extracted entities and relations
        """
        doc = self.nlp(text)
        
        # Extract entities
        entities = []
        entity_counts = {}
        entity_labels = {}  # Track entity labels for relation extraction
        
        for ent in doc.ents:
            if ent.label_ in ["PERSON", "ORG", "GPE", "DATE", "EVENT"]:
                # Track entity frequency and label
                key = (ent.text, ent.label_)
                entity_counts[key] = entity_counts.get(key, 0) + 1
                entity_labels[ent.text] = ent.label_
                
                if entity_counts[key] >= self.min_entity_freq:
                    entities.append({
                        "text": ent.text,
                        "label": ent.label_,
                        "start": ent.start_char,
                        "end": ent.end_char,
                        "frequency": entity_counts[key]
                    })
        
        # Extract relations
        relations = []
        for token in doc:
            if token.dep_ == "ROOT":
                for child in token.children:
                    if child.dep_ in ["nsubj", "dobj"]:
                        # Check relation distance
                        obj = next((c for c in token.children 
                                  if c.dep_ in ["dobj", "pobj"]), None)
                        if obj and abs(child.i - obj.i) <= self.max_relation_distance:
                            # Only add relation if both entities have labels
                            if child.text in entity_labels and obj.text in entity_labels:
                                relations.append({
                                    "subject": child.text,
                                    "subject_label": entity_labels[child.text],
                                    "predicate": token.text,
                                    "object": obj.text,
                                    "object_label": entity_labels[obj.text],
                                    "distance": abs(child.i - obj.i)
                                })
        
        return {
            "entities": entities,
            "relations": relations
        }
    
    def process_directory(
        self,
        dir_path: str,
        metadata: Optional[Dict] = None,
        recursive: bool = True
    ) -> List[Dict[str, Any]]:
        """Process all documents in a directory.
        
        Args:
            dir_path: Path to directory
            metadata: Optional metadata to add to all documents
            recursive: Whether to process subdirectories
            
        Returns:
            List of processed documents with extracted graph data
        """
        # Get all files
        if recursive:
            file_paths = []
            for root, _, files in os.walk(dir_path):
                for file in files:
                    if file.endswith(('.txt', '.pdf', '.docx')):
                        file_paths.append(os.path.join(root, file))
        else:
            file_paths = [
                os.path.join(dir_path, f) for f in os.listdir(dir_path)
                if f.endswith(('.txt', '.pdf', '.docx'))
            ]
        
        return self.process_files(file_paths, metadata)
