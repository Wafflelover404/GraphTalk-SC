#!/usr/bin/env python3
"""
Example: How AI receives full file content with every search result
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'rag_api'))

def demonstrate_full_context():
    """Demonstrate how AI receives complete file content"""
    print("=" * 70)
    print("AI with Full File Context - Complete Example")
    print("=" * 70)
    
    from chroma_utils import create_ai_prompt_with_citations
    from langchain_core.documents import Document
    
    # Simulate search results with full file content
    # This is what search_documents() now returns automatically
    mock_results = {
        'semantic_results': [
            Document(
                page_content="Machine learning is a subset of AI that enables systems to learn from data.",
                metadata={
                    'filename': 'ml_guide.pdf',
                    'source': '/docs/ml_guide.pdf',
                    'relevance_score': 0.92,
                    # FULL FILE CONTENT - automatically included!
                    'full_file_content': """# Complete Machine Learning Guide

## Introduction
Machine learning is a subset of AI that enables systems to learn from data.
It's revolutionizing how we approach complex problems.

## Types of Machine Learning

### Supervised Learning
Uses labeled data to train models. Examples:
- Classification (spam detection)
- Regression (price prediction)

### Unsupervised Learning
Finds patterns in unlabeled data. Examples:
- Clustering (customer segmentation)
- Dimensionality reduction (data compression)

### Reinforcement Learning
Learns through trial and error with rewards. Examples:
- Game playing (AlphaGo)
- Robotics (autonomous navigation)

## Key Algorithms
1. Linear Regression
2. Decision Trees
3. Neural Networks
4. Support Vector Machines
5. K-Means Clustering

## Applications
- Healthcare: Disease diagnosis
- Finance: Fraud detection
- Retail: Recommendation systems
- Transportation: Autonomous vehicles

## Conclusion
Machine learning continues to advance rapidly, with new techniques
and applications emerging constantly."""
                }
            )
        ],
        'stats': {'total_checked': 100}
    }
    
    print("\n📊 What the System Does:")
    print("-" * 70)
    print("1. User searches: 'What is reinforcement learning?'")
    print("2. System finds relevant chunk: 'Machine learning is a subset...'")
    print("3. System AUTOMATICALLY retrieves ENTIRE file")
    print("4. Both chunk AND full file sent to AI")
    
    print("\n🤖 Creating AI Prompt with Full Context...")
    print("-" * 70)
    
    prompt = create_ai_prompt_with_citations(
        query="What is reinforcement learning and give me examples?",
        search_results=mock_results,
        citation_style="inline"
    )
    
    # Show what AI receives
    print("\n" + "=" * 70)
    print("WHAT AI RECEIVES:")
    print("=" * 70)
    print(prompt[:1500] + "\n... [truncated for display] ...\n")
    
    print("\n" + "=" * 70)
    print("KEY POINTS:")
    print("=" * 70)
    
    points = """
✅ AI gets the RELEVANT CHUNK:
   "Machine learning is a subset of AI..."
   
✅ AI gets the COMPLETE FILE:
   - Introduction
   - Types of Machine Learning (including Reinforcement Learning!)
   - Key Algorithms
   - Applications
   - Conclusion

✅ Even though the chunk doesn't mention "reinforcement learning",
   the AI can find it in the complete file and answer correctly!

✅ AI can cite specific sections:
   "Reinforcement learning learns through trial and error [ml_guide.pdf].
    Examples include game playing like AlphaGo and autonomous navigation
    [ml_guide.pdf - see Reinforcement Learning section]."
"""
    
    print(points)
    
    print("\n" + "=" * 70)
    print("EXAMPLE AI RESPONSE:")
    print("=" * 70)
    
    example_response = """
Based on the provided document [ml_guide.pdf], reinforcement learning 
is a type of machine learning that learns through trial and error with 
rewards.

Key characteristics:
- Uses reward-based learning approach
- Learns optimal actions through experience
- Does not require labeled training data

Examples from the document:
1. Game Playing: AlphaGo - the AI that mastered the game of Go
2. Robotics: Autonomous navigation systems

The document also mentions that reinforcement learning is one of three
main types of machine learning, alongside supervised and unsupervised 
learning [ml_guide.pdf - see Types of Machine Learning section].

Source: [ml_guide.pdf]
"""
    
    print(example_response)
    
    print("\n" + "=" * 70)
    print("WHY THIS WORKS:")
    print("=" * 70)
    
    explanation = """
❌ OLD WAY (chunk only):
   Query: "What is reinforcement learning?"
   Chunk: "Machine learning is a subset of AI..."
   AI: "I don't have information about reinforcement learning"
   
✅ NEW WAY (chunk + full file):
   Query: "What is reinforcement learning?"
   Chunk: "Machine learning is a subset of AI..."
   Full File: [Complete guide including RL section]
   AI: "Reinforcement learning learns through trial and error...
        Examples include AlphaGo and autonomous navigation [ml_guide.pdf]"

The answer was in a DIFFERENT CHUNK of the same file!
Now AI has the COMPLETE file and can find it!
"""
    
    print(explanation)
    
    print("\n" + "=" * 70)
    print("REAL USAGE:")
    print("=" * 70)
    
    usage = """
from rag_api.chroma_utils import search_documents, create_ai_prompt_with_citations

# 1. Search (automatically gets full files)
results = search_documents(
    query="What is reinforcement learning?",
    max_results=5
)

# 2. Create AI prompt
prompt = create_ai_prompt_with_citations(
    query="What is reinforcement learning?",
    search_results=results,
    citation_style="inline"
)

# 3. Send to AI
# response = your_ai_model.generate(prompt)

# AI will have:
# - All relevant chunks
# - Complete source files for each chunk
# - Citation instructions
# - Ability to find answers anywhere in the files!
"""
    
    print(usage)
    
    print("\n" + "=" * 70)
    print("✅ AI Now Has Complete Context for Every Search!")
    print("=" * 70)
    
    return True

if __name__ == "__main__":
    try:
        demonstrate_full_context()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
