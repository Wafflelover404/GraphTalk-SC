"""
Enhanced embedding and vector store functionality with caching and batching.
"""
import json
import torch
import chromadb
import logging
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from chromadb.api.types import Documents, EmbeddingFunction
from chromadb.config import Settings

logger = logging.getLogger(__name__)

class EnhancedEmbeddingFunction(EmbeddingFunction):
    """Enhanced embedding function with batching and caching."""
    
    def __init__(self, model_name: str = "cross-encoder/ms-marco-TinyBERT-L-2-v2", 
                 device: str = None, 
                 batch_size: int = 8,  # Reduced batch size for Qwen
                 cache_dir: str = ".embedding_cache"):
        self.model_name = model_name
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.batch_size = batch_size
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self._model = None
        self._tokenizer = None
        self._max_length = 512  # Max sequence length for Qwen
    
    @property
    def model(self):
        """Lazy load the Qwen model and tokenizer."""
        if self._model is None:
            from transformers import AutoModel, AutoTokenizer
            
            # Load the tokenizer with trust_remote_code for Qwen
            self._tokenizer = AutoTokenizer.from_pretrained(
                self.model_name,
                trust_remote_code=True
            )
            
            # Load the model with trust_remote_code and device_map
            self._model = AutoModel.from_pretrained(
                self.model_name,
                device_map="auto" if "cuda" in self.device else None,
                trust_remote_code=True,
                torch_dtype=torch.bfloat16 if 'cuda' in self.device else torch.float32
            )
            
            # Set model to evaluation mode
            self._model.eval()
            
            logger.info(f"Loaded Qwen model: {self.model_name} on {self.device}")
            
        return self._model, self._tokenizer
    
    def _get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a batch of texts using Qwen model."""
        import torch
        from torch.nn.functional import normalize
        
        model, tokenizer = self.model
        
        # Tokenize the batch
        encoded_input = tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=self._max_length,
            return_tensors='pt'
        ).to(self.device)
        
        # Get model outputs
        with torch.no_grad():
            outputs = model(**encoded_input, output_hidden_states=True)
            
            # Use the last hidden state for embeddings
            last_hidden = outputs.last_hidden_state
            
            # Apply attention mask to ignore padding tokens
            attention_mask = encoded_input['attention_mask']
            input_mask_expanded = attention_mask.unsqueeze(-1).expand(last_hidden.size()).float()
            
            # Mean pooling with attention masking
            sum_embeddings = torch.sum(last_hidden * input_mask_expanded, 1)
            sum_mask = torch.clamp(input_mask_expanded.sum(1), min=1e-9)
            embeddings = sum_embeddings / sum_mask
            
            # Normalize embeddings
            embeddings = normalize(embeddings, p=2, dim=1)
            
            # Convert to list of lists
            return embeddings.cpu().numpy().tolist()
    
    def _get_embedding(self, text: str) -> List[float]:
        """Get embedding for a single text with caching."""
        import numpy as np
        
        # Create a cache key based on model name and text
        cache_key = hashlib.md5(f"{self.model_name}:{text}".encode()).hexdigest()
        cache_file = self.cache_dir / f"{cache_key}.npy"
        
        # Try to load from cache
        if cache_file.exists():
            try:
                # Load numpy array directly for embeddings
                return np.load(cache_file).tolist()
            except Exception as e:
                logger.warning(f"Error loading from cache {cache_file}: {e}")
                
        # Generate embedding if not in cache
        embeddings = self._get_embeddings_batch([text])
        embedding = embeddings[0] if embeddings else [0.0] * 4096  # Default size for Qwen
        
        # Save to cache
        try:
            np.save(cache_file, np.array(embedding), allow_pickle=False)
        except Exception as e:
            logger.warning(f"Error saving to cache {cache_file}: {e}")
            
        return embedding
    
    def __call__(self, input: Documents) -> List[List[float]]:
        """Generate embeddings for a batch of texts with batching and caching."""
        if not input:
            return []
            
        # Process in batches
        all_embeddings = []
        for i in range(0, len(input), self.batch_size):
            batch = input[i:i + self.batch_size]
            
            # Get cached and non-cached texts
            cached_embeddings = []
            non_cached_texts = []
            non_cached_indices = []
            
            for j, text in enumerate(batch):
                cache_key = f"{self.model_name}:{text}"
                cache_hash = hashlib.md5(cache_key.encode()).hexdigest()
                cache_file = self.cache_dir / f"{cache_hash}.npy"
                
                if cache_file.exists():
                    try:
                        cached_embeddings.append(np.load(cache_file).tolist())
                    except Exception as e:
                        logger.warning(f"Error loading from cache {cache_file}: {e}")
                        non_cached_texts.append(text)
                        non_cached_indices.append(j)
                else:
                    non_cached_texts.append(text)
                    non_cached_indices.append(j)
            
            # Process non-cached texts
            if non_cached_texts:
                try:
                    new_embeddings = self._get_embeddings_batch(non_cached_texts)
                    
                    # Cache the new embeddings
                    for text, embedding in zip(non_cached_texts, new_embeddings):
                        cache_key = f"{self.model_name}:{text}"
                        cache_hash = hashlib.md5(cache_key.encode()).hexdigest()
                        cache_file = self.cache_dir / f"{cache_hash}.npy"
                        try:
                            np.save(cache_file, np.array(embedding), allow_pickle=False)
                        except Exception as e:
                            logger.warning(f"Error saving to cache {cache_file}: {e}")
                    
                    # Combine with cached embeddings
                    batch_embeddings = [None] * len(batch)
                    for idx, emb in zip(non_cached_indices, new_embeddings):
                        batch_embeddings[idx] = emb
                    
                    for idx, emb in enumerate(cached_embeddings):
                        if idx < len(batch_embeddings) and batch_embeddings[idx] is None:
                            batch_embeddings[idx] = emb
                    
                    all_embeddings.extend(batch_embeddings)
                    
                except Exception as e:
                    logger.error(f"Error generating embeddings: {e}")
                    # Fallback to individual processing if batch fails
                    for text in non_cached_texts:
                        try:
                            embedding = self._get_embedding(text)
                            all_embeddings.append(embedding)
                        except Exception as e:
                            logger.error(f"Error processing text: {e}")
                            all_embeddings.append([0.0] * 4096)  # Default size for Qwen
            else:
                all_embeddings.extend(cached_embeddings)
                
        return all_embeddings

def get_vector_store(persist_directory: str = "./chroma_db", 
                    collection_name: str = "documents_enhanced",
                    embedding_model: str = "Qwen/Qwen1.5-7B-Chat") -> chromadb.Collection:
    """Get or create a ChromaDB collection with enhanced settings."""
    try:
        # Initialize ChromaDB with optimized settings
        client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # Create or get collection
        embedding_function = EnhancedEmbeddingFunction(
            model_name=embedding_model,
            device="cuda" if torch.cuda.is_available() else "cpu"
        )
        
        # List all collections to check if ours exists
        collections = client.list_collections()
        collection_names = [col.name for col in collections]
        
        if collection_name in collection_names:
            logger.info(f"Loading existing collection: {collection_name}")
            collection = client.get_collection(
                name=collection_name,
                embedding_function=embedding_function
            )
        else:
            logger.info(f"Creating new collection: {collection_name}")
            collection = client.create_collection(
                name=collection_name,
                embedding_function=embedding_function,
                metadata={"hnsw:space": "cosine"}
            )
            
        return collection
        
    except Exception as e:
        logger.error(f"Error initializing vector store: {str(e)}")
        raise
