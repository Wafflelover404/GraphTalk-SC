# AI Citation System - Quick Reference Guide

## 🎯 Overview

The citation system ensures AI responses always reference their sources, providing transparency and traceability.

## 🚀 Quick Start

### Basic Usage

```python
from rag_api.chroma_utils import (
    search_with_full_context,
    create_ai_prompt_with_citations
)

# 1. Search for relevant documents
results = search_with_full_context(
    query="What is machine learning?",
    relevance_threshold=0.5,
    max_results=5
)

# 2. Create AI prompt with citations
prompt = create_ai_prompt_with_citations(
    query="What is machine learning?",
    search_results=results,
    citation_style="inline"
)

# 3. Send to your AI model
# response = your_ai_model.generate(prompt)
```

## 📝 Citation Styles

### 1. Inline (Default)
**Format**: `[filename]`

**Best for**: Conversational AI, chatbots

**Example**:
```
Machine learning enables systems to learn from data [ml_guide.pdf].
```

### 2. Footnote
**Format**: `Source: filename (path)`

**Best for**: Detailed references, documentation

**Example**:
```
Machine learning enables systems to learn from data.

Source: ml_guide.pdf (/documents/ml_guide.pdf)
```

### 3. Academic
**Format**: `filename | Type: .ext | Date: YYYY-MM-DD | Path: /path`

**Best for**: Formal reports, research

**Example**:
```
Machine learning enables systems to learn from data.

ml_guide.pdf | Type: .pdf | Date: 2023-10-14 | Path: /documents/ml_guide.pdf
```

## 🔧 Functions

### 1. `generate_citation()`
Generate a citation for a single document.

```python
from rag_api.chroma_utils import generate_citation

metadata = {
    'filename': 'document.pdf',
    'source': '/path/to/document.pdf',
    'file_type': '.pdf',
    'created_at': 1697299200
}

citation = generate_citation(metadata, citation_style="inline")
# Returns: [document.pdf]
```

### 2. `format_search_results_with_citations()`
Format search results with citations for display or logging.

```python
from rag_api.chroma_utils import format_search_results_with_citations

formatted = format_search_results_with_citations(
    search_results=results,
    citation_style="academic",
    include_relevance_scores=True
)

print(formatted)
```

### 3. `create_ai_prompt_with_citations()`
Create a complete AI prompt with citation instructions.

```python
from rag_api.chroma_utils import create_ai_prompt_with_citations

prompt = create_ai_prompt_with_citations(
    query="Explain neural networks",
    search_results=results,
    citation_style="inline",
    instruction=None  # Optional custom instruction
)
```

## 💡 Advanced Usage

### Custom AI Instructions

```python
custom_instruction = """
You are a technical expert in machine learning.

CITATION REQUIREMENTS:
1. Cite sources using [filename] format
2. Include citations after each claim
3. List all sources at the end
4. Rate source reliability (High/Medium/Low)

Be precise and technical in your explanations.
"""

prompt = create_ai_prompt_with_citations(
    query="How do neural networks learn?",
    search_results=results,
    citation_style="inline",
    instruction=custom_instruction
)
```

### Combining with Full Context

```python
# Get full document content for highly relevant results
results = search_with_full_context(
    query="machine learning algorithms",
    relevance_threshold=0.6,  # Higher threshold for full content
    max_results=10
)

# Create prompt with citations
prompt = create_ai_prompt_with_citations(
    query="machine learning algorithms",
    search_results=results,
    citation_style="academic"
)

# Results will include full document content for top matches
# AI can reference complete context with proper citations
```

### Multiple Citation Styles

```python
# For user-facing responses
user_prompt = create_ai_prompt_with_citations(
    query=user_question,
    search_results=results,
    citation_style="inline"
)

# For internal documentation
doc_prompt = create_ai_prompt_with_citations(
    query=user_question,
    search_results=results,
    citation_style="academic"
)
```

## 📊 Example AI Responses

### Example 1: Technical Explanation

**Query**: "What is deep learning?"

**AI Response**:
```
Deep learning is a subset of machine learning that uses neural networks 
with multiple layers [deep_learning_intro.pdf]. These multi-layered 
networks can automatically learn hierarchical representations of data, 
making them particularly effective for complex tasks like image 
recognition and natural language processing [neural_networks.pdf].

The key advantage of deep learning is its ability to learn features 
automatically from raw data, without manual feature engineering 
[ml_fundamentals.pdf].

Sources cited:
- [deep_learning_intro.pdf] - Relevance: 0.94
- [neural_networks.pdf] - Relevance: 0.87
- [ml_fundamentals.pdf] - Relevance: 0.76
```

### Example 2: Comparative Analysis

**Query**: "Compare supervised and unsupervised learning"

**AI Response**:
```
Supervised learning requires labeled training data where the correct 
outputs are known [ml_basics.pdf]. The algorithm learns to map inputs 
to outputs based on these examples [supervised_learning.pdf].

In contrast, unsupervised learning works with unlabeled data, finding 
patterns and structures without predefined categories [unsupervised_methods.pdf]. 
Common techniques include clustering and dimensionality reduction 
[ml_basics.pdf].

The choice between them depends on data availability and the specific 
problem requirements [ml_basics.pdf, supervised_learning.pdf].

Sources:
- [ml_basics.pdf] - Relevance: 0.91
- [supervised_learning.pdf] - Relevance: 0.88
- [unsupervised_methods.pdf] - Relevance: 0.82
```

## ✅ Best Practices

### 1. Choose Appropriate Citation Style
- **Inline**: Conversational AI, chatbots
- **Footnote**: Documentation, reports
- **Academic**: Research, formal writing

### 2. Set Relevance Thresholds
```python
# For high-quality citations, use higher threshold
results = search_with_full_context(
    query=query,
    relevance_threshold=0.6,  # Only cite highly relevant sources
    max_results=5
)
```

### 3. Customize Instructions
Tailor AI instructions to your use case:
- Technical documentation: Emphasize precision
- User support: Emphasize clarity
- Research: Emphasize completeness

### 4. Verify Citations
Always check that AI responses include citations:
```python
response = ai_model.generate(prompt)

# Verify citations are present
if '[' in response and ']' in response:
    print("✓ Response includes citations")
else:
    print("⚠️ Response missing citations")
```

## 🔍 Troubleshooting

### Issue: AI not citing sources
**Solution**: Strengthen citation instructions
```python
instruction = """
CRITICAL: You MUST cite sources for EVERY claim.
Use [filename] format immediately after each statement.
Never make claims without citations.
"""
```

### Issue: Too many citations
**Solution**: Adjust relevance threshold
```python
# Use higher threshold to get fewer, more relevant sources
results = search_with_full_context(
    query=query,
    relevance_threshold=0.7,  # Increased from 0.5
    max_results=3  # Reduced from 5
)
```

### Issue: Citations not formatted correctly
**Solution**: Verify citation style parameter
```python
# Ensure citation_style is one of: "inline", "footnote", "academic"
prompt = create_ai_prompt_with_citations(
    query=query,
    search_results=results,
    citation_style="inline"  # Check spelling
)
```

## 📚 Integration Examples

### With OpenAI

```python
import openai

results = search_with_full_context(query="machine learning")
prompt = create_ai_prompt_with_citations(query, results)

response = openai.ChatCompletion.create(
    model="gpt-4",
    messages=[{"role": "user", "content": prompt}]
)

print(response.choices[0].message.content)
```

### With Google Gemini

```python
import google.generativeai as genai

results = search_with_full_context(query="machine learning")
prompt = create_ai_prompt_with_citations(query, results)

model = genai.GenerativeModel('gemini-pro')
response = model.generate_content(prompt)

print(response.text)
```

### With Local LLM

```python
from transformers import pipeline

results = search_with_full_context(query="machine learning")
prompt = create_ai_prompt_with_citations(query, results)

generator = pipeline('text-generation', model='mistralai/Mistral-7B-v0.1')
response = generator(prompt, max_length=500)

print(response[0]['generated_text'])
```

## 🎉 Summary

The citation system provides:
- ✅ Automatic source attribution
- ✅ Multiple citation formats
- ✅ Customizable AI instructions
- ✅ Integration with any AI model
- ✅ Transparency and traceability

**Result**: AI responses that are trustworthy, verifiable, and properly sourced!
