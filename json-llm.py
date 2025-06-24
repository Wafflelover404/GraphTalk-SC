from g4f.client import Client
import json


def llm_call(message):
    """
    A function to call LLM models (GPT-Like models) to translate plain text into json.
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
        f"{base_prompt}\n\nIMPORTANT: Respond ONLY with the requested JSON object, without any explanations, comments, or extra text. The output must be valid JSON."
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
    #try:
    return json.loads(content)
    #except json.JSONDecodeError:
    #    print("Error: LLM response is not valid JSON.")
    #    return None

if __name__ == "__main__":
    result = llm_call("Я обучаюсь в Национальном детском технопарке")
    if result is not None:
        with open("output.json", "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print("JSON written to output.json")
    else:
        print("No valid JSON to write.") 