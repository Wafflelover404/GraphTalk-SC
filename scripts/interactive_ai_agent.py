#!/usr/bin/env python3
"""
Interactive AI Agent with Command Execution
Run this to use the AI agent interactively
"""

import sys
import os
sys.path.append('/Users/wafflelover404/Documents/wikiai')

from ai_agent_commands import AIAgentCommandExecutor

def interactive_ai_agent():
    """Interactive AI agent session"""
    print("🤖 Interactive AI Agent with Command Execution")
    print("=" * 60)
    print("🔐 Login: test/test")
    print("📚 Available Commands:")
    print("   • <file-content>filename.md</file-content>")
    print("   • <semantic-search>your query</semantic-search>")
    print("   • Type 'files' to see available files")
    print("   • Type 'quit' to exit")
    print("   • Type 'help' for examples")
    print()
    
    agent = AIAgentCommandExecutor()
    
    # Login
    if not agent.login():
        print("❌ Failed to login. Exiting.")
        return
    
    # Get available files
    agent.get_user_available_files()
    
    print(f"\n📄 Found {len(agent.available_files)} available files")
    print("🚀 Ready to process your commands!\n")
    
    # Interactive loop
    while True:
        try:
            user_input = input("🤖 You: ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("👋 Goodbye!")
                break
            
            if user_input.lower() == 'files':
                print(agent.get_available_files_list())
                continue
            
            if user_input.lower() == 'help':
                print("""
📖 **Examples:**
1. Get file content:
   <file-content>ЦЕННОСТИ КОМПАНИИ.md</file-content>

2. Search for information:
   <semantic-search>company rules</semantic-search>

3. Multiple commands:
   <file-content>ПРАВИЛА КОММУНИКАЦИИ.md</file-content>
   <semantic-search>communication guidelines</semantic-search>

4. Mixed request:
   Please analyze this document and find related info:
   <file-content>ЦЕННОСТИ КОМПАНИИ.md</file-content>
   <semantic-search>company values implementation</semantic-search>
                """)
                continue
            
            if not user_input:
                continue
            
            # Parse and execute commands
            command_results, has_commands = agent.parse_and_execute_commands(user_input)
            
            if has_commands:
                print(f"\n🔧 **Command Results:**")
                print(command_results)
                print(f"\n💭 **AI Response:**")
                print("I've executed your commands and retrieved the requested information. What would you like me to help you with next?")
            else:
                print(f"\n💭 **AI Response:**")
                print("I didn't detect any commands in your request. Use <file-content>filename.md</file-content> or <semantic-search>query</semantic-search> to get information.")
                print("Type 'help' for examples.")
            
            print()
            
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    interactive_ai_agent()
