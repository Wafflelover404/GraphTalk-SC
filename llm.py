import os
from google import genai

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def llm_call(message, data):
    """
    Calls Gemini LLM to analyze KB data and answer user's message.
    Args:
        message (str): User's query
        data (str): Knowledge base search results
    Returns:
        str: LLM response
    """
    system_prompt = (
        "You are an AI assistant. You receive a bunch of data from a knowledge base. "
        "Your task is to analyze this data and provide a helpful, concise answer based on the user's message. "
        "Focus on extracting relevant information and reasoning from the knowledge base data in the context of the user's query."
    )
    contents = [
        system_prompt,
        f"Knowledge base search query: {data}",
        f"User request: {message}"
    ]
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
        )
        return response.text
    except Exception as e:
        print("Gemini LLM error:", e)
        return str(e)

if __name__ == "__main__":
    print(llm_call("Hello, what do you know about me ?", "My name is John And I love waffles, C/C++ language"))
