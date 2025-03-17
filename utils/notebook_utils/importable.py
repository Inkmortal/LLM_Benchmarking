"""
Utility for making Jupyter notebooks importable as Python modules.
This allows RAG implementation notebooks to be used as libraries.
"""

import json
import nbformat
import types
import sys
import inspect
from pathlib import Path
from typing import Any, Dict, Optional


def notebook_to_module(notebook_path: str, module_name: Optional[str] = None) -> types.ModuleType:
    """
    Convert a Jupyter notebook into an importable Python module.
    
    Args:
        notebook_path (str): Path to the notebook file
        module_name (str, optional): Name for the generated module. 
                                   Defaults to notebook filename without extension.
    
    Returns:
        types.ModuleType: Module containing the notebook's code
    
    Example:
        >>> baseline_rag = notebook_to_module('rag_implementations/baseline_rag/implementation.ipynb')
        >>> query_engine = baseline_rag.RAGImplementation()
    """
    # Resolve and validate path
    nb_path = Path(notebook_path)

    # If path is not absolute, resolve it relative to the calling file
    if not nb_path.is_absolute():
        frame = inspect.stack()[1]
        caller_file = Path(frame.filename).resolve()
        nb_path = (caller_file.parent / nb_path).resolve()
    
    # Try project root if path doesn't exist
    if not nb_path.exists():
        raise FileNotFoundError(f"Notebook not found: {notebook_path} (resolved to: {nb_path})")
    
    # Default module name to notebook filename
    if module_name is None:
        module_name = nb_path.stem
    
    # Create empty module
    module = types.ModuleType(module_name)
    module.__file__ = str(nb_path.absolute())
    
    # Load and parse notebook
    with open(nb_path, 'r', encoding='utf-8') as f:
        nb = nbformat.read(f, as_version=4)
    
    # Compile code cells
    code = []
    for cell in nb.cells:
        if cell.cell_type == 'code':
            # Skip cells marked with "# skip-import" comment
            if '# skip-import' in cell.source:
                continue
            code.append(cell.source)
    
    # Join code and compile
    source = '\n\n'.join(code)
    try:
        exec(compile(source, module.__file__, 'exec'), module.__dict__)
    except Exception as e:
        raise ImportError(f"Failed to import notebook {notebook_path}: {str(e)}")
    
    return module


def get_notebook_variables(notebook_path: str) -> Dict[str, Any]:
    """
    Extract variables defined in a notebook.
    Useful for accessing configurations or constants.
    
    Args:
        notebook_path (str): Path to the notebook file
    
    Returns:
        Dict[str, Any]: Dictionary of variable names and values
    """
    module = notebook_to_module(notebook_path)
    return {
        name: value for name, value in module.__dict__.items()
        if not name.startswith('_')  # Skip private/internal variables
    }


class NotebookLoader:
    """
    Context manager for temporarily importing notebooks.
    Useful when you need to import a notebook in a specific context.
    
    Example:
        >>> with NotebookLoader('path/to/notebook.ipynb') as module:
        ...     result = module.some_function()
    """
    
    def __init__(self, notebook_path: str):
        self.notebook_path = notebook_path
        self.module = None
    
    def __enter__(self) -> types.ModuleType:
        self.module = notebook_to_module(self.notebook_path)
        return self.module
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Clean up module if needed
        if self.module and self.module.__name__ in sys.modules:
            del sys.modules[self.module.__name__]
