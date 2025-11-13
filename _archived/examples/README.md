# Example Scripts

These files demonstrate how to use the RAG API and show best practices for integrating with the system.

## Available Examples

### `example_ai_citations.py`
Demonstrates how to generate AI responses with proper citations from source documents.

**Key Features:**
- Query the RAG system
- Generate AI responses with citations
- Format citations properly
- Reference source documents

**Usage:**
```bash
python example_ai_citations.py
```

### `example_ai_with_full_context.py`
Shows how to retrieve and use full document context in AI responses.

**Key Features:**
- Full document context retrieval
- Enhanced AI response generation
- Context-aware prompting
- Citation formatting with context

**Usage:**
```bash
python example_ai_with_full_context.py
```

## Learning Path

1. Start with the simple examples first
2. Review the code to understand the API patterns
3. Adapt the patterns to your use case
4. Integrate into your application

## Common Patterns

- **Search Documents:** Use `chroma_utils.search_documents()`
- **Generate Responses:** Use `llm.llm_call()` with RAG context
- **Format Citations:** Use citation utilities from the RAG API
- **Handle Sessions:** Use session management from the API

## Integration Tips

- Always handle authentication before making queries
- Use context managers for resource cleanup
- Implement proper error handling
- Add logging for debugging

For more details, see the main API documentation in the parent directory.
