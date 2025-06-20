from g4f.client import Client

def llm_call(message):
    """
    A function to call LLM models (GPT-Like models) to complete KB-Parsed data.
    Args:
        message (str): Text message as a string (should be a string, not a list)
    Return:
        Text response (str)
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

    return(response.choices[0].message.content)

if __name__ == "__main__":
    print(llm_call("Я обучаюсь в Национальном детском технопарке"))
