"""
Claude Agent with File System Storage Integration

This module demonstrates how to use Claude Agent SDK with file system storage tools
to build a knowledge base that can be continuously updated.

The agent can:
- Read and write documents to file storage
- Search through stored documents
- Answer questions based on stored knowledge
- Update and maintain the knowledge base
"""

import os
import json
from typing import List, Dict, Any
from anthropic import Anthropic
from storage_tools import FileSystemStorage, get_storage_tools


class KnowledgeBaseAgent:
    """Claude Agent with knowledge base storage capabilities"""
    
    def __init__(self, api_key: str = None, storage_path: str = "./storage", model: str = "claude-3-5-sonnet-20241022"):
        """
        Initialize the Knowledge Base Agent
        
        Args:
            api_key: Anthropic API key (if None, reads from ANTHROPIC_API_KEY env var)
            storage_path: Path to storage directory
            model: Claude model to use
        """
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("API key must be provided or set in ANTHROPIC_API_KEY environment variable")
        
        self.client = Anthropic(api_key=self.api_key)
        self.storage = FileSystemStorage(storage_path)
        self.model = model
        self.tools = get_storage_tools()
        
    def _process_tool_call(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a tool call from Claude
        
        Args:
            tool_name: Name of the tool to call
            tool_input: Input parameters for the tool
            
        Returns:
            Result from the tool execution
        """
        if tool_name == "read_file":
            return self.storage.read_file(tool_input["file_path"])
        elif tool_name == "write_file":
            return self.storage.write_file(
                tool_input["file_path"],
                tool_input["content"],
                tool_input.get("mode", "w")
            )
        elif tool_name == "list_files":
            return self.storage.list_files(
                tool_input.get("directory", ""),
                tool_input.get("pattern", "*")
            )
        elif tool_name == "delete_file":
            return self.storage.delete_file(tool_input["file_path"])
        elif tool_name == "search_files":
            return self.storage.search_files(
                tool_input["search_text"],
                tool_input.get("directory", ""),
                tool_input.get("file_pattern", "*")
            )
        else:
            return {"success": False, "error": f"Unknown tool: {tool_name}"}
    
    def run(self, user_message: str, max_turns: int = 10) -> str:
        """
        Run the agent with a user message
        
        Args:
            user_message: User's input message
            max_turns: Maximum number of turns to process
            
        Returns:
            Agent's final response
        """
        messages = [{"role": "user", "content": user_message}]
        
        for turn in range(max_turns):
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                tools=self.tools,
                messages=messages
            )
            
            # Check if we're done
            if response.stop_reason == "end_turn":
                # Extract text response
                text_response = ""
                for block in response.content:
                    if block.type == "text":
                        text_response += block.text
                return text_response
            
            # Process tool calls
            if response.stop_reason == "tool_use":
                # Add assistant's response to messages
                messages.append({"role": "assistant", "content": response.content})
                
                # Process each tool call
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        tool_result = self._process_tool_call(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(tool_result)
                        })
                
                # Add tool results to messages
                messages.append({"role": "user", "content": tool_results})
            else:
                # Unexpected stop reason
                break
        
        return "Maximum turns reached without completion"
    
    def run_interactive(self):
        """
        Run the agent in interactive mode
        """
        print("Knowledge Base Agent - Interactive Mode")
        print("=" * 50)
        print("Commands:")
        print("  - Type your message to interact with the agent")
        print("  - Type 'quit' or 'exit' to stop")
        print("=" * 50)
        print()
        
        while True:
            try:
                user_input = input("You: ").strip()
                if user_input.lower() in ['quit', 'exit']:
                    print("Goodbye!")
                    break
                
                if not user_input:
                    continue
                
                response = self.run(user_input)
                print(f"\nAgent: {response}\n")
                
            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
            except Exception as e:
                print(f"\nError: {e}\n")


def main():
    """Main entry point for the agent"""
    import sys
    
    # Check for API key
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY environment variable not set")
        print("Please set it with: export ANTHROPIC_API_KEY='your-api-key'")
        sys.exit(1)
    
    # Initialize agent
    agent = KnowledgeBaseAgent(api_key=api_key)
    
    # Check if a message was provided as command line argument
    if len(sys.argv) > 1:
        message = " ".join(sys.argv[1:])
        response = agent.run(message)
        print(response)
    else:
        # Run in interactive mode
        agent.run_interactive()


if __name__ == "__main__":
    main()
