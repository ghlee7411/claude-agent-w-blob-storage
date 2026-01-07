"""Base agent with common functionality for Claude Agent SDK integration."""

import os
import uuid
from typing import Any, Dict, List, Optional

from storage import FileSystemStorage
from tools.kb_tools import KnowledgeBaseTools
from tools.document_tools import DocumentTools


class BaseAgent:
    """Base class for knowledge base agents using Claude Agent SDK.

    Provides common setup for both Ingest and Analysis agents.
    Uses @tool decorator pattern from Claude Agent SDK.
    """

    def __init__(
        self,
        storage_path: str = "./knowledge_base",
        model: str = "claude-sonnet-4-20250514",
        api_key: Optional[str] = None
    ):
        """Initialize base agent.

        Args:
            storage_path: Path to knowledge base storage
            model: Claude model to use
            api_key: Anthropic API key (defaults to env var)
        """
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")

        self.model = model
        self.agent_id = f"agent-{uuid.uuid4().hex[:8]}"
        self.storage_path = storage_path

        # Initialize components
        self.storage = FileSystemStorage(storage_path)
        self.kb_tools = KnowledgeBaseTools(self.storage)
        self.doc_tools = DocumentTools()

    def _get_system_prompt(self) -> str:
        """Get system prompt for the agent.

        Subclasses should override to provide specific prompts.
        """
        return "You are a helpful assistant."

    def _create_mcp_server(self):
        """Create MCP server with tools.

        Subclasses should override to provide specific tools.
        """
        raise NotImplementedError("Subclasses must implement _create_mcp_server")

    def _get_allowed_tools(self) -> List[str]:
        """Get list of allowed tool names.

        Subclasses should override to provide specific tool list.
        """
        return []

    async def run(self, user_message: str, max_turns: int = 15) -> str:
        """Run the agent with a user message using Claude Agent SDK.

        Args:
            user_message: User's input
            max_turns: Maximum conversation turns

        Returns:
            Agent's final response
        """
        from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, TextBlock

        mcp_server = self._create_mcp_server()
        system_prompt = self._get_system_prompt()
        allowed_tools = self._get_allowed_tools()

        options = ClaudeAgentOptions(
            model=self.model,
            system_prompt=system_prompt,
            max_turns=max_turns,
            mcp_servers={"kb": mcp_server},
            allowed_tools=allowed_tools if allowed_tools else None
        )

        full_response = ""

        async for message in query(prompt=user_message, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        full_response = block.text  # Take the last text response

        return full_response if full_response else "No response generated"
