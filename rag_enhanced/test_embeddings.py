#!/usr/bin/env python3
"""
Test script for Qwen embeddings.
"""
import sys
import torch
from pathlib import Path
from embeddings import EnhancedEmbeddingFunction

def main():
    print("Testing Qwen embeddings...")
    
    # Check if CUDA is available
    print(f"CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"CUDA device: {torch.cuda.get_device_name(0)}")
    
    # Initialize the embedding function
    print("\nInitializing Qwen embedding function...")
    embedder = EnhancedEmbeddingFunction(
        model_name="cross-encoder/ms-marco-TinyBERT-L-2-v2",
        device="cuda" if torch.cuda.is_available() else "cpu",
        batch_size=4
    )
    
    # Test texts
    test_texts = [
        "The quick brown fox jumps over the lazy dog.",
        "Artificial intelligence is transforming the world.",
        "The capital of France is Paris.",
        "Machine learning is a subset of artificial intelligence."
    ]
    
    # Get embeddings
    print("\nGenerating embeddings...")
    embeddings = embedder(test_texts)
    
    # Print results
    print("\nEmbedding dimensions:")
    for i, (text, emb) in enumerate(zip(test_texts, embeddings)):
        print(f"Text {i+1} (length: {len(text)} chars) -> Embedding dim: {len(emb)}")
    
    print("\nTest completed successfully!")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
