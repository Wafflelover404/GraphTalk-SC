# **SC-Machine JSON Standard**

*A formalized format for semantic relations and source attribution*

---

## **1. Structure Definition**

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

### **Key Fields**

- **Connection Types**: Define semantic relations (e.g., `Обучаться в` = "studying at").
- **Nodes**: Represent concepts (e.g., `Я` = "I", `технопарк` = "technopark").
- **membership**: Lists attributes/modifiers for a node (e.g., `["Национальный", "детский"]`).
- **Source content**: Original unprocessed input for reference.

---

## **2. Example: NLP Processing**

### **Input**

> "Я обучаюсь в Национальном детском технопарке"
> 

### **Step 1: Normalization**

> "Я обучаться в Национальный детский технопарк"
> 

### **Step 2: Formalized JSON**

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

### **Explanation**

- `Обучаться в` links the subject (`Я`) to the object (`технопарк`).
- `membership` groups adjectives describing `технопарк`.
- `Source content` preserves the original sentence.

---

## **3. Validation Rules**

1. **Syntax**:
    - Commas between objects/arrays.
    - Quotes around all keys/strings.
2. **Semantics**:
    - Connection types should be verb phrases (`Обучаться в`).
    - Nodes in `membership` must match referenced nodes.
3. **Completeness**:
    - All inputs must include `Source content`.

---

## **4. Edge Cases & Notes**

- **Arrays**: Use only in `membership` if no descriptions for connections provided.
- **Node Consistency**: Ensure node IDs (e.g., `технопарк`) are reused, not redefined.
- **Language**: All keys/nodes are in **nominative case** (e.g., "Национальный", not "Национальном").

---

### **Why This Standard?**

- **Machine-Readable**: Simple parsing via key-value pairs.
- **Extensible**: Add new connection types without breaking changes.
- **Traceable**: `Source content` ties output to input.