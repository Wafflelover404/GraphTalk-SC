#!/usr/bin/env python3
"""
Demonstration of AI Agent with Command Execution
Shows how the agent processes commands and provides results
"""

import sys
import os
sys.path.append('/Users/wafflelover404/Documents/wikiai')

from ai_agent_commands import AIAgentCommandExecutor
import time

def demo_ai_agent():
    """Demonstrate AI agent capabilities"""
    print("🤖 AI Agent Command System Demonstration")
    print("=" * 60)
    
    agent = AIAgentCommandExecutor()
    
    # Login
    print("1. 🔐 Logging in...")
    if agent.login():
        print("✅ Login successful")
    else:
        print("❌ Login failed")
        return
    
    # Get available files
    print("\n2. 📄 Getting available files...")
    files = agent.get_user_available_files()
    if files:
        print(f"✅ Found {len(files)} files")
        print("📋 Sample files:")
        for i, file in enumerate(files[:5], 1):
            print(f"   {i}. {file}")
    else:
        print("❌ No files found")
        return
    
    # Demo scenarios
    scenarios = [
        {
            "name": "File Content Analysis",
            "input": f"Please analyze this company document: <file-content>{files[0]}</file-content>",
            "description": "Retrieves and analyzes a specific file"
        },
        {
            "name": "Semantic Search",
            "input": "<semantic-search>Правила компании</semantic-search>",
            "description": "Searches for company rules using semantic search"
        },
        {
            "name": "Combined Commands",
            "input": f"""
            Analyze the company values and search for related communication rules:
            <file-content>ЦЕННОСТИ КОМПАНИИ.md</file-content>
            <semantic-search>communication rules</semantic-search>
            """,
            "description": "Uses multiple commands in one request"
        }
    ]
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n{i+1}. 🎯 {scenario['name']}")
        print(f"📝 Description: {scenario['description']}")
        print(f"💬 Input: {scenario['input'].strip()}")
        print("🔧 Processing...")
        
        start_time = time.time()
        result, has_commands = agent.parse_and_execute_commands(scenario['input'])
        end_time = time.time()
        
        if has_commands:
            print(f"⏱️  Execution time: {end_time - start_time:.2f} seconds")
            print("📊 Results:")
            # Show first 500 characters of result
            preview = result[:500] + "..." if len(result) > 500 else result
            print(preview)
        else:
            print("❌ No commands detected")
        
        print("-" * 40)
    
    print("\n🎉 Demonstration Complete!")
    print("\n📚 Available Commands:")
    print("- <file-content>filename.md</file-content> - Retrieve file content")
    print("- <semantic-search>query</semantic-search> - Perform semantic search")
    print("\n💡 Tips:")
    print("- Use multiple commands in one request")
    print("- Commands are executed in parallel when possible")
    print("- Results are returned in command execution order")

if __name__ == "__main__":
    demo_ai_agent()
