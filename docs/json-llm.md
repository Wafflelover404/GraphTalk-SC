# json-llm.py - JSON Structure Generation from Natural Language

## Overview
Converts natural language text into structured JSON format following the SC-Machine JSON Standard. This module enables semantic parsing of text into machine-readable knowledge representations.

## Key Features
- **Text-to-JSON Conversion**: Transforms natural language into structured semantic data
- **SC-Machine Standard Compliance**: Follows formal specification for semantic relations
- **LLM-Powered Parsing**: Uses GPT-4o-mini for intelligent text analysis
- **JSON Validation**: Ensures output adheres to valid JSON format
- **Source Attribution**: Preserves original text in output for traceability

## Core Function

### `llm_call(message)`
Converts plain text messages into structured JSON following the SC-Machine JSON Standard.

#### Parameters
- `message` (str): Input text to be converted to JSON structure

#### Returns
- `dict`: Parsed JSON object following SC-Machine standard, or `None` if parsing fails

#### JSON Structure Format
```json
{
  "[Connection Type]": {
    "[Subject Node]": "[Object Node]",
    "[Subject Node]": ["Object Node (Array if needed)"]
  },
  "membership": {
    "[Node]": ["Modifier 1", "Modifier 2"]
  },
  "Source content": "[Original Input Text]"
}
```

## SC-Machine JSON Standard

### Connection Types
Semantic relations expressed as verb phrases:
- `"Обучаться в"` (studying at)
- `"Работать в"` (working at)  
- `"Принадлежать к"` (belonging to)

### Membership
Attributes and modifiers for nodes:
- Adjectives describing entities
- Classifications and categories
- Properties and characteristics

### Source Content
- Original unprocessed input text
- Required for all outputs
- Enables traceability and verification

## Implementation Details

### Prompt Engineering
The function uses a sophisticated prompt structure:

1. **Base Prompt**: Loaded from `json-prompt.md` file
2. **JSON Instructions**: Strict formatting requirements
3. **Example Structure**: Template showing expected output format
4. **Validation Rules**: Ensures valid JSON compliance

### Model Configuration
- **Model**: `gpt-4o-mini` (cost-effective, reliable)
- **Provider**: g4f (GPT4Free) client
- **Web Search**: Disabled (pure text processing)
- **Output Format**: JSON-only responses

## Usage Examples

### Basic Text Conversion
```python
from json_llm import llm_call

# Convert Russian text to JSON
text = "Я обучаюсь в Национальном детском технопарке"
result = llm_call(text)

if result:
    print(json.dumps(result, ensure_ascii=False, indent=2))
```

### Expected Output
```json
{
  "Обучаться в": {
    "Я": "технопарк"
  },
  "membership": {
    "технопарк": ["Национальный", "детский"]
  },
  "Source content": "Я обучаюсь в Национальном детском технопарке"
}
```

### Batch Processing
```python
texts = [
    "Студент изучает математику в университете",
    "Компания разрабатывает искусственный интеллект",
    "Исследователь работает над новым проектом"
]

results = []
for text in texts:
    json_result = llm_call(text)
    if json_result:
        results.append(json_result)
        
# Save all results
with open("batch_output.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
```

### File Output Processing
```python
# Using the main script functionality
if __name__ == "__main__":
    result = llm_call("Я обучаюсь в Национальном детском технопарке")
    if result is not None:
        with open("output.json", "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print("JSON written to output.json")
    else:
        print("No valid JSON to write.")
```

## Prompt Structure Analysis

### Base Prompt (from json-prompt.md)
- Defines SC-Machine JSON Standard
- Provides structure definitions
- Shows validation rules
- Includes example transformations

### JSON-Only Instructions
```
"IMPORTANT: Respond ONLY with a valid JSON object that strictly follows the SC-Machine JSON Standard. 
Do not include any explanations, comments, or extra text. The JSON must adhere to the structure below:
{
  "[Connection Type]": {
    "[Subject Node]": "[Object Node]",
    "[Subject Node]": ["Object Node (Array if needed)"]
  },
  "membership": {
    "[Node]": ["Modifier 1", "Modifier 2"]
  },
  "Source content": "[Original Input Text]"
}
Ensure the output is strictly valid JSON."
```

## Language Processing Features

### Normalization
- Converts inflected forms to nominative case
- Extracts base semantic relationships
- Handles complex sentence structures

### Relationship Extraction
- Identifies subject-verb-object patterns
- Maps semantic roles to JSON structure
- Preserves relationship semantics

### Attribute Grouping
- Collects modifiers and adjectives
- Associates attributes with correct entities
- Maintains semantic coherence

## Error Handling

### JSON Parsing Errors
```python
try:
    parsed_json = json.loads(content)
    return parsed_json
except json.JSONDecodeError as e:
    print(f"Error: LLM response is not valid JSON. Error details: {e}")
    return None
```

### LLM Response Validation
- Checks for valid JSON format
- Verifies required fields presence
- Handles malformed responses gracefully

### Debug Output
```python
print("LLM raw output:", repr(content))
```
Enables debugging of LLM responses for troubleshooting.

## Integration Patterns

### Knowledge Base Population
```python
# Convert text to structured data for KB insertion
documents = load_text_documents()
structured_data = []

for doc in documents:
    json_structure = llm_call(doc.content)
    if json_structure:
        structured_data.append(json_structure)

# Insert into knowledge base
insert_into_kb(structured_data)
```

### Semantic Analysis Pipeline
```python
def analyze_text_semantics(text):
    # 1. Convert to JSON structure
    json_data = llm_call(text)
    
    # 2. Extract semantic components
    if json_data:
        connections = extract_connections(json_data)
        memberships = extract_memberships(json_data)
        source = json_data.get("Source content")
        
        return {
            "connections": connections,
            "memberships": memberships,
            "source": source
        }
    return None
```

### Quality Assurance
```python
def validate_json_output(json_data):
    required_fields = ["Source content"]
    
    # Check required fields
    for field in required_fields:
        if field not in json_data:
            return False
    
    # Validate structure
    if not isinstance(json_data.get("membership", {}), dict):
        return False
        
    return True
```

## Performance Considerations

### Token Usage
- Input text length affects token consumption
- Complex sentences require more processing
- Monitor API costs for large-scale processing

### Response Quality
- Quality depends on text complexity and language
- Russian language processing may have variations
- Consider post-processing validation

### Batch Processing
- Process texts in batches for efficiency
- Implement retry logic for failed conversions
- Cache results for repeated texts

## Best Practices

1. **Input Validation**: Ensure input text is well-formed
2. **Output Verification**: Always check for valid JSON output
3. **Error Handling**: Implement robust error handling for production use
4. **Language Consistency**: Maintain consistent language usage (Russian in examples)
5. **Source Preservation**: Always include original text in output
6. **Format Validation**: Verify adherence to SC-Machine standard
7. **Batch Optimization**: Use batch processing for multiple texts
8. **Cost Monitoring**: Track API usage and optimize for cost-effectiveness

## File Dependencies

### json-prompt.md
Contains the complete SC-Machine JSON Standard specification including:
- Structure definitions
- Validation rules
- Example transformations
- Edge case handling guidelines

This file is critical for proper prompt construction and must be maintained alongside the code.
