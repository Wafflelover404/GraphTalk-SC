import os
import asyncio
from typing import Optional, Dict, Any
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration - Priority: DeepSeek > ChatGPT > Gemini > None
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Initialize clients
deepseek_client = None
openai_client = None
gemini_client = None
active_llm = None  # Track which LLM is being used

# Try DeepSeek first (preferred)
if DEEPSEEK_API_KEY:
    try:
        from openai import AsyncOpenAI
        deepseek_client = AsyncOpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url="https://api.deepseek.com/v1"
        )
        active_llm = "deepseek"
        print("✓ DeepSeek client initialized successfully")
    except Exception as e:
        print(f"Warning: Failed to initialize DeepSeek client: {e}")
        deepseek_client = None

# Try ChatGPT/OpenAI if DeepSeek is not available
if not deepseek_client and OPENAI_API_KEY:
    try:
        from openai import AsyncOpenAI
        openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        active_llm = "chatgpt"
        print("✓ ChatGPT (OpenAI) client initialized successfully")
    except Exception as e:
        print(f"Warning: Failed to initialize OpenAI client: {e}")
        openai_client = None

# Try Gemini if DeepSeek and ChatGPT are not available
if not deepseek_client and not openai_client and GEMINI_API_KEY:
    try:
        from google import genai
        # Set the API key in environment for the library
        if not os.getenv("GOOGLE_API_KEY"):
            os.environ["GOOGLE_API_KEY"] = GEMINI_API_KEY
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        active_llm = "gemini"
        print("✓ Gemini client initialized successfully")
    except Exception as e:
        print(f"Warning: Failed to initialize Gemini client: {e}")
        gemini_client = None

if not deepseek_client and not openai_client and not gemini_client:
    print("ℹ No LLM API key found. Running in RAG-only mode (search results only).")

# Check if any LLM is available
LLM_AVAILABLE = deepseek_client is not None or openai_client is not None or gemini_client is not None

def get_immediate_results(data):
    """
    Extract and return immediate RAG results without waiting for LLM. Always provide user with comprehensive overview in the same language as user query
    
    Args:
        data: Knowledge base search results
        
    Returns:
        dict: {
            'files': list of source files,
            'raw_results': str
        }
    """
    # Extract source files from data if possible
    source_files = []
    if isinstance(data, dict) and 'source_documents' in data:
        source_files = list(set(doc.metadata.get('source', 'unknown') 
                             for doc in data['source_documents'] 
                             if hasattr(doc, 'metadata')))
    
    return {
        'files': source_files,
        'raw_results': str(data) if not isinstance(data, str) else data
    }

async def generate_llm_overview(message: str, data: Any) -> Optional[str]:
    """
    Generate LLM overview asynchronously. This can be called separately
    after immediate results are returned.
    
    Args:
        message: User's query
        data: Knowledge base search results
        
    Returns:
        str or None: LLM-generated overview
    """
    if not LLM_AVAILABLE:
        return None
    
    system_prompt = (
        "You are an AI assistant. You receive search results from a knowledge base. "
        "Your task is to analyze these results and provide a helpful, concise overview "
        "based on the user's query. Focus on extracting key information and insights."
    )
    
    overview = None
    
    # Try DeepSeek first
    if deepseek_client:
        try:
            print("🤖 Generating overview with DeepSeek...")
            response = await deepseek_client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Knowledge base search results: {data}\n\nUser request: {message}"}
                ],
                temperature=0.7,
                max_tokens=1000
            )
            overview = response.choices[0].message.content
            print("✓ DeepSeek overview generated successfully")
            return overview
        except Exception as e:
            print(f"❌ DeepSeek API error: {e}")
    
    # Try ChatGPT if DeepSeek failed or not available
    if openai_client:
        try:
            print("🤖 Generating overview with ChatGPT...")
            response = await openai_client.chat.completions.create(
                model="gpt-4o-mini",  # Fast and cost-effective
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Knowledge base search results: {data}\n\nUser request: {message}"}
                ],
                temperature=0.7,
                max_tokens=1000
            )
            overview = response.choices[0].message.content
            print("✓ ChatGPT overview generated successfully")
            return overview
        except Exception as e:
            print(f"❌ ChatGPT API error: {e}")
    
    # Try Gemini if DeepSeek and ChatGPT failed or not available
    if gemini_client:
        try:
            print("🤖 Generating overview with Gemini...")
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: gemini_client.models.generate_content(
                    model="gemini-2.0-flash-exp",
                    contents=[
                        system_prompt,
                        f"Knowledge base search results: {data}",
                        f"User request: {message}"
                    ],
                )
            )
            overview = response.text
            print("✓ Gemini overview generated successfully")
            return overview
        except Exception as e:
            error_msg = str(e).lower()
            if '400' in error_msg and ('location' in error_msg or 'region' in error_msg or 'not supported' in error_msg):
                print("❌ Gemini region restriction detected. Falling back to RAG response only.")
            else:
                print(f"❌ Gemini API error: {e}")
    
    print("⚠️ All LLM services unavailable. Providing fallback response.")
    return "I apologize, but I'm currently unable to generate a detailed AI overview due to technical difficulties with the language models. The search results above contain relevant information from your knowledge base that should help answer your question. Please try again later for a comprehensive analysis."

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
            'overview': str or None,  # LLM-generated overview if available
            'llm_used': str or None  # Which LLM was used
        }
    """
    # Get immediate results (fast, no LLM)
    immediate_response = get_immediate_results(data)
    
    # If no LLM or overview not requested, return immediately
    if not LLM_AVAILABLE or not get_overview:
        return {
            'immediate': immediate_response,
            'overview': None,
            'llm_used': None
        }
    
    # Generate overview (this will take time)
    overview = await generate_llm_overview(message, data)
    
    return {
        'immediate': immediate_response,
        'overview': overview,
        'llm_used': active_llm if overview else None
    }

if __name__ == "__main__":
    print(llm_call("Hello, what do you know about me ?", "My name is John And I love waffles, C/C++ language"))
