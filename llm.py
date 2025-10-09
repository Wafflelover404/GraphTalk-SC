import os
from google import genai
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Prefer GOOGLE_API_KEY, fallback to GEMINI_API_KEY
api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
client = None

# Only initialize the client if we have an API key
if api_key:
    try:
        client = genai.Client(api_key=api_key)
    except Exception as e:
        print(f"Warning: Failed to initialize Gemini client: {e}")
        client = None

async def llm_call(message, data, get_overview=True):
    """
    Process query and return results in two phases:
    1. Immediate return with files list and raw results
    2. (Optional) LLM-generated overview if available
    
    Args:
        message (str): User's query
        data (str): Knowledge base search results
        get_overview (bool): Whether to generate an LLM overview
        
    Returns:
        dict: {
            'immediate': {
                'files': list of source files,
                'raw_results': str  # Raw search results
            },
            'overview': str or None  # LLM-generated overview if available
        }
    """
    # Extract source files from data if possible
    source_files = []
    if isinstance(data, dict) and 'source_documents' in data:
        source_files = list(set(doc.metadata.get('source', 'unknown') 
                             for doc in data['source_documents'] 
                             if hasattr(doc, 'metadata')))
    
    # Prepare immediate response
    immediate_response = {
        'files': source_files,
        'raw_results': str(data) if not isinstance(data, str) else data
    }
    
    # If LLM is not available or overview not requested, return just the immediate response
    if client is None or not get_overview:
        return {
            'immediate': immediate_response,
            'overview': None
        }
    
    # Generate overview using LLM in the background
    async def generate_overview():
        try:
            system_prompt = (
                "You are an AI assistant. You receive search results from a knowledge base. "
                "Your task is to analyze these results and provide a helpful, concise overview "
                "based on the user's query. Focus on extracting key information and insights."
            )
            contents = [
                system_prompt,
                f"Knowledge base search results: {data}",
                f"User request: {message}"
            ]
            
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
            return None
    
    # Return immediate response and start overview generation
    return {
        'immediate': immediate_response,
        'overview': await generate_overview() if get_overview else None
    }

if __name__ == "__main__":
    print(llm_call("Hello, what do you know about me ?", "My name is John And I love waffles, C/C++ language"))
