# Environment Configuration

This document describes the environment variables used by the RAG API system.

## Required Environment Variables

### GEMINI_API_KEY
**Purpose**: API key for Google Gemini service  
**Required**: Yes (when using server model)  
**Example**: 
```bash
export GEMINI_API_KEY="your-gemini-api-key-here"
```

### RAG_MODEL_TYPE
**Purpose**: Selects which model to use for RAG queries  
**Required**: No (defaults to "server")  
**Options**:
- `local` - Use local llama3.2 model
- `server` - Use server-based Gemini model (default)

**Example**:
```bash
# Use local model
export RAG_MODEL_TYPE=local

# Use server model (default)
export RAG_MODEL_TYPE=server
```

## Setting Environment Variables

### Method 1: One-time setup
```bash
# Set for current session only
export RAG_MODEL_TYPE=local
export GEMINI_API_KEY="your-api-key"
```

### Method 2: Persistent setup
Add to your shell configuration file (`~/.bashrc`, `~/.zshrc`, etc.):
```bash
echo 'export RAG_MODEL_TYPE=local' >> ~/.zshrc
echo 'export GEMINI_API_KEY="your-api-key"' >> ~/.zshrc
source ~/.zshrc
```

### Method 3: Using the provided script
```bash
# Interactive model selection
./set_model.sh
```

### Method 4: .env file (if using python-dotenv)
Create a `.env` file in the project root:
```bash
RAG_MODEL_TYPE=local
GEMINI_API_KEY=your-api-key-here
```

## Verifying Configuration

Check your current environment:
```bash
echo "Model Type: $RAG_MODEL_TYPE"
echo "Gemini API Key: $(if [ -n "$GEMINI_API_KEY" ]; then echo "✓ Set"; else echo "✗ Not set"; fi)"
```

## API Behavior

- **Without RAG_MODEL_TYPE**: Defaults to "server" (Gemini)
- **RAG_MODEL_TYPE=local**: Uses llama3.2 with fallback to Gemini on error
- **RAG_MODEL_TYPE=server**: Uses Gemini directly
- **Missing GEMINI_API_KEY**: Server model will fail, local model will work if available

## Migration from Request-based Model Selection

Previously, model selection was controlled by the `use_local` parameter in API requests:
```json
{
  "question": "What is this about?",
  "use_local": true
}
```

Now it's controlled by environment variable, so requests only need:
```json
{
  "question": "What is this about?"
}
```

This change provides:
- Consistent model selection across all requests
- Server-side control over model usage
- Simplified API requests
- Better separation of configuration and runtime data
