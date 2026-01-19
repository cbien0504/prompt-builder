"""Text chunking logic for code files using simplified AST-based chunking."""

from __future__ import annotations

import os
from typing import List, Tuple, Optional
import logging

import tiktoken
import tree_sitter_language_pack

logger = logging.getLogger(__name__)

# Initialize tiktoken encoder (cl100k_base is compatible with most modern models)
_ENCODER = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    """Count tokens in text using tiktoken.
    
    Args:
        text: Text to count tokens for
        
    Returns:
        Number of tokens
    """
    return len(_ENCODER.encode(text))

# Supported languages for AST-based chunking
EXT_TO_LANG = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".c": "c",
    ".h": "c",
    ".hpp": "cpp",
    ".php": "php",
    ".rb": "ruby",
    ".cs": "c_sharp",
}

# File extensions that should use line-based chunking as fallback
FALLBACK_EXTENSIONS = {
    ".json", ".yaml", ".yml", ".toml", ".xml", ".html", ".css", ".scss", ".sass",
    ".md", ".txt", ".rst", ".ini", ".cfg", ".conf", ".env", ".gitignore",
    ".sql", ".sh", ".bash", ".zsh", ".fish", ".dockerfile", ".lock",
}

def get_language_for_file(filename: str) -> Optional[str]:
    """Get language name from file extension."""
    _, ext = os.path.splitext(filename)
    return EXT_TO_LANG.get(ext.lower())

def get_definition_types(language: str) -> set:
    """Get AST node types that represent top-level definitions.
    
    These are the node types we want to keep as complete units (not split).
    
    Args:
        language: Language name (python, javascript, etc)
        
    Returns:
        Set of AST node type names
    """
    mappings = {
        "python": {
            "function_definition", 
            "class_definition",
            "decorated_definition"  # decorators + function/class
        },
        "javascript": {
            "function_declaration", 
            "class_declaration", 
            "method_definition",
            "export_statement",  # export function/class
        },
        "typescript": {
            "function_declaration", 
            "class_declaration", 
            "method_definition",
            "interface_declaration",
            "type_alias_declaration",
            "export_statement",
        },
        "go": {
            "function_declaration", 
            "method_declaration",
            "type_declaration",
        },
        "rust": {
            "function_item", 
            "struct_item", 
            "impl_item",
            "trait_item",
            "enum_item",
        },
        "java": {
            "method_declaration", 
            "class_declaration",
            "interface_declaration",
        },
        "cpp": {
            "function_definition",
            "class_specifier",
            "struct_specifier",
        },
        "c": {
            "function_definition",
            "struct_specifier",
        },
        "php": {
            "function_definition",
            "class_declaration",
            "method_declaration",
        },
        "ruby": {
            "method",
            "class",
            "module",
        },
        "c_sharp": {
            "method_declaration",
            "class_declaration",
            "interface_declaration",
        },
    }
    return mappings.get(language, {"function_definition", "class_definition"})

# -----------------------------------------------------------------------------
# Interfaces
# -----------------------------------------------------------------------------

class Chunker:
    """Abstract base class for text chunking."""
    
    def chunk(self, lines: List[str], file_path: Optional[str] = None) -> List[Tuple[int, int, str]]:
        """Chunk text into semantic blocks.
        
        Args:
            lines: List of text lines
            file_path: Path to the file (optional, for language detection)
            
        Returns:
            List of (start_line, end_line, text) tuples
        """
        raise NotImplementedError


class DefaultChunker(Chunker):
    """Default chunker using AST-based or line-based strategy."""
    
    def __init__(self, max_tokens: int = 2000, overlap: int = 0, min_lines: int = 1):
        self.max_tokens = max_tokens
        self.overlap = overlap
        self.min_lines = min_lines

    def chunk(self, lines: List[str], file_path: Optional[str] = None) -> List[Tuple[int, int, str]]:
        if not lines:
            return []
        
        text = "".join(lines)
        total_tokens = count_tokens(text)
        total_lines = len(lines)
        
        # Adaptive strategy: small files kept as single chunk
        if total_tokens <= self.max_tokens:
            logger.debug(f"File {file_path or 'unknown'}: {total_tokens} tokens, keeping as single chunk")
            return [(1, total_lines, text)]
        
        logger.debug(f"File {file_path or 'unknown'}: {total_tokens} tokens, chunking required")
        
        # Check if file supports AST chunking
        if file_path:
            lang_name = get_language_for_file(file_path)
            if lang_name:
                # Use AST chunking for supported languages
                try:
                    return chunk_ast(text, lang_name, self.max_tokens, self.overlap, self.min_lines)
                except Exception as e:
                    logger.warning(f"AST chunking failed for {file_path}, falling back to line-based: {e}")
                    # Fall through to line-based chunking
        
        # Fallback to line-based chunking for unsupported file types
        _, ext = os.path.splitext(file_path) if file_path else ("", "")
        if ext.lower() in FALLBACK_EXTENSIONS or not file_path:
            logger.debug(f"Using line-based chunking for {file_path or 'unknown file'}")
        
        return chunk_lines(lines, self.max_tokens, self.overlap, self.min_lines)


def chunk_text(lines: List[str], max_tokens: int, overlap: int, min_lines: int, file_path: str = None) -> List[Tuple[int, int, str]]:
    """Chunk text using token-based adaptive chunking (Functional Wrapper)."""
    chunker = DefaultChunker(max_tokens=max_tokens, overlap=overlap, min_lines=min_lines)
    return chunker.chunk(lines, file_path=file_path)


def chunk_ast(text: str, language: str, max_tokens: int, overlap: int, min_lines: int) -> List[Tuple[int, int, str]]:
    """Simplified AST chunking: group complete top-level definitions by token count.
    
    Strategy:
    1. Extract all top-level definitions (functions, classes, etc.)
    2. Group them into chunks that don't exceed max_tokens
    3. Keep complete definitions intact (don't split them)
    4. Include some overlap by starting new chunks before previous chunk ends
    
    Args:
        text: Source code text
        language: Programming language
        max_tokens: Maximum tokens per chunk
        overlap: Number of tokens to overlap between chunks
        min_lines: Minimum lines for a valid chunk (filter out tiny chunks)
        
    Returns:
        List of (start_line_1based, end_line_1based_inclusive, text) tuples
    """
    parser = tree_sitter_language_pack.get_parser(language)
    tree = parser.parse(text.encode("utf-8"))
    root_node = tree.root_node
    
    lines = text.splitlines(keepends=True)
    total_lines = len(lines)
    
    # Extract all top-level definitions
    definition_types = get_definition_types(language)
    definitions = []
    
    for child in root_node.children:
        # Only include actual definitions, skip comments/imports/whitespace
        if child.type in definition_types:
            start_line = child.start_point[0]  # 0-indexed
            end_line = child.end_point[0]  # 0-indexed
            definitions.append((start_line, end_line))
    
    # If no definitions found, fallback to line-based
    if not definitions:
        logger.debug(f"No definitions found for {language}, using fallback")
        return chunk_lines(lines, max_tokens, overlap, min_lines)
    
    logger.debug(f"Found {len(definitions)} definitions for {language} file")
    
    # Group definitions into chunks based on token count
    chunks = []
    i = 0
    
    while i < len(definitions):
        chunk_start = definitions[i][0]
        chunk_end = definitions[i][1]
        j = i + 1
        
        # Get current chunk text
        chunk_text = "".join(lines[chunk_start:chunk_end + 1])
        chunk_tokens = count_tokens(chunk_text)
        
        # Try to add more definitions to current chunk
        while j < len(definitions):
            next_start, next_end = definitions[j]
            # Calculate potential chunk text
            potential_text = "".join(lines[chunk_start:next_end + 1])
            potential_tokens = count_tokens(potential_text)
            
            if potential_tokens <= max_tokens:
                chunk_end = next_end
                chunk_text = potential_text
                chunk_tokens = potential_tokens
                j += 1
            else:
                break
        
        # Add this chunk
        chunks.append((chunk_start, chunk_end, chunk_text, chunk_tokens))
        
        # Move to next chunk with overlap
        # Find definition that starts around (current_position - overlap_tokens)
        i = j  # Default: continue from where we stopped
        
        # Try to create overlap by backtracking
        if i < len(definitions) and overlap > 0:
            # Go back to find a good overlap point
            for k in range(i - 1, max(i - 3, 0), -1):
                overlap_text = "".join(lines[definitions[k][0]:chunk_end + 1])
                overlap_tokens = count_tokens(overlap_text)
                if overlap_tokens >= overlap and overlap_tokens < max_tokens:
                    i = k
                    break
    
    # Filter out chunks that are too small (by line count)
    chunks = [(s, e, txt, tok) for s, e, txt, tok in chunks if (e - s + 1) >= min_lines]
    
    # Convert to result format (0-indexed to 1-indexed)
    result = []
    for start, end, chunk_text, chunk_tokens in chunks:
        result.append((start + 1, end + 1, chunk_text))
    
    logger.info(f"Created {len(result)} semantic chunks from {len(definitions)} definitions")
    return result

def chunk_lines(lines: List[str], max_tokens: int, overlap: int, min_lines: int) -> List[Tuple[int, int, str]]:
    """Token-based line chunking with overlap for files that don't support AST.
    
    Uses binary search to find optimal number of lines that fit within max_tokens.
    
    Args:
        lines: List of text lines
        max_tokens: Maximum tokens per chunk
        overlap: Number of overlapping tokens between chunks
        min_lines: Minimum lines for a valid chunk
    
    Returns:
        List of (start_line_1based, end_line_1based_inclusive, text) tuples
    """
    if not lines:
        return []
    
    chunks = []
    total_lines = len(lines)
    start_idx = 0
    
    while start_idx < total_lines:
        # Binary search to find max lines that fit in max_tokens
        left, right = 1, total_lines - start_idx
        best_end = start_idx + 1
        
        while left <= right:
            mid = (left + right) // 2
            end_idx = min(start_idx + mid, total_lines)
            chunk_text = "".join(lines[start_idx:end_idx])
            chunk_tokens = count_tokens(chunk_text)
            
            if chunk_tokens <= max_tokens:
                best_end = end_idx
                left = mid + 1  # Try to include more lines
            else:
                right = mid - 1  # Too many tokens, reduce lines
        
        end_idx = best_end
        chunk_text = "".join(lines[start_idx:end_idx])
        num_lines = end_idx - start_idx
        
        # Only add if meets minimum line requirement
        if num_lines >= min_lines or start_idx == 0:
            # Convert to 1-based indexing
            chunks.append((start_idx + 1, end_idx, chunk_text))
        
        # Move to next chunk with overlap
        # If this is the last chunk, break
        if end_idx >= total_lines:
            break
        
        # Calculate overlap in lines (approximate)
        # Binary search to find overlap point
        overlap_start = start_idx
        if overlap > 0:
            left, right = 0, end_idx - start_idx - 1
            while left <= right:
                mid = (left + right) // 2
                overlap_text = "".join(lines[end_idx - mid:end_idx])
                overlap_tokens = count_tokens(overlap_text)
                
                if overlap_tokens < overlap:
                    left = mid + 1
                else:
                    overlap_start = end_idx - mid
                    right = mid - 1
        
        # Advance to next chunk
        start_idx = max(end_idx - (end_idx - overlap_start), end_idx - (total_lines - end_idx))
        if start_idx >= end_idx:
            start_idx = end_idx
    
    return chunks
