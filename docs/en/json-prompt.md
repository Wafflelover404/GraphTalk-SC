# SC-Machine JSON Standard v3.0

## 1. Purpose
Standardized JSON structure for semantic representation of technical content with:
- Text segmentation support
- Machine-readable relations
- OSTIS compatibility

## 2. File Structure
```json
{
  "Source content": {
    "segments": {
      "seg_[SHA256]": "Text segment content..."
    }
  },
  "Belongs to segment": {
    "[concept]": "seg_[SHA256]"
  },
  "[relation_verb]": {
    "[subject]": "[object]|['object1','object2']"
  },
  "membership": {
    "[node]": ["attribute1", "attribute2"]
  }
}
```

## 3. Field Specifications

### 3.1 Source Content (Required)
```json
"Source content": {
  "segments": {
    "seg_a1b2c3": "C++ was created by Bjarne Stroustrup...",
    "seg_d4e5f6": "Key features include..."
  }
}
```
- `segments`: Key-value pairs with SHA256 hashes as keys

### 3.2 Segment Relations
```json
"Belongs to segment": {
  "C++": "seg_a1b2c3",
  "OOP": ["seg_a1b2c3", "seg_d4e5f6"]
}
```
- Values can be string (single segment) or array (multiple segments)

### 3.3 Semantic Relations
```json
"Is a": {
  "C++": "programming language"
},
"Supports": {
  "C++": ["OOP", "generic programming"]
}
```
- Relations must use infinitive verbs
- Objects can be strings or arrays

## 4. Normalization Rules

### 4.1 Node Identifiers
```python
normalize_identifier("Object-oriented") → "object_oriented"
normalize_identifier("C++") → "c" 
```

### 4.2 Segment IDs
```python
import hashlib
seg_id = "seg_" + hashlib.sha256(text.encode()).hexdigest()[:6]
```

## 5. Validation Rules

1. **Structural**:
   - `Source content` must exist
   - All segments must be referenced

2. **Semantic**:
   - Relations must be valid verb phrases
   - Nodes must be in nominative case

## 6. OSTIS Mapping

| JSON Component       | SC-Node Type          |
|----------------------|-----------------------|
| `[concept]`          | `sc_node_class`       |
| `[relation_verb]`    | `sc_node_norel`       |
| `seg_[hash]`         | `sc_node_struct`      |

