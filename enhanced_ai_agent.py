#!/usr/bin/env python3
"""
Enhanced AI Agent with Additional Command Types
Supports:
- <file-content>filename.md</file-content> (existing)
- <file-id>123</file-id> (new - access by ID)
- <fuzzy-search>query</fuzzy-search> (new - fuzzy search)
- <kb-search>query</kb-search> (new - knowledge base search)
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
from difflib import SequenceMatcher

# Configuration
BACKEND_URL = "http://localhost:9001"
WS_URL = "ws://localhost:9001/ws/query"

class EnhancedAIAgentCommandExecutor:
    def __init__(self):
        self.token = None
        self.username = None
        self.available_files = []
        self.file_id_map = {}  # Map filenames to IDs
        
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
        """Get list of files available to the user with ID mapping"""
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
                    
                    # Extract filenames and create ID mapping
                    self.available_files = []
                    self.file_id_map = {}
                    
                    for doc in documents:
                        filename = doc.get("filename", "")
                        file_id = doc.get("id")
                        if filename:
                            self.available_files.append(filename)
                            self.file_id_map[filename] = file_id
                            # Also map by ID for reverse lookup
                            self.file_id_map[str(file_id)] = filename
                    
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
                content = response.text
                print(f"✅ Successfully retrieved content for {filename}")
                return f"📄 **Content of {filename}:**\n\n```\n{content}\n```"
            else:
                return f"❌ HTTP Error {response.status_code}: {response.text}"
                
        except Exception as e:
            return f"❌ Error retrieving file content: {str(e)}"
    
    def execute_file_id_command(self, file_id: str) -> str:
        """Execute <file-id>123</file-id> command"""
        print(f"🆔 Executing file-id command for: {file_id}")
        
        if not self.token:
            return "❌ Not authenticated"
        
        # Look up filename by ID
        filename = self.file_id_map.get(file_id)
        if not filename:
            return f"❌ File ID {file_id} not found"
        
        # Use the existing file content method
        return self.execute_file_content_command(filename)
    
    def execute_fuzzy_search_command(self, query: str) -> str:
        """Execute <fuzzy-search>query</fuzzy-search> command"""
        print(f"🔍 Executing fuzzy-search command for: {query}")
        
        if not self.available_files:
            return "❌ No files available for search"
        
        # Convert query to lowercase for case-insensitive search
        query_lower = query.lower()
        matches = []
        
        for filename in self.available_files:
            filename_lower = filename.lower()
            
            # Check for exact match
            if query_lower in filename_lower:
                similarity = SequenceMatcher(None, query_lower, filename_lower).ratio()
                matches.append((filename, similarity))
        
        # Sort by similarity score (highest first)
        matches.sort(key=lambda x: x[1], reverse=True)
        
        if matches:
            result_lines = [f"🔍 **Fuzzy Search Results for '{query}':**\n"]
            
            for filename, similarity in matches[:10]:  # Top 10 results
                match_type = "Exact match" if query_lower in filename.lower() else f"Similarity: {similarity:.2f}"
                result_lines.append(f"📄 **{filename}** ({match_type})")
            
            return "\n".join(result_lines)
        else:
            return f"🔍 No files found matching '{query}'"
    
    def execute_kb_search_command(self, query: str) -> str:
        """Execute <kb-search>query</kb-search> command - search across knowledge base"""
        print(f"🌐 Executing kb-search command for: {query}")
        
        if not self.token:
            return "❌ Not authenticated"
        
        # Use WebSocket for standard search (non-semantic) to avoid HTTP endpoint issues
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
                "ai_agent_mode": False  # Use standard search for KB search
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
        timeout = 15
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
                    
                    for i, snippet in enumerate(snippets[:5], 1):  # Limit to top 5 results
                        source = snippet.get("source", "unknown")
                        content = snippet.get("content", "")[:200] + "..." if len(snippet.get("content", "")) > 200 else snippet.get("content", "")
                        results.append(f"**{i}. {source}**\n{content}")
                
                elif msg.get("type") == "overview":
                    overview = msg.get("data", "")
                    results.insert(0, f"🌐 **Knowledge Base Search Overview:** {overview}")
            
            if results:
                print(f"✅ KB search completed for: {query}")
                return "\n\n".join(results)
            else:
                return "🌐 No results found for the knowledge base search query."
        else:
            return "❌ Knowledge base search timed out or failed"
    
    def execute_semantic_search_command(self, query: str) -> str:
        """Execute <semantic-search>query</semantic-search> command"""
        print(f"🧠 Executing semantic-search command for: {query}")
        
        if not self.token:
            return "❌ Not authenticated"
        
        # Use WebSocket for real-time AI-agent search
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
                    
                    for i, snippet in enumerate(snippets[:5], 1):  # Limit to top 5 results
                        source = snippet.get("source", "unknown")
                        content = snippet.get("content", "")[:300] + "..." if len(snippet.get("content", "")) > 300 else snippet.get("content", "")
                        results.append(f"**{i}. {source}**\n{content}")
                
                elif msg.get("type") == "overview":
                    overview = msg.get("data", "")
                    results.insert(0, f"🧠 **Semantic Search Overview:** {overview}")
            
            if results:
                print(f"✅ Semantic search completed for: {query}")
                return "\n\n".join(results)
            else:
                return "🧠 No results found for the semantic search query."
        else:
            return "❌ Semantic search timed out or failed"
    
    def parse_and_execute_commands(self, user_input: str) -> Tuple[str, bool]:
        """Parse user input for all supported commands and execute them"""
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
        
        # Find file-id commands
        file_id_pattern = r'<file-id>(.*?)</file-id>'
        file_id_matches = re.findall(file_id_pattern, user_input, re.DOTALL)
        
        for file_id in file_id_matches:
            file_id = file_id.strip()
            if file_id:
                commands_found.append(f"file-id:{file_id}")
                result = self.execute_file_id_command(file_id)
                results.append(f"**Command Result:** {result}")
        
        # Find fuzzy-search commands
        fuzzy_search_pattern = r'<fuzzy-search>(.*?)</fuzzy-search>'
        fuzzy_matches = re.findall(fuzzy_search_pattern, user_input, re.DOTALL)
        
        for query in fuzzy_matches:
            query = query.strip()
            if query:
                commands_found.append(f"fuzzy-search:{query}")
                result = self.execute_fuzzy_search_command(query)
                results.append(f"**Command Result:** {result}")
        
        # Find kb-search commands
        kb_search_pattern = r'<kb-search>(.*?)</kb-search>'
        kb_matches = re.findall(kb_search_pattern, user_input, re.DOTALL)
        
        for query in kb_matches:
            query = query.strip()
            if query:
                commands_found.append(f"kb-search:{query}")
                result = self.execute_kb_search_command(query)
                results.append(f"**Command Result:** {result}")
        
        # Find semantic-search commands
        semantic_search_pattern = r'<semantic-search>(.*?)</semantic-search>'
        semantic_matches = re.findall(semantic_search_pattern, user_input, re.DOTALL)
        
        for query in semantic_matches:
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
        """Get formatted list of available files with IDs"""
        if not self.available_files:
            self.get_user_available_files()
        
        if self.available_files:
            file_list = []
            for filename in self.available_files[:20]:  # Limit to 20 files
                file_id = self.file_id_map.get(filename, "N/A")
                file_list.append(f"- **{filename}** (ID: {file_id})")
            
            return f"📄 **Available Files:**\n" + "\n".join(file_list)
        else:
            return "📄 No files available or failed to retrieve file list."
    
    def get_help_text(self) -> str:
        """Get help text for all available commands"""
        return """
📖 **Available Commands:**

1. **File Content by Name:**
   `<file-content>filename.md</file-content>`
   Example: `<file-content>ЦЕННОСТИ КОМПАНИИ.md</file-content>`

2. **File Content by ID:**
   `<file-id>123</file-id>`
   Example: `<file-id>13</file-id>`

3. **Fuzzy Search:**
   `<fuzzy-search>query</fuzzy-search>`
   Example: `<fuzzy-search>компании</fuzzy-search>`

4. **Knowledge Base Search:**
   `<kb-search>query</kb-search>`
   Example: `<kb-search>company rules</kb-search>`

5. **Semantic Search:**
   `<semantic-search>query</semantic-search>`
   Example: `<semantic-search>company values</semantic-search>`

6. **Multiple Commands:**
   You can use multiple commands in one request:
   ```
   <file-content>ЦЕННОСТИ КОМПАНИИ.md</file-content>
   <fuzzy-search>правила</fuzzy-search>
   <semantic-search>communication</semantic-search>
   ```

7. **Other Commands:**
   - `files` - Show available files with IDs
   - `help` - Show this help message
   - `quit` - Exit the agent
        """

def main():
    """Run enhanced AI agent with all command types"""
    print("🤖 Enhanced AI Agent with Multiple Command Types")
    print("=" * 60)
    
    agent = EnhancedAIAgentCommandExecutor()
    
    # Login
    if not agent.login():
        print("❌ Failed to login. Exiting.")
        return
    
    # Get available files
    agent.get_user_available_files()
    
    print(f"\n📄 Found {len(agent.available_files)} available files")
    print("🚀 Ready to process your commands!")
    print("Type 'help' to see all available commands")
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
            
            if user_input.lower() == 'help':
                print(agent.get_help_text())
                continue
            
            if not user_input:
                continue
            
            # Parse and execute commands
            command_results, has_commands = agent.parse_and_execute_commands(user_input)
            
            if has_commands:
                print(f"\n🔧 **Command Execution Results:**")
                print(command_results)
                print(f"\n💭 **AI Response:**")
                print("I've executed your commands and retrieved the requested information. What would you like me to help you with next?")
            else:
                print(f"\n💭 **AI Response:**")
                print("I didn't detect any commands in your request. Use <file-content>, <file-id>, <fuzzy-search>, <kb-search>, or <semantic-search> commands to get information.")
                print("Type 'help' to see all available commands.")
            
            print()
            
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    main()
