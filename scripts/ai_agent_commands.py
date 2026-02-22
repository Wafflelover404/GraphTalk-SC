#!/usr/bin/env python3
"""
AI Agent with Command Execution System
Supports commands:
- <file-content>filename.md</file-content>
- <semantic-search>query</semantic-search>
"""

import requests
import json
import websocket
import threading
import time
import uuid
import re
import os
from typing import List, Dict, Optional, Tuple

# Configuration
BACKEND_URL = "http://localhost:9001"
WS_URL = "ws://localhost:9001/ws/query"

class AIAgentCommandExecutor:
    def __init__(self):
        self.token = None
        self.username = None
        self.available_files = []
        
    def login(self, username: str = "test", password: str = "test") -> bool:
        """Login to get authentication token"""
        login_data = {
            "username": username,
            "password": password
        }
        
        try:
            response = requests.post(f"{BACKEND_URL}/login", json=login_data, headers={"ngrok-skip-browser-warning": "true"})
            
            if response.status_code != 200:
                print(f"❌ Login failed: {response.status_code}")
                return False
                
            login_result = response.json()
            if login_result.get("status") != "success":
                print(f"❌ Login failed: {login_result.get('message')}")
                return False
                
            self.token = login_result.get("token")
            self.username = username
            print(f"✅ Login successful as {username}")
            return True
            
        except Exception as e:
            print(f"❌ Login error: {str(e)}")
            return False
    
    def get_user_available_files(self) -> List[str]:
        """Get list of files available to the user"""
        if not self.token:
            print("❌ Not logged in")
            return []
        
        try:
            response = requests.get(
                f"{BACKEND_URL}/files/list",
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "ngrok-skip-browser-warning": "true"
                }
            )
            
            if response.status_code == 200:
                files_data = response.json()
                if files_data.get("status") == "success":
                    response_data = files_data.get("response", {})
                    documents = response_data.get("documents", [])
                    # Extract filenames from documents
                    self.available_files = [doc.get("filename", "") for doc in documents if doc.get("filename")]
                    print(f"📄 Found {len(self.available_files)} available files")
                    return self.available_files
            else:
                print(f"❌ Failed to get files: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Error getting files: {str(e)}")
        
        return []
    
    def execute_file_content_command(self, filename: str) -> str:
        """Execute <file-content>filename.md</file-content> command"""
        print(f"📂 Executing file-content command for: {filename}")
        
        if not self.token:
            return "❌ Not authenticated"
        
        try:
            response = requests.get(
                f"{BACKEND_URL}/files/content/{filename}",
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "ngrok-skip-browser-warning": "true"
                }
            )
            
            if response.status_code == 200:
                # The endpoint returns plain text content
                content = response.text
                print(f"✅ Successfully retrieved content for {filename}")
                return f"📄 **Content of {filename}:**\n\n```\n{content}\n```"
            else:
                return f"❌ HTTP Error {response.status_code}: {response.text}"
                
        except Exception as e:
            return f"❌ Error retrieving file content: {str(e)}"
    
    def execute_semantic_search_command(self, query: str) -> str:
        """Execute <semantic-search>query</semantic-search> command"""
        print(f"🔍 Executing semantic-search command for: {query}")
        
        if not self.token:
            return "❌ Not authenticated"
        
        # Use WebSocket for real-time search
        ws_url_with_token = f"{WS_URL}?token={self.token}"
        messages_received = []
        
        def on_message(ws, message):
            try:
                data = json.loads(message)
                messages_received.append(data)
            except Exception as e:
                print(f"❌ Error parsing WebSocket message: {e}")
        
        def on_error(ws, error):
            print(f"❌ WebSocket error: {error}")
        
        def on_close(ws, close_status_code, close_msg):
            pass
        
        def on_open(ws):
            query_data = {
                "question": query,
                "humanize": True,
                "session_id": str(uuid.uuid4()),
                "ai_agent_mode": True
            }
            ws.send(json.dumps(query_data))
        
        # Create WebSocket connection
        ws = websocket.WebSocketApp(
            ws_url_with_token,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
            on_open=on_open
        )
        
        # Run WebSocket
        ws_thread = threading.Thread(target=ws.run_forever)
        ws_thread.daemon = True
        ws_thread.start()
        
        # Wait for completion
        timeout = 20
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if any(msg.get("type") == "complete" for msg in messages_received):
                break
            if any(msg.get("type") == "error" for msg in messages_received):
                break
            time.sleep(0.2)
        
        ws.close()
        
        # Process results
        if any(msg.get("type") == "complete" for msg in messages_received):
            results = []
            for msg in messages_received:
                if msg.get("type") == "immediate":
                    immediate_data = msg.get("data", {})
                    snippets = immediate_data.get("snippets", [])
                    
                    for i, snippet in enumerate(snippets[:5]):  # Limit to top 5 results
                        source = snippet.get("source", "unknown")
                        content = snippet.get("content", "")[:300] + "..." if len(snippet.get("content", "")) > 300 else snippet.get("content", "")
                        results.append(f"**{i+1}. {source}**\n{content}")
                
                elif msg.get("type") == "overview":
                    overview = msg.get("data", "")
                    results.insert(0, f"🤖 **AI Overview:** {overview}")
            
            if results:
                print(f"✅ Semantic search completed for: {query}")
                return "\n\n".join(results)
            else:
                return "🔍 No results found for the semantic search query."
        else:
            return "❌ Semantic search timed out or failed"
    
    def parse_and_execute_commands(self, user_input: str) -> Tuple[str, bool]:
        """Parse user input for commands and execute them"""
        commands_found = []
        results = []
        
        # Find file-content commands
        file_content_pattern = r'<file-content>(.*?)</file-content>'
        file_matches = re.findall(file_content_pattern, user_input, re.DOTALL)
        
        for filename in file_matches:
            filename = filename.strip()
            if filename:
                commands_found.append(f"file-content:{filename}")
                result = self.execute_file_content_command(filename)
                results.append(f"**Command Result:** {result}")
        
        # Find semantic-search commands
        semantic_search_pattern = r'<semantic-search>(.*?)</semantic-search>'
        search_matches = re.findall(semantic_search_pattern, user_input, re.DOTALL)
        
        for query in search_matches:
            query = query.strip()
            if query:
                commands_found.append(f"semantic-search:{query}")
                result = self.execute_semantic_search_command(query)
                results.append(f"**Command Result:** {result}")
        
        if commands_found:
            print(f"🔧 Executed {len(commands_found)} commands: {', '.join(commands_found)}")
            return "\n\n".join(results), True
        else:
            return "", False
    
    def get_available_files_list(self) -> str:
        """Get formatted list of available files"""
        if not self.available_files:
            self.get_user_available_files()
        
        if self.available_files:
            file_list = "\n".join([f"- {file}" for file in self.available_files[:20]])  # Limit to 20 files
            return f"📄 **Available Files:**\n{file_list}"
        else:
            return "📄 No files available or failed to retrieve file list."

def main():
    """Run AI Agent with command execution"""
    print("🤖 AI Agent with Command Execution System")
    print("=" * 50)
    print("Supported commands:")
    print("- <file-content>filename.md</file-content>")
    print("- <semantic-search>your query</semantic-search>")
    print()
    
    agent = AIAgentCommandExecutor()
    
    # Login
    if not agent.login():
        print("❌ Failed to login. Exiting.")
        return
    
    # Get available files
    agent.get_user_available_files()
    
    print(f"\n📄 Available files: {len(agent.available_files)} files")
    print("Type 'files' to see available files, 'quit' to exit")
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
                continue
            
            if not user_input:
                continue
            
            # Parse and execute commands
            command_results, has_commands = agent.parse_and_execute_commands(user_input)
            
            if has_commands:
                print(f"\n🔧 **Command Execution Results:**")
                print(command_results)
                print(f"\n🤖 **AI Response:**")
                print("I've executed your commands. Here are the results. What would you like me to do with this information?")
            else:
                # Regular AI response (for now, just echo)
                print(f"\n🤖 **AI Response:**")
                print(f"You said: {user_input}")
                print("Use <file-content>filename.md</file-content> or <semantic-search>query</semantic-search> commands to get information.")
            
            print()
            
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    main()
