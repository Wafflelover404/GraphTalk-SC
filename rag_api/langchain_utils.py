import os
import json
import logging
import google.generativeai as genai
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.documents import Document
from chroma_utils import vectorstore, search_documents
from timing_utils import Timer, PerformanceTracker, time_block

# Initialize the Google Generative AI client
genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))

# Initialize Google's Gemini model
google_api_key = os.environ.get("GOOGLE_API_KEY")
if not google_api_key:
    raise ValueError("GOOGLE_API_KEY environment variable is not set")

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
    # List available models if none specified
    if model is None:
        try:
            models = genai.list_models()
            available_models = [m.name for m in models]
            print("Available models:", available_models)
            # Try to find a suitable model
            for m in ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.5-flash"]:
                if any(m in name for name in available_models):
                    model = m
                    print(f"Using model: {model}")
                    break
            if model is None:
                raise ValueError("No suitable model found. Please check your API key and permissions.")
        except Exception as e:
            print(f"Error listing models: {e}")
            model = "gemini-2.5-flash"  # Fallback
    
    # Initialize LLM with enhanced configuration for better responses
    llm = ChatGoogleGenerativeAI(
        model=model,
        google_api_key=google_api_key,
        max_output_tokens=4096,  # Increased for more detailed responses
        temperature=0.3,  # Lower for more focused, deterministic responses
        top_p=0.9,  # Controls diversity of responses
        top_k=40,   # Broader sampling of next tokens
        n=1,        # Number of responses to generate
        stop_sequences=None,  # Let the model decide when to stop
        request_options={
            'timeout': 60,  # Increased timeout for complex queries
        }
    )
    
    # Create a simple chain that just formats the prompt
    async def answer_chain(inputs):
        logger = logging.getLogger(__name__)
        tracker = PerformanceTracker(f"answer_chain", logger)

        try:
            # Format the prompt with context and question
            tracker.start_operation("format_prompt")
            context = inputs.get("context", "No context provided")
            user_input = inputs.get("input", "No question provided")

            # Format the prompt
            prompt = qa_prompt.format(
                context=context,
                input=user_input
            )
            tracker.end_operation("format_prompt")

            # Get the LLM response
            tracker.start_operation("llm_call")
            response = await llm.ainvoke(prompt)
            tracker.end_operation("llm_call")

            # Extract the content from the response
            tracker.start_operation("extract_response")
            if hasattr(response, 'content'):
                result = response.content
            elif isinstance(response, str):
                result = response
            elif hasattr(response, 'text'):
                result = response.text
            else:
                result = str(response)
            tracker.end_operation("extract_response")

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
