# llm.py - Language Model Integration

## Overview
Provides AI-powered response generation using language models to create human-readable answers from knowledge base search results. This module is also a core component of the RAG (Retrieval-Augmented Generation) pipeline, bridging the gap between raw KB data and natural language responses.

## Key Features
- **GPT-4 Integration**: Uses GPT-4o-mini for cost-effective AI responses
- **Context-Aware**: Combines user queries with KB search results
- **No Web Search**: Focuses purely on knowledge base content
- **Simple Interface**: Single function for LLM calls

## Core Function

### `llm_call(message, data)`
Generates human-readable responses using LLM based on user query and knowledge base data.

#### Parameters
- `message` (str): The user's original question or request
- `data` (str): Knowledge base search results as context

#### Returns
- `str`: AI-generated response that combines the KB data with natural language explanation

#### System Prompt Strategy
The function uses a three-part prompt structure:
1. **System Instructions**: Defines the AI's role as a KB assistant
2. **Knowledge Base Context**: Provides the search results as reference data
3. **User Request**: The actual user query to be answered

## Implementation Details

### Model Configuration
- **Model**: `gpt-4o-mini` (cost-effective GPT-4 variant)
- **Provider**: g4f (GPT4Free) client
- **Web Search**: Disabled (focuses on provided KB data only)
- **Temperature**: Default (balanced creativity/accuracy)

### Message Structure
```python
messages = [
    {
        "role": "system", 
        "content": "Instructions - {system_prompt}"
    },
    {
        "role": "system", 
        "content": "Knowledge base search query - {data}"
    },
    {
        "role": "user", 
        "content": "user request - {message}"
    }
]
```

## Usage Examples

### Basic Response Generation
```python
from llm import llm_call

# KB search results
kb_data = [
    "Keynode: ostis_technology",
    "Link Content: OSTIS is a technology for building knowledge bases",
    "Link Content: Semantic networks are used in OSTIS"
]

# Generate human response
user_question = "What is OSTIS technology?"
response = llm_call(user_question, "\n".join(kb_data))

print(response)
# Output: "OSTIS technology is a framework for building knowledge bases that utilizes semantic networks..."
```

### Integration with Search
```python
from sc_search import kb_search
from llm import llm_call

# Complete workflow
query = "How do semantic networks work?"

# 1. Search knowledge base
kb_results = kb_search(query)

# 2. Generate human response
if kb_results:
    context = "\n".join(kb_results)
    human_response = llm_call(query, context)
    print(human_response)
else:
    print("No information found in knowledge base")
```

### API Integration
```python
# In api.py
@app.post("/query")
async def process_query(request: QueryRequest, humanize: bool = False, use_rag: bool = False):
    kb_results = kb_search(request.text)
    
        if use_rag:
        # RAG logic will retrieve context and call the LLM.
        # This is a simplified representation.
        rag_context = get_rag_context(request.text)
        response = llm_call(request.text, rag_context)
    elif humanize:
        context = "\n".join(kb_results) if isinstance(kb_results, list) else kb_results
        response = llm_call(request.text, context)
    else:
        response = kb_results
        
    return APIResponse(status="success", response=response)
```

## System Prompt Analysis

The system prompt instructs the AI to:
1. **Act as KB Assistant**: Focus on knowledge base content
2. **Analyze Provided Data**: Extract relevant information from search results
3. **Provide Helpful Answers**: Generate concise, relevant responses
4. **Reason from Context**: Base answers on the provided KB data

```
"You are an AI assistant. You receive a bunch of data from a knowledge base. 
Your task is to analyze this data and provide a helpful, concise answer based on the user's message. 
Focus on extracting relevant information and reasoning from the knowledge base data in the context of the user's query."
```

## Response Quality Features

### Context Integration
- Combines multiple KB search results into coherent explanations
- Maintains focus on knowledge base content
- Avoids hallucination by grounding responses in provided data

### Natural Language Processing
- Converts technical KB identifiers into readable explanations
- Structures information logically for human consumption
- Provides reasoning and connections between concepts

### Conciseness
- Generates focused responses without unnecessary elaboration
- Balances completeness with readability
- Adapts response length to available KB data

## Error Handling

### Connection Issues
```python
def safe_llm_call(message, data):
    try:
        return llm_call(message, data)
    except Exception as e:
        return f"Error generating response: {str(e)}"
```

### Empty Data Handling
```python
# In API integration
if not kb_results or not any(kb_results):
    return "No relevant information found in knowledge base"
    
context = "\n".join(kb_results)
if not context.strip():
    return "Knowledge base search returned empty results"
    
response = llm_call(query, context)
```

## Performance Considerations

### API Limits
- g4f client may have rate limits
- Consider implementing retry logic for production
- Monitor API usage for cost management

### Response Time
- LLM calls add latency to search responses
- Consider caching for frequent queries
- Implement timeout handling

### Quality Control
- Responses depend on KB data quality
- Better search results lead to better LLM responses
- Consider response validation for critical applications

## Configuration Options

### Model Selection
```python
# Alternative models (modify in llm_call)
response = client.chat.completions.create(
    model="gpt-4",          # Higher quality, more expensive
    model="gpt-3.5-turbo",  # Faster, less expensive
    model="gpt-4o-mini",    # Current default
    # ... rest of parameters
)
```

### Temperature Control
```python
# Add temperature parameter for creativity control
response = client.chat.completions.create(
    model="gpt-4o-mini",
    temperature=0.7,  # 0.0 = deterministic, 1.0 = creative
    # ... rest of parameters
)
```

## Integration Patterns

### Simple Humanization
```python
# Direct KB-to-human conversion
raw_results = kb_search("query")
human_response = llm_call("query", "\n".join(raw_results))
```

### Multi-step Processing
```python
# Complex workflow with validation
raw_results = kb_search("query")
if validate_kb_results(raw_results):
    processed_context = preprocess_kb_data(raw_results)
    response = llm_call("query", processed_context)
    return postprocess_response(response)
```

### Fallback Strategy
```python
# Graceful degradation
try:
    human_response = llm_call(query, kb_data)
    return human_response
except Exception:
    return kb_data  # Return raw results if LLM fails
```

## Best Practices

1. **Data Quality**: Ensure KB search results are relevant and clean
2. **Context Size**: Monitor token limits for large KB result sets
3. **Error Handling**: Implement fallbacks for LLM failures
4. **Cost Management**: Monitor API usage and costs
5. **Response Validation**: Check response quality and relevance
6. **Caching**: Cache responses for repeated queries when appropriate
