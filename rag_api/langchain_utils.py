import os
import json
import google.generativeai as genai
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.documents import Document
from chroma_utils import vectorstore

# Initialize the Google Generative AI client
genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))

# Initialize Google's Gemini model
google_api_key = os.environ.get("GOOGLE_API_KEY")
if not google_api_key:
    raise ValueError("GOOGLE_API_KEY environment variable is not set")

# Configure retriever to get more results
retriever = vectorstore.as_retriever(
    search_type="similarity",
    search_kwargs={
        "k": 20,  # Get more results initially
        "score_threshold": 0.3  # Lower threshold to get more potential matches
    }
)

# Simple prompt focused on document content
qa_prompt = """You are a helpful AI assistant. 
Use the following context to answer the question. If the context doesn't contain relevant information, 
say "I couldn't find relevant information in the documents. You MUST ALWAYS RESPONSE IN SAME LANGUAGE AS USER REQUEST."

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
        temperature=0.2,
        max_output_tokens=2048
    )
    
    # Create a simple chain that just formats the prompt
    async def answer_chain(inputs):
        try:
            # Format the prompt with context and question
            context = inputs.get("context", "No context provided")
            user_input = inputs.get("input", "No question provided")
            
            # Format the prompt
            prompt = qa_prompt.format(
                context=context,
                input=user_input
            )
            
            # Get the LLM response
            response = await llm.ainvoke(prompt)
            
            # Extract the content from the response
            if hasattr(response, 'content'):
                return response.content
            elif isinstance(response, str):
                docs = inputs.get("docs", [])
                relevance_scores = inputs.get("relevance_scores", [])
                username = inputs.get("username", "")
                chunks = []
                for doc, relevance in zip(docs, relevance_scores):
                    # Get the filename from metadata, default to unknown
                    filename = doc.metadata.get('filename', doc.metadata.get('source', 'unknown'))
                    # Get just the base filename with extension
                    base_filename = os.path.basename(str(filename))
                    # Ensure .md extension is included in title
                    title = base_filename if base_filename.endswith('.md') else f"{base_filename}.md"
                    
                    # Clean and escape content
                    content = (
                        doc.page_content
                        .replace('"', '\\"')
                        .replace('\n', ' ')
                        .strip()
                    )
                    
                    # Create a proper JSON string
                    chunk_data = {
                        'title': title,
                        'content': content,
                        'relevance': f"{relevance}%"
                    }
                    
                    # Convert to JSON string and add filename tag
                    chunk_str = (
                        f"{json.dumps(chunk_data, ensure_ascii=False)}\n"
                        f"<filename>{filename}</filename>"
                    )
                    chunks.append(chunk_str)
                
                return {
                    "status": "success",
                    "message": "Query processed with secure RAG (raw chunks)",
                    "response": {
                        "chunks": chunks,
                        "model": "server",
                        "security_info": {
                            "user_filtered": True,
                            "username": username,
                            "source_documents_count": len(docs),
                            "security_filtered": False
                        }
                    }
                }
            elif hasattr(response, 'text'):
                return response.text
            else:
                return str(response)
                
        except Exception as e:
            logger.error(f"Error in answer_chain: {str(e)}")
            return f"Error generating response: {str(e)}"
    
    # Create the chain
    rag_chain = {
        "input": lambda x: x.get("input", ""),
        "context": lambda x: x.get("context", ""),
        "answer": answer_chain
    }
    
    return rag_chain
