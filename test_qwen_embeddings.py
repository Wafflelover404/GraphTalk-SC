"""
Test script for Qwen embeddings integration.
"""
import torch
from rag_enhanced.embeddings import EnhancedEmbeddingFunction

def test_qwen_embeddings():
    # Check if CUDA is available
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}")
    
    # Initialize the embedding function with Qwen model
    print("Initializing Qwen embedding function...")
    embedder = EnhancedEmbeddingFunction(
        model_name="Qwen/Qwen1.5-7B-Chat",
        device=device,
        batch_size=4  # Small batch size to avoid OOM
    )
    
    # Test texts
    texts = [
        "What is artificial intelligence?",
        "Explain quantum computing in simple terms.",
        "The quick brown fox jumps over the lazy dog.",
        "How does a neural network work?"
    ]
    
    # Get embeddings
    print("\nGenerating embeddings...")
    embeddings = embedder(texts)
    
    # Print results
    print("\nEmbedding dimensions:")
    for i, (text, emb) in enumerate(zip(texts, embeddings)):
        print(f"Text {i+1} (length: {len(emb)}): {text[:50]}...")
    
    # Test similarity
    if len(embeddings) >= 2:
        import numpy as np
        from sklearn.metrics.pairwise import cosine_similarity
        
        # Calculate similarity between first two embeddings
        sim = cosine_similarity(
            np.array(embeddings[0]).reshape(1, -1),
            np.array(embeddings[1]).reshape(1, -1)
        )[0][0]
        
        print(f"\nCosine similarity between first two texts: {sim:.4f}")

if __name__ == "__main__":
    test_qwen_embeddings()
