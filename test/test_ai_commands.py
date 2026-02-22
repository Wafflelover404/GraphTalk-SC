#!/usr/bin/env python3
"""
Test AI Agent Command System
"""

import sys
import os
sys.path.append('/Users/wafflelover404/Documents/wikiai')

from ai_agent_commands import AIAgentCommandExecutor
import time

def test_ai_agent_commands():
    """Test the AI agent command system"""
    print("🧪 Testing AI Agent Command System")
    print("=" * 50)
    
    agent = AIAgentCommandExecutor()
    
    # Test login
    print("1. Testing login...")
    if agent.login():
        print("✅ Login successful")
    else:
        print("❌ Login failed")
        return False
    
    # Test getting available files
    print("\n2. Testing file listing...")
    files = agent.get_user_available_files()
    if files:
        print(f"✅ Found {len(files)} files")
        if isinstance(files, list):
            print(f"📄 First few files: {files[:3]}")
        else:
            print(f"📄 Files data: {files}")
    else:
        print("⚠️ No files found or error occurred")
    
    # Test file-content command
    print("\n3. Testing file-content command...")
    if files:
        test_file = files[0]
        test_input = f"Please analyze this file: <file-content>{test_file}</file-content>"
        result, has_commands = agent.parse_and_execute_commands(test_input)
        if has_commands:
            print("✅ File-content command executed")
            print(f"📄 Result preview: {result[:200]}...")
        else:
            print("❌ File-content command not detected")
    else:
        print("⚠️ Skipping file-content test (no files available)")
    
    # Test semantic-search command
    print("\n4. Testing semantic-search command...")
    test_input = "Search for company rules: <semantic-search>Правила компании</semantic-search>"
    result, has_commands = agent.parse_and_execute_commands(test_input)
    if has_commands:
        print("✅ Semantic-search command executed")
        print(f"🔍 Result preview: {result[:300]}...")
    else:
        print("❌ Semantic-search command not detected")
    
    # Test multiple commands
    print("\n5. Testing multiple commands...")
    if files:
        test_input = f"""
        Analyze this file and search for related info:
        <file-content>{files[0]}</file-content>
        <semantic-search>company values</semantic-search>
        """
        result, has_commands = agent.parse_and_execute_commands(test_input)
        if has_commands:
            print("✅ Multiple commands executed")
            print(f"🔧 Commands found and executed successfully")
        else:
            print("❌ Multiple commands not detected")
    
    print("\n🎉 AI Agent Command System Test Complete!")
    return True

if __name__ == "__main__":
    test_ai_agent_commands()
