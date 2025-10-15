#!/usr/bin/env python3
"""
Example: How AI cites files in responses
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'rag_api'))

def show_citation_example():
    """Show how AI will cite files"""
    print("=" * 70)
    print("AI File Citation Example")
    print("=" * 70)
    
    from chroma_utils import create_ai_prompt_with_citations
    from langchain_core.documents import Document
    
    # Mock search results
    mock_results = {
        'semantic_results': [
            Document(
                page_content="Machine learning is a subset of AI.",
                metadata={
                    'filename': 'ml_basics.pdf',
                    'relevance_score': 0.95,
                    'full_file_content': """Machine learning is a subset of AI that enables systems to learn from data.

Types of ML:
- Supervised learning
- Unsupervised learning  
- Reinforcement learning

Applications include image recognition and natural language processing."""
                }
            ),
            Document(
                page_content="Deep learning uses neural networks.",
                metadata={
                    'filename': 'deep_learning.pdf',
                    'relevance_score': 0.87,
                    'full_file_content': """Deep learning is a type of machine learning using neural networks with multiple layers.

Key concepts:
- Convolutional Neural Networks (CNNs)
- Recurrent Neural Networks (RNNs)
- Transformers

Used in computer vision and NLP tasks."""
                }
            )
        ]
    }
    
    print("\n1️⃣  Creating AI Prompt with Citation Requirements")
    print("-" * 70)
    
    prompt = create_ai_prompt_with_citations(
        query="What is machine learning and what are its types?",
        search_results=mock_results,
        citation_style="inline"
    )
    
    print("Prompt created with strict citation rules!")
    print("\n2️⃣  What AI Receives:")
    print("-" * 70)
    print(prompt[:800] + "\n...[truncated]...\n")
    
    print("\n3️⃣  Example AI Response (CORRECT FORMAT):")
    print("=" * 70)
    
    correct_response = """Files used: ml_basics.pdf, deep_learning.pdf

Machine learning is a subset of AI that enables systems to learn from 
data [ml_basics.pdf]. 

There are three main types of machine learning [ml_basics.pdf]:
1. Supervised learning - uses labeled data
2. Unsupervised learning - finds patterns in unlabeled data
3. Reinforcement learning - learns through trial and error

Machine learning has various applications including image recognition 
and natural language processing [ml_basics.pdf].

Deep learning is a specific type of machine learning that uses neural 
networks with multiple layers [deep_learning.pdf]. It's particularly 
effective for computer vision and NLP tasks [deep_learning.pdf].

Sources used:
- [ml_basics.pdf]
- [deep_learning.pdf]"""
    
    print(correct_response)
    
    print("\n\n4️⃣  Key Features of the Response:")
    print("=" * 70)
    
    features = """
✅ Starts with "Files used:" listing all sources
✅ Every statement has [filename] citation
✅ Multiple citations when using multiple sources
✅ Ends with "Sources used:" section
✅ Clear, traceable information
"""
    
    print(features)
    
    print("\n5️⃣  What Makes This Work:")
    print("=" * 70)
    
    explanation = """
The prompt includes:

1. STRICT INSTRUCTIONS:
   - "You MUST cite the source file for EVERY piece of information"
   - "Use the format [filename] immediately after each statement"
   - "NEVER provide information without a citation"

2. CLEAR FORMAT:
   - Shows exact format to follow
   - Provides example
   - Requires "Files used:" at start
   - Requires "Sources used:" at end

3. COMPLETE CONTEXT:
   - AI gets full file content
   - Can find information anywhere in files
   - Has all necessary information to cite correctly

4. ENFORCEMENT:
   - Format is mandatory
   - Example shows how to do it
   - Instructions are explicit and clear
"""
    
    print(explanation)
    
    print("\n6️⃣  Usage in Your Code:")
    print("=" * 70)
    
    usage = """
from rag_api.chroma_utils import search_documents, create_ai_prompt_with_citations

# 1. Search (gets full file content automatically)
results = search_documents(
    query="What is machine learning?",
    max_results=5
)

# 2. Create prompt with strict citation requirements
prompt = create_ai_prompt_with_citations(
    query="What is machine learning?",
    search_results=results,
    citation_style="inline"  # or "footnote" or "academic"
)

# 3. Send to AI
# response = your_ai_model.generate(prompt)

# AI will respond with:
# - "Files used: [list]"
# - Answer with [filename] after each statement
# - "Sources used: [list]"

# Example response:
# "Files used: ml_guide.pdf
#  
#  Machine learning is a subset of AI [ml_guide.pdf].
#  It has three main types: supervised, unsupervised, and 
#  reinforcement learning [ml_guide.pdf].
#  
#  Sources used:
#  - [ml_guide.pdf]"
"""
    
    print(usage)
    
    print("\n" + "=" * 70)
    print("✅ AI Will Now Clearly Cite All Files Used!")
    print("=" * 70)
    
    return True

if __name__ == "__main__":
    try:
        show_citation_example()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
