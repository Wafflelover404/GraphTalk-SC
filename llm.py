from g4f.client import Client

def llm_call(message, data):
    """
    A function to call LLM models (GPT-Like models) to complete KB-Parsed data.
    Args:
        message (str): Text message as a string (should be a string, not a list)
    Return:
        Text response (str)
    """
    client = Client()
    system_prompt = (
        "You are an AI assistant. You receive a bunch of data from a knowledge base. "
        "Your task is to analyze this data and provide a helpful, concise answer based on the user's message. "
        "Focus on extracting relevant information and reasoning from the knowledge base data in the context of the user's query."
    )
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": f"Instructions - {system_prompt}"},
            {"role": "system", "content": f"Knowledge base search query - {data}"},
            {"role": "user", "content": f"user request - {message}"}
        ],
        web_search=False
    )

    return(response.choices[0].message.content)

if __name__ == "__main__":
    print(llm_call("Hello, what do you know about me ?", "My name is John And I love waffles, C/C++ language"))
