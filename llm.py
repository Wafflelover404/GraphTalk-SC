import os
from google import genai
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Prefer GOOGLE_API_KEY, fallback to GEMINI_API_KEY
api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("Missing API key: set GOOGLE_API_KEY or GEMINI_API_KEY in the backend .env")

client = genai.Client(api_key=api_key)

async def llm_call(message, data):
    """
    Calls Gemini LLM to analyze KB data and answer user's message.
    Args:
        message (str): User's query
        data (str): Knowledge base search results
    Returns:
        str: LLM response always in same language as user request is, not the provided data.
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
        # Run the potentially blocking operation in a thread pool
        import asyncio
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.models.generate_content(
                model="gemini-2.5-flash",
                contents=contents,
            )
        )
        return response.text
    except Exception as e:
        print("Gemini LLM error:", e)
        return str(e)

if __name__ == "__main__":
    print(llm_call("Hello, what do you know about me ?", "My name is John And I love waffles, C/C++ language"))
