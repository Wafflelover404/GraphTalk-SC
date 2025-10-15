import os
import json
import logging
from dotenv import load_dotenv
from langchain_core.documents import Document
from chroma_utils import vectorstore, search_documents
from timing_utils import Timer, PerformanceTracker, time_block

# Load environment variables
load_dotenv()

# Configuration - Priority: DeepSeek > ChatGPT > Gemini > None
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Initialize clients
deepseek_client = None
openai_client = None
gemini_client = None
active_llm = None

# Try DeepSeek first (preferred)
if DEEPSEEK_API_KEY:
    try:
        from openai import AsyncOpenAI
        deepseek_client = AsyncOpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url="https://api.deepseek.com/v1"
        )
        active_llm = "deepseek"
        print("✓ DeepSeek client initialized for RAG chain")
    except Exception as e:
        print(f"Warning: Failed to initialize DeepSeek client: {e}")
        deepseek_client = None

# Try ChatGPT/OpenAI if DeepSeek is not available
if not deepseek_client and OPENAI_API_KEY:
    try:
        from openai import AsyncOpenAI
        openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        active_llm = "chatgpt"
        print("✓ ChatGPT (OpenAI) client initialized for RAG chain")
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
        print("✓ Gemini client initialized for RAG chain")
    except Exception as e:
        print(f"Warning: Failed to initialize Gemini client: {e}")
        gemini_client = None

if not deepseek_client and not openai_client and not gemini_client:
    print("ℹ No LLM API key found. RAG will work in retrieval-only mode.")

class ChromaRetriever:
    def __init__(self, vectorstore):
        self.vectorstore = vectorstore
    
    def get_relevant_documents(self, query: str) -> list[Document]:
        """Retrieve documents relevant to the query."""
        # Use our enhanced search function
        results = search_documents(
            query=query,
            similarity_threshold=0.3,  # Match the previous threshold
            max_results=20,  # Match the previous k value
            include_full_document=False  # We just need the chunks for RAG
        )
        
        # Return the semantic search results as Documents
        return results.get('semantic_results', [])
    
    async def aget_relevant_documents(self, query: str) -> list[Document]:
        """Async version of get_relevant_documents."""
        return self.get_relevant_documents(query)

# Create a custom retriever that uses our enhanced search
retriever = ChromaRetriever(vectorstore)

# Enhanced prompt with better context utilization and response guidance
qa_prompt = """You are an expert assistant analyzing company documents. Your task is to provide accurate, detailed answers based on the provided context.

GUIDELINES:
1. ALWAYS respond in the same language as the user's question.
2. If the context is insufficient, say "I couldn't find enough information to fully answer your question."
3. When possible, provide specific details, names, dates, and numbers from the context.
4. If the context contains multiple relevant points, include them all in a structured way.
5. For complex topics, break down the information into clear, organized sections.
6. If the context contains technical terms or jargon, explain them when necessary.
7. For financial or numerical data, include specific figures from the context.

CONTEXT:
{context}

QUESTION: {input}

Before answering, analyze the context and follow these steps:
1. Identify all relevant information in the context
2. Organize the information logically
3. Cross-reference multiple context sections if available
4. Provide a comprehensive response that directly addresses the question

ANSWER (be thorough and specific):"""

def get_rag_chain(model: str = None):
    # Model parameter is kept for backward compatibility but not used with DeepSeek
    if model is None:
        model = "deepseek-chat"  # Default DeepSeek model
    
    # Create a simple chain that just formats the prompt
    async def answer_chain(inputs):
        logger = logging.getLogger(__name__)
        tracker = PerformanceTracker(f"answer_chain", logger)

        try:
            # Format the prompt with context and question
            tracker.start_operation("format_prompt")
            context = inputs.get("context", "No context provided")
            user_input = inputs.get("input", "No question provided")
            tracker.end_operation("format_prompt")

            # If no LLM is available, return just the context
            if not deepseek_client and not openai_client and not gemini_client:
                logger.info("No LLM available, returning context only")
                return f"Search results for '{user_input}':\n\n{context}"

            # Get the LLM response using available client
            tracker.start_operation("llm_call")
            result = None
            
            # Try DeepSeek first
            if deepseek_client:
                try:
                    logger.info("🤖 Generating response with DeepSeek...")
                    response = await deepseek_client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "system", "content": "You are an expert assistant analyzing company documents. Provide accurate, detailed answers based on the provided context. Always respond in the same language as the user's question."},
                            {"role": "user", "content": qa_prompt.format(context=context, input=user_input)}
                        ],
                        temperature=0.3,
                        max_tokens=4096,
                        timeout=60
                    )
                    result = response.choices[0].message.content
                    logger.info("✓ DeepSeek response generated")
                except Exception as e:
                    logger.error(f"❌ DeepSeek API error: {e}")
                    result = None
            
            # Try ChatGPT if DeepSeek failed or not available
            if not result and openai_client:
                try:
                    logger.info("🤖 Generating response with ChatGPT...")
                    response = await openai_client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": "You are an expert assistant analyzing company documents. Provide accurate, detailed answers based on the provided context. Always respond in the same language as the user's question."},
                            {"role": "user", "content": qa_prompt.format(context=context, input=user_input)}
                        ],
                        temperature=0.3,
                        max_tokens=4096,
                        timeout=60
                    )
                    result = response.choices[0].message.content
                    logger.info("✓ ChatGPT response generated")
                except Exception as e:
                    logger.error(f"❌ ChatGPT API error: {e}")
                    result = None
            
            # Try Gemini if DeepSeek and ChatGPT failed or not available
            if not result and gemini_client:
                try:
                    logger.info("🤖 Generating response with Gemini...")
                    import asyncio
                    loop = asyncio.get_event_loop()
                    response = await loop.run_in_executor(
                        None,
                        lambda: gemini_client.models.generate_content(
                            model="gemini-2.0-flash-exp",
                            contents=[
                                "You are an expert assistant analyzing company documents. Provide accurate, detailed answers based on the provided context. Always respond in the same language as the user's question.",
                                qa_prompt.format(context=context, input=user_input)
                            ],
                        )
                    )
                    result = response.text
                    logger.info("✓ Gemini response generated")
                except Exception as e:
                    error_msg = str(e).lower()
                    if '400' in error_msg and ('location' in error_msg or 'region' in error_msg or 'not supported' in error_msg):
                        logger.error("❌ Gemini region restriction detected")
                    else:
                        logger.error(f"❌ Gemini API error: {e}")
                    result = None
            
            # If both failed, return context
            if not result:
                result = f"Could not generate LLM response. Here are the search results:\n\n{context}"
            
            tracker.end_operation("llm_call")

            tracker.log_summary()
            return result

        except Exception as e:
            logger.error(f"Error in answer_chain: {str(e)}")
            tracker.log_summary()
            return f"Error generating response: {str(e)}"
    
    # Create the chain
    rag_chain = {
        "input": lambda x: x.get("input", ""),
        "context": lambda x: x.get("context", ""),
        "answer": answer_chain
    }
    
    return rag_chain
