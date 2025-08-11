# json-prompt.md - SC-Machine JSON Standard Specification

## Overview
This file contains the formal specification for the SC-Machine JSON Standard used by the GraphTalk system. It defines the structure and rules for converting natural language text into machine-readable semantic representations.

## Document Purpose
- **Template for LLM Prompts**: Used by `json-llm.py` for structured text conversion
- **Standard Definition**: Formal specification for semantic JSON format
- **Validation Reference**: Guidelines for ensuring output compliance
- **Example Repository**: Contains transformation examples and edge cases

## Structure Definition

### Core JSON Schema
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

## Key Components

### Connection Types
Semantic relations expressed as verb phrases in nominative case:
- **Russian Examples**: `"Обучаться в"`, `"Работать в"`, `"Принадлежать к"`
- **Format**: Infinitive verb form + preposition when applicable
- **Purpose**: Define the nature of relationships between entities

### Nodes
Entities and concepts in nominative case:
- **Subjects**: Acting entities (`"Я"`, `"студент"`, `"компания"`)
- **Objects**: Target entities (`"технопарк"`, `"университет"`, `"проект"`)
- **Consistency**: Same entity must use identical identifier throughout

### Membership
Attributes and modifiers for nodes:
- **Format**: Node identifier mapped to array of descriptive terms
- **Content**: Adjectives, classifications, properties
- **Case**: All modifiers in nominative case
- **Example**: `"технопарк": ["Национальный", "детский"]`

### Source Content
- **Requirement**: Mandatory field in all outputs
- **Content**: Exact copy of original input text
- **Purpose**: Traceability and verification
- **Encoding**: Preserved exactly as received

## Transformation Process

### Example Transformation
**Input:**
```
"Я обучаюсь в Национальном детском технопарке"
```

**Step 1: Linguistic Analysis**
- Subject: "Я" (I)
- Verb: "обучаюсь" → normalize to "Обучаться в"
- Object: "технопарке" → normalize to "технопарк"
- Modifiers: "Национальном детском" → ["Национальный", "детский"]

**Step 2: JSON Structure**
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

## Validation Rules

### Syntax Requirements
1. **Valid JSON**: Must parse without errors
2. **Quoted Strings**: All keys and string values must be quoted
3. **Comma Separation**: Proper comma usage between elements
4. **Bracket Matching**: Correct nesting of objects and arrays

### Semantic Requirements
1. **Connection Types**: Must be meaningful verb phrases
2. **Node Consistency**: Same entity uses same identifier
3. **Nominative Case**: All Russian words in nominative form
4. **Source Preservation**: Original text exactly reproduced

### Completeness Requirements
1. **Source Content**: Must be present in all outputs
2. **Non-empty Structure**: At least one connection or membership
3. **Meaningful Mapping**: Connections should reflect actual relationships

## Language Processing Guidelines

### Case Normalization
- **From**: Inflected forms (`"технопарке"`, `"Национальном"`)
- **To**: Nominative forms (`"технопарк"`, `"Национальный"`)
- **Method**: Automatic detection and conversion

### Verb Processing
- **Extract**: Main semantic verb from sentence
- **Normalize**: Convert to infinitive + preposition format
- **Examples**: 
  - `"изучает"` → `"Изучать"`
  - `"работает в"` → `"Работать в"`
  - `"принадлежит к"` → `"Принадлежать к"`

### Modifier Extraction
- **Identify**: Adjectives and descriptive phrases
- **Group**: Associate with correct noun
- **Normalize**: Convert to nominative case
- **Array Format**: Multiple modifiers as array elements

## Edge Cases and Special Handling

### Arrays in Connections
```json
{
  "Изучать": {
    "студент": ["математика", "физика", "химия"]
  }
}
```
Use when one subject relates to multiple objects.

### Multiple Connections
```json
{
  "Обучаться в": {
    "Я": "технопарк"
  },
  "Изучать": {
    "Я": "программирование"
  },
  "membership": {
    "технопарк": ["Национальный", "детский"],
    "программирование": ["основы"]
  }
}
```

### Complex Sentences
For sentences with multiple clauses, extract all meaningful semantic relationships while maintaining source attribution.

### Missing Information
When certain semantic components are unclear:
- Skip unclear relationships rather than guess
- Focus on explicitly stated connections
- Ensure what is captured is accurate

## Usage in GraphTalk System

### LLM Integration
- **File Loading**: Read by `json-llm.py` as base prompt
- **Prompt Construction**: Combined with specific instructions
- **Response Validation**: Used to verify LLM output compliance

### Quality Assurance
- **Format Checking**: Ensure JSON validity
- **Standard Compliance**: Verify adherence to structure rules
- **Semantic Validation**: Check meaningful content extraction

### Processing Pipeline
1. **Input Received**: Natural language text
2. **Prompt Construction**: Combine with this specification
3. **LLM Processing**: Generate structured JSON
4. **Validation**: Check against rules in this document
5. **Output**: Compliant SC-Machine JSON

## Maintenance Guidelines

### Updating the Standard
1. **Version Control**: Track changes to specification
2. **Compatibility**: Ensure backward compatibility when possible
3. **Documentation**: Update examples and rules together
4. **Testing**: Validate changes against existing content

### Example Management
- **Diversity**: Include various sentence structures
- **Clarity**: Each example should demonstrate specific rule
- **Accuracy**: Verify all examples follow the standard
- **Language Coverage**: Include different linguistic patterns

## Integration with OSTIS

### Knowledge Base Population
Generated JSON structures can be:
- Converted to SCS format for OSTIS import
- Used as intermediate representation for KB updates
- Processed by semantic analysis tools
- Integrated with existing knowledge graphs
  
### Semantic Compatibility
- **Node Identifiers**: Compatible with OSTIS keynodes
- **Relationship Types**: Mappable to SC-arcs and connectors  
- **Membership Relations**: Convertible to SC-sets and classes
- **Source Attribution**: Maintains provenance information

This specification serves as the foundation for reliable natural language to semantic structure conversion in the GraphTalk system, ensuring consistency and interoperability with OSTIS technology.
