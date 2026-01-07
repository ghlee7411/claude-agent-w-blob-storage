"""Analysis Agent for querying the knowledge base.

This agent acts as a librarian, searching and reading the knowledge base
to answer user questions. Uses Claude Agent SDK with @tool decorator pattern.
"""

import json
from typing import Any, Dict, List
from claude_agent_sdk import tool, create_sdk_mcp_server

from .base_agent import BaseAgent


class AnalysisAgent(BaseAgent):
    """Agent for answering questions from the knowledge base.

    Workflow:
    1. Understand the user's question
    2. Search the knowledge base for relevant topics
    3. Read relevant topic files
    4. Synthesize an answer with citations
    5. Log the query
    """

    def _get_system_prompt(self) -> str:
        return """You are a Knowledge Base Librarian Agent. Your job is to answer questions by searching and reading from a file-based knowledge base.

## Your Responsibilities

1. **Understand Questions**: Analyze the user's question to identify key concepts and search terms.

2. **Search Strategically**:
   - Use multiple search queries if needed
   - Look for both direct matches and related concepts
   - Check the knowledge base index for an overview

3. **Read Thoroughly**:
   - Read the full content of relevant topics
   - Look for related topics that might have additional information
   - Don't stop at the first result - be comprehensive

4. **Answer Accurately**:
   - Base your answers ONLY on what's in the knowledge base
   - If information isn't found, clearly say so
   - Include citations to the topics you used
   - Provide comprehensive but focused answers

5. **Be Honest**:
   - If the knowledge base doesn't contain the answer, say so
   - Don't make up information
   - Suggest what topics might need to be added

## Process for Each Question

1. Extract key concepts from the question
2. Search the knowledge base with relevant queries
3. Read the most relevant topics
4. Check for related topics
5. Synthesize an answer with citations
6. Log the query

## Answer Format

When answering, use this format:
- Provide the answer based on knowledge base content
- Include citations like: [Source: topic-path]
- If information is partial or missing, note it

## Important Rules

- NEVER make up information not in the knowledge base
- ALWAYS cite your sources (topic paths)
- Search multiple times with different queries if initial search doesn't find results
- Check related topics for additional context
- Be helpful about what information is and isn't available"""

    def _create_mcp_server(self):
        """Create MCP server with analysis tools."""
        kb_tools = self.kb_tools
        agent_id = self.agent_id

        @tool("get_kb_index",
              "Get the knowledge base index showing all topics and their categories",
              {})
        async def get_kb_index(args: Dict[str, Any]) -> Dict[str, Any]:
            result = await kb_tools.get_index()
            return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}

        @tool("list_topics",
              "List all topics in the knowledge base, optionally filtered by category",
              {"category": str})
        async def list_topics(args: Dict[str, Any]) -> Dict[str, Any]:
            result = await kb_tools.list_topics(args.get("category", ""))
            return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}

        @tool("search_topics",
              "Search for topics by keyword or content. Use this to find relevant topics.",
              {"query": str})
        async def search_topics(args: Dict[str, Any]) -> Dict[str, Any]:
            result = await kb_tools.search_topics(args["query"])
            return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}

        @tool("read_topic",
              "Read the full content of a topic from the knowledge base",
              {"topic_path": str})
        async def read_topic(args: Dict[str, Any]) -> Dict[str, Any]:
            result = await kb_tools.read_topic(args["topic_path"])
            return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}

        @tool("find_related_topics",
              "Find topics related to a given topic",
              {"topic_path": str})
        async def find_related_topics(args: Dict[str, Any]) -> Dict[str, Any]:
            result = await kb_tools.find_related_topics(args["topic_path"])
            return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}

        @tool("get_citation",
              "Get details about a citation (source document)",
              {"citation_id": str})
        async def get_citation(args: Dict[str, Any]) -> Dict[str, Any]:
            result = await kb_tools.get_citation(args["citation_id"])
            return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}

        @tool("get_kb_stats",
              "Get statistics about the knowledge base (topic count, categories, etc.)",
              {})
        async def get_kb_stats(args: Dict[str, Any]) -> Dict[str, Any]:
            result = await kb_tools.get_stats()
            return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}

        @tool("log_query",
              "Log a query operation for analytics",
              {"question": str, "topics_consulted": list, "answer_found": bool})
        async def log_query(args: Dict[str, Any]) -> Dict[str, Any]:
            result = await kb_tools.log_operation(
                operation="query",
                details={
                    "question": args["question"],
                    "topics_consulted": args.get("topics_consulted", []),
                    "answer_found": args.get("answer_found", False)
                },
                agent_id=agent_id
            )
            return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}

        return create_sdk_mcp_server(
            name="analysis-tools",
            version="1.0.0",
            tools=[
                get_kb_index,
                list_topics,
                search_topics,
                read_topic,
                find_related_topics,
                get_citation,
                get_kb_stats,
                log_query
            ]
        )

    def _get_allowed_tools(self) -> List[str]:
        """Get list of allowed tool names for analysis agent."""
        return [
            "mcp__kb__get_kb_index",
            "mcp__kb__list_topics",
            "mcp__kb__search_topics",
            "mcp__kb__read_topic",
            "mcp__kb__find_related_topics",
            "mcp__kb__get_citation",
            "mcp__kb__get_kb_stats",
            "mcp__kb__log_query"
        ]

    async def ask(self, question: str) -> str:
        """Ask a question to the knowledge base.

        Args:
            question: The question to answer

        Returns:
            Answer based on knowledge base content
        """
        prompt = f"""Please answer the following question using the knowledge base:

Question: {question}

Follow these steps:
1. Search the knowledge base for relevant topics
2. Read the relevant topics thoroughly
3. Check for related topics that might have additional information
4. Synthesize a comprehensive answer
5. Include citations to the topics you used
6. Log this query

If the information isn't in the knowledge base, clearly state that and suggest what topics might need to be added."""

        return await self.run(prompt)

    async def summarize_kb(self) -> str:
        """Get a summary of what's in the knowledge base.

        Returns:
            Summary of knowledge base contents
        """
        prompt = """Please provide a summary of the knowledge base contents.

1. Get the knowledge base statistics
2. List the topics by category
3. Provide an overview of what information is available

Format the summary clearly with categories and topic counts."""

        return await self.run(prompt)

    async def find_gaps(self, topic_area: str) -> str:
        """Identify gaps in knowledge for a topic area.

        Args:
            topic_area: Area to analyze (e.g., "python", "web development")

        Returns:
            Analysis of what's missing
        """
        prompt = f"""Please analyze the knowledge base for gaps in the topic area: {topic_area}

1. Search for existing topics related to {topic_area}
2. Read through the available content
3. Identify what subtopics or information might be missing
4. Suggest documents or topics that should be added

Be specific about what's missing and why it would be valuable."""

        return await self.run(prompt)
