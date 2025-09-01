#!/bin/bash

# RAG Model Configuration Script
# This script sets the RAG_MODEL_TYPE environment variable to control model selection

echo "RAG Model Selection:"
echo "1. local  - Use local llama3.2 model"
echo "2. server - Use server gemini model (default)"
echo ""

read -p "Select model type (1 for local, 2 for server, default: server): " choice

case $choice in
    1)
        export RAG_MODEL_TYPE=local
        echo "✓ Model set to LOCAL (llama3.2)"
        echo "To make this persistent, add this line to your ~/.bashrc or ~/.zshrc:"
        echo "export RAG_MODEL_TYPE=local"
        ;;
    2|"")
        export RAG_MODEL_TYPE=server
        echo "✓ Model set to SERVER (gemini)"
        echo "To make this persistent, add this line to your ~/.bashrc or ~/.zshrc:"
        echo "export RAG_MODEL_TYPE=server"
        ;;
    *)
        echo "Invalid choice. Setting to default (server)"
        export RAG_MODEL_TYPE=server
        ;;
esac

echo ""
echo "Current environment:"
echo "RAG_MODEL_TYPE=$RAG_MODEL_TYPE"
echo "GEMINI_API_KEY=" $(if [ -n "$GEMINI_API_KEY" ]; then echo "✓ Set"; else echo "✗ Not set"; fi)

echo ""
echo "To start the API server with this configuration:"
echo "python api.py"
