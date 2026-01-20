#!/usr/bin/env python3
"""
Interactive Enhanced AI Agent Demo
Run this to use the enhanced AI agent with all command types
"""

import sys
import os
sys.path.append('/Users/wafflelover404/Documents/wikiai')

from enhanced_ai_agent import EnhancedAIAgentCommandExecutor

def interactive_enhanced_demo():
    """Interactive enhanced AI agent demonstration"""
    print("🤖 Enhanced AI Agent - All Command Types")
    print("=" * 60)
    print("🔐 Login: test/test")
    print()
    print("📚 **All Available Commands:**")
    print("   📄 File Access:")
    print("      • <file-content>filename.md</file-content>")
    print("      • <file-id>123</file-id>")
    print("   🔍 Search Types:")
    print("      • <fuzzy-search>query</fuzzy-search> (filename search)")
    print("      • <kb-search>query</kb-search> (knowledge base search)")
    print("      • <semantic-search>query</semantic-search> (AI-powered search)")
    print("   🛠️  Other Commands:")
    print("      • 'files' - Show available files with IDs")
    print("      • 'help' - Show command examples")
    print("      • 'quit' - Exit")
    print()
    
    agent = EnhancedAIAgentCommandExecutor()
    
    # Login
    if not agent.login():
        print("❌ Failed to login. Exiting.")
        return
    
    # Get available files
    agent.get_user_available_files()
    
    print(f"📄 Found {len(agent.available_files)} available files")
    print("🚀 Ready to process your commands!")
    print()
    
    # Interactive loop
    while True:
        try:
            user_input = input("🤖 You: ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("👋 Goodbye!")
                break
            
            if user_input.lower() == 'files':
                print(agent.get_available_files_list())
                print()
                continue
            
            if user_input.lower() == 'help':
                print(agent.get_help_text())
                print()
                continue
            
            if not user_input:
                continue
            
            # Parse and execute commands
            command_results, has_commands = agent.parse_and_execute_commands(user_input)
            
            if has_commands:
                print(f"\n🔧 **Command Results:**")
                print(command_results)
                print(f"\n💭 **AI Response:**")
                print("I've executed your commands and retrieved the requested information. You can now ask me to analyze, summarize, or work with this data. What would you like to do next?")
            else:
                print(f"\n💭 **AI Response:**")
                print("I didn't detect any commands in your request. Use the available commands to get information:")
                print("📄 File access: <file-content>filename.md</file-content> or <file-id>123</file-id>")
                print("🔍 Search: <fuzzy-search>, <kb-search>, or <semantic-search>")
                print("Type 'help' for detailed examples.")
            
            print()
            
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    interactive_enhanced_demo()
