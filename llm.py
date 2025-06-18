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
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": message}],
        web_search=False
    )

    return(response.choices[0].message.content)

if __name__ == "__main__":
    print(llm_call("Hello !"))
