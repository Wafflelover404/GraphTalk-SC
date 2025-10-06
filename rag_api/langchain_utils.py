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

# Simple prompt focused on document content
qa_prompt = """You are a helpful AI assistant. 
Use the following context to answer the question. The context comes from document chunks that were found relevant to your query.

If the context doesn't contain relevant information, say "I couldn't find relevant information in the documents." 

IMPORTANT: You MUST ALWAYS RESPOND IN THE SAME LANGUAGE AS THE USER'S REQUEST.

Context:
{context}

Question: {input}

Answer:"""

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
            model = "gemini-1.5-flash"  # Fallback
    
    # Initialize LLM with the selected model
    llm = ChatGoogleGenerativeAI(
        model=model,
        google_api_key=google_api_key,
        max_output_tokens=2048
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
