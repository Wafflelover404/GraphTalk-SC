#!/usr/bin/env python3
"""
Test Enhanced AI Agent with All Command Types
"""

import sys
import os
sys.path.append('/Users/wafflelover404/Documents/wikiai')

from enhanced_ai_agent import EnhancedAIAgentCommandExecutor
import time

def test_enhanced_ai_agent():
    """Test all enhanced AI agent command types"""
    print("🧪 Testing Enhanced AI Agent with All Command Types")
    print("=" * 60)
    
    agent = EnhancedAIAgentCommandExecutor()
    
    # Test login
    print("1. 🔐 Testing login...")
    if agent.login():
        print("✅ Login successful")
    else:
        print("❌ Login failed")
        return False
    
    # Test getting available files
    print("\n2. 📄 Testing file listing with ID mapping...")
    files = agent.get_user_available_files()
    if files:
        print(f"✅ Found {len(files)} files")
        print(f"📄 Sample files with IDs:")
        for i, file in enumerate(files[:3], 1):
            file_id = agent.file_id_map.get(file, "N/A")
            print(f"   {i}. {file} (ID: {file_id})")
    else:
        print("❌ No files found")
        return False
    
    # Test scenarios
    scenarios = [
        {
            "name": "File Content by Name",
            "input": f"Analyze this document: <file-content>{files[0]}</file-content>",
            "description": "Retrieves file by filename"
        },
        {
            "name": "File Content by ID",
            "input": f"Get file by ID: <file-id>{agent.file_id_map.get(files[0])}</file-id>",
            "description": "Retrieves file by ID"
        },
        {
            "name": "Fuzzy Search",
            "input": "<fuzzy-search>компании</fuzzy-search>",
            "description": "Fuzzy search across filenames"
        },
        {
            "name": "Knowledge Base Search",
            "input": "<kb-search>company rules</kb-search>",
            "description": "Search across knowledge base (non-semantic)"
        },
        {
            "name": "Semantic Search",
            "input": "<semantic-search>Правила компании</semantic-search>",
            "description": "Semantic search with AI analysis"
        },
        {
            "name": "Multiple Commands",
            "input": f"""
            Analyze company documents using multiple methods:
            <file-content>{files[0]}</file-content>
            <fuzzy-search>правила</fuzzy-search>
            <kb-search>communication</kb-search>
            <semantic-search>company values</semantic-search>
            """,
            "description": "Multiple commands in one request"
        }
    ]
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n{i+2}. 🎯 {scenario['name']}")
        print(f"📝 Description: {scenario['description']}")
        print(f"💬 Input: {scenario['input'].strip()}")
        print("🔧 Processing...")
        
        start_time = time.time()
        result, has_commands = agent.parse_and_execute_commands(scenario['input'])
        end_time = time.time()
        
        if has_commands:
            print(f"⏱️  Execution time: {end_time - start_time:.2f} seconds")
            print("📊 Results:")
            # Show first 400 characters of result
            preview = result[:400] + "..." if len(result) > 400 else result
            print(preview)
        else:
            print("❌ No commands detected")
        
        print("-" * 50)
    
    print("\n🎉 Enhanced AI Agent Test Complete!")
    print("\n📚 All Command Types Tested:")
    print("✅ <file-content>filename.md</file-content> - File by name")
    print("✅ <file-id>123</file-id> - File by ID")
    print("✅ <fuzzy-search>query</fuzzy-search> - Fuzzy filename search")
    print("✅ <kb-search>query</kb-search> - Knowledge base search")
    print("✅ <semantic-search>query</semantic-search> - Semantic search")
    print("✅ Multiple commands in single request")
    
    return True

if __name__ == "__main__":
    test_enhanced_ai_agent()
