#!/usr/bin/env python3
"""
Test and demonstrate the citation system for AI responses
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'rag_api'))

def test_citation_generation():
    """Test citation generation in different styles"""
    from chroma_utils import generate_citation, format_search_results_with_citations, create_ai_prompt_with_citations
    from langchain_core.documents import Document
    
    print("=" * 70)
    print("AI Citation System Test")
    print("=" * 70)
    
    # Sample metadata
    metadata = {
        'filename': 'machine_learning_guide.pdf',
        'source': '/documents/ml/machine_learning_guide.pdf',
        'file_type': '.pdf',
        'created_at': 1697299200,  # Oct 14, 2023
        'relevance_score': 0.87
    }
    
    # Test 1: Different citation styles
    print("\n1️⃣  Testing Citation Styles")
    print("-" * 70)
    
    inline = generate_citation(metadata, "inline")
    print(f"Inline:    {inline}")
    
    footnote = generate_citation(metadata, "footnote")
    print(f"Footnote:  {footnote}")
    
    academic = generate_citation(metadata, "academic")
    print(f"Academic:  {academic}")
    
    # Test 2: Format search results with citations
    print("\n2️⃣  Testing Formatted Search Results")
    print("-" * 70)
    
    # Create mock search results
    mock_results = {
        'semantic_results': [
            Document(
                page_content="Machine learning is a subset of AI that enables systems to learn from data without explicit programming.",
                metadata={
                    'filename': 'ml_basics.pdf',
                    'source': '/docs/ml_basics.pdf',
                    'relevance_score': 0.92
                }
            ),
            Document(
                page_content="Deep learning uses neural networks with multiple layers to process complex patterns.",
                metadata={
                    'filename': 'deep_learning.pdf',
                    'source': '/docs/deep_learning.pdf',
                    'relevance_score': 0.78
                }
            )
        ],
        'stats': {'total_checked': 100}
    }
    
    formatted = format_search_results_with_citations(
        mock_results,
        citation_style="inline",
        include_relevance_scores=True
    )
    
    print(formatted[:500] + "...\n")
    
    # Test 3: Complete AI prompt with citations
    print("\n3️⃣  Testing Complete AI Prompt Generation")
    print("-" * 70)
    
    query = "What is machine learning and how does it work?"
    
    prompt = create_ai_prompt_with_citations(
        query=query,
        search_results=mock_results,
        citation_style="inline"
    )
    
    print(prompt[:800] + "...\n")
    
    # Test 4: Show example AI response format
    print("\n4️⃣  Example AI Response with Citations")
    print("-" * 70)
    
    example_response = """
Based on the provided sources, I can explain machine learning:

Machine learning is a subset of AI that enables systems to learn from 
data without explicit programming [ml_basics.pdf]. This approach allows 
computers to improve their performance on tasks through experience rather 
than being explicitly coded for every scenario [ml_basics.pdf].

One important technique in machine learning is deep learning, which uses 
neural networks with multiple layers to process complex patterns 
[deep_learning.pdf]. This multi-layered approach is particularly effective 
for tasks like image recognition and natural language processing 
[deep_learning.pdf].

Sources cited:
- [ml_basics.pdf] - Relevance: 0.92
- [deep_learning.pdf] - Relevance: 0.78
"""
    
    print(example_response)
    
    print("\n" + "=" * 70)
    print("Citation System Features")
    print("=" * 70)
    
    features = """
✅ Multiple Citation Styles:
   - Inline: [filename]
   - Footnote: Source: filename (path)
   - Academic: filename | Type: .pdf | Date: 2023-10-14 | Path: /path

✅ Automatic Formatting:
   - Formats search results with citations
   - Includes relevance scores
   - Handles full content and excerpts

✅ AI Prompt Generation:
   - Creates complete prompts with citation instructions
   - Includes all source documents
   - Enforces citation rules

✅ Flexible Integration:
   - Works with regular search results
   - Works with full context search
   - Customizable citation styles
   - Custom AI instructions
"""
    
    print(features)
    
    print("\n" + "=" * 70)
    print("Usage Examples")
    print("=" * 70)
    
    usage = """
# Example 1: Search and create AI prompt with citations
from rag_api.chroma_utils import search_with_full_context, create_ai_prompt_with_citations

# Search for relevant documents
results = search_with_full_context(
    query="How does machine learning work?",
    relevance_threshold=0.5,
    max_results=5
)

# Create prompt for AI with citations
prompt = create_ai_prompt_with_citations(
    query="How does machine learning work?",
    search_results=results,
    citation_style="inline"  # or "footnote" or "academic"
)

# Send to AI (e.g., OpenAI, Gemini, etc.)
# The AI will respond with proper citations!

# Example 2: Custom citation instruction
custom_instruction = '''
You are a technical expert. Provide detailed explanations.
ALWAYS cite sources using [filename] format.
If you reference specific data or claims, cite the source immediately.
'''

prompt = create_ai_prompt_with_citations(
    query="Explain neural networks",
    search_results=results,
    citation_style="inline",
    instruction=custom_instruction
)

# Example 3: Format results for display
from rag_api.chroma_utils import format_search_results_with_citations

formatted = format_search_results_with_citations(
    results,
    citation_style="academic",
    include_relevance_scores=True
)

print(formatted)  # Show to user or log
"""
    
    print(usage)
    
    print("\n" + "=" * 70)
    print("✅ Citation System Ready for AI Integration!")
    print("=" * 70)
    
    return True

if __name__ == "__main__":
    try:
        success = test_citation_generation()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
