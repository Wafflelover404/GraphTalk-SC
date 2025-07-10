from g4f.client import Client
import json


def llm_call(message):
    """
    A function to call LLM models (GPT-Like models) to translate plain text into JSON.
    Args:
        message (str): Text message as a string (should be a string, not a list)
    Return:
        Parsed JSON response (dict)
    """
    client = Client()
    # Read the prompt from json-prompt.md
    with open("json-prompt.md", "r", encoding="utf-8") as f:
        base_prompt = f.read()

    # Add instruction to respond with JSON only
    system_prompt = (
        f"{base_prompt}\n\n"
        "IMPORTANT: Respond ONLY with a valid JSON object that strictly follows the SC-Machine JSON Standard. "
        "Do not include any explanations, comments, or extra text. The JSON must adhere to the structure below:\n"
        "{\n"
        '  "[Connection Type]": {\n'
        '    "[Subject Node]": "[Object Node]",\n'
        '    "[Subject Node]": ["Object Node (Array if needed)"]\n'
        "  },\n"
        '  "membership": {\n'
        '    "[Node]": ["Modifier 1", "Modifier 2"]\n'
        "  },\n"
        '  "Source content": "[Original Input Text]"\n'
        "}\n"
        "Ensure the output is strictly valid JSON."
    )

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ],
        web_search=False
    )
    content = response.choices[0].message.content
    print("LLM raw output:", repr(content))

    try:
        # Attempt to parse the JSON response
        parsed_json = json.loads(content)
        return parsed_json
    except json.JSONDecodeError as e:
        print(f"Error: LLM response is not valid JSON. Error details: {e}")
        return None


if __name__ == "__main__":
    result = llm_call("Вчера я поступил в БГУ, а сегодня я поступил в МГУ. Я учусь на факультете математики и физики в БГУ, а в МГУ на факультете информатики. Я живу в Минске и Москве.")
    if result is not None:
        with open("output.json", "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print("JSON written to output.json")
    else:
        print("No valid JSON to write.")