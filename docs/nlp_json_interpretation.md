# NLP JSON Interpretation & LLM Integration

This document describes the process of interpreting natural language (NL) into a machine-readable JSON format and loading it into the SC-memory using the `json-interpreter.py` script. It also covers how this process can be integrated with LLMs (Large Language Models) for automated knowledge extraction.

---

## Overview

The NLP pipeline consists of the following steps:

1. **Natural Language Input:**  
   The user provides text in any language (e.g., Russian, English, Spanish).

2. **JSON Formalization:**  
   The text is converted into a structured JSON format, where:
   - Relations are verb phrases (e.g., "Поступить в", "Учиться на").
   - Nodes and objects are in nominative case.
   - The original sentence is preserved as `"Source content"`.

3. **SC-memory Loading:**  
   The `json-interpreter.py` script reads the JSON and creates semantic nodes and relations in SC-memory, attaching the original text as a label to each node.

---

## Example: Log Output

Below is a sample log from running `json-interpreter.py` on a Russian-language input:

```
--- Detailed Log ---
Node exists: source_content (from 'Source content') -> ScAddr(262154) | Label attached
Source content link attached: Вчера я поступил в БГУ, а сегодня я поступил в МГУ. Я учусь на факультете математики и физики в БГУ, а в МГУ на факультете информатики. Я живу в Минске и Москве.
Node created: postupit_v (from 'Поступить в') -> ScAddr(262302) | Label attached
Node created: ia (from 'я') -> ScAddr(262306) | Label attached
Node created: bgu (from 'БГУ') -> ScAddr(262310) | Label attached
Relation created: я -[Поступить в]-> БГУ
Node created: mgu (from 'МГУ') -> ScAddr(262316) | Label attached
Relation created: я -[Поступить в]-> МГУ
Node created: uchitsia_na (from 'Учиться на') -> ScAddr(262322) | Label attached
Node created: ia (from 'я') -> ScAddr(262326) | Label attached
Node created: fakultet_matematiki_i_fiziki_v_bgu (from 'факультет математики и физики в БГУ') -> ScAddr(262330) | Label attached
Relation created: я -[Учиться на]-> факультет математики и физики в БГУ
Node created: fakultet_informatiki_v_mgu (from 'факультет информатики в МГУ') -> ScAddr(262336) | Label attached
Relation created: я -[Учиться на]-> факультет информатики в МГУ
Node created: zhit_v (from 'Жить в') -> ScAddr(262342) | Label attached
Node created: ia (from 'я') -> ScAddr(262346) | Label attached
Node created: minsk (from 'Минск') -> ScAddr(262350) | Label attached
Relation created: я -[Жить в]-> Минск
Node created: moskva (from 'Москва') -> ScAddr(262356) | Label attached
Relation created: я -[Жить в]-> Москва
Node created: bgu (from 'БГУ') -> ScAddr(262362) | Label attached
Node created: mgu (from 'МГУ') -> ScAddr(262366) | Label attached
Node created: fakultet_matematiki_i_fiziki_v_bgu (from 'факультет математики и физики в БГУ') -> ScAddr(262370) | Label attached
Node created: fakultet_informatiki_v_mgu (from 'факультет информатики в МГУ') -> ScAddr(262374) | Label attached
Node created: minsk (from 'Минск') -> ScAddr(262378) | Label attached
Node created: moskva (from 'Москва') -> ScAddr(262382) | Label attached
```

- Each node is created with a normalized system identifier (e.g., `postupit_v` for `"Поступить в"`), but the original text is always attached as a label.
- Relations are created between nodes, and all actions are logged.

---

## JSON Format

The expected JSON format is as follows:

```json
{
  "Поступить в": {
    "я": ["БГУ", "МГУ"]
  },
  "Учиться на": {
    "я": [
      "факультет математики и физики в БГУ",
      "факультет информатики в МГУ"
    ]
  },
  "Жить в": {
    "я": ["Минск", "Москва"]
  },
  "membership": {
    "БГУ": [],
    "МГУ": [],
    "факультет математики и физики в БГУ": [],
    "факультет информатики в МГУ": [],
    "Минск": [],
    "Москва": []
  },
  "Source content": "Вчера я поступил в БГУ, а сегодня я поступил в МГУ. Я учусь на факультете математики и физики в БГУ, а в МГУ на факультете информатики. Я живу в Минске и Москве."
}
```

---

## Integration with LLMs

- LLMs can be used to automatically convert natural language text into the above JSON format.
- The JSON can then be loaded into SC-memory using the interpreter script.
- This enables automated knowledge extraction and semantic graph construction from arbitrary text in any language.

---

## Usage

1. Place your JSON in `output.json`.
2. Run the interpreter:
   ```
   python3 json-interpreter.py
   ```
3. Review the detailed log for information about which nodes and relations were created.

---

## See Also

- [SC-Machine JSON Standard](./json-prompt.md)
- [Main README](../README.md)
