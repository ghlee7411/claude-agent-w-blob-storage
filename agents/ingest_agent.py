"""Ingest Agent for processing documents into the knowledge base.

This agent reads external documents, analyzes their content, and
integrates the information into the file-based knowledge base.
Uses Claude Agent SDK with @tool decorator pattern.
"""

import json
from typing import Any, Dict, List
from claude_agent_sdk import tool, create_sdk_mcp_server

from .base_agent import BaseAgent


class IngestAgent(BaseAgent):
    """Agent for ingesting documents into the knowledge base.

    Workflow:
    1. Parse the input document
    2. Analyze content and extract topics
    3. Search existing knowledge base for related content
    4. Decide: create new topics or update existing ones
    5. Write changes with citations
    6. Log the operation
    """

    def _get_system_prompt(self) -> str:
        return """You are a Knowledge Base Curator Agent. Your job is to ingest documents and integrate their information into a structured, file-based knowledge base.

## Your Responsibilities

1. **Analyze Documents**: When given a document, understand its main topics, concepts, and key information.

2. **Search Existing Knowledge**: Before creating new content, always search the knowledge base to find related existing topics.

3. **Integrate Intelligently**:
   - If a topic already exists: UPDATE it by adding new information with proper citations
   - If a topic is new: CREATE a new topic file in the appropriate category
   - Always maintain connections between related topics

4. **Maintain Quality**:
   - Write clear, well-structured markdown content
   - Include proper citations to source documents
   - Use appropriate categories (e.g., python/, javascript/, concepts/)
   - Extract meaningful keywords for searchability

5. **Follow the Pattern**:
   - Topic paths use format: category/topic-name (e.g., python/gil, concepts/concurrency)
   - Always add citations when adding or modifying content
   - Update related_topics when connections exist

## Process for Each Document

1. First, read and understand the document content
2. List the knowledge base topics to see what exists
3. Search for potentially related topics
4. For each piece of significant information:
   a. Decide if it fits an existing topic or needs a new one
   b. Read the existing topic if updating
   c. Write the updated or new content
5. Create a citation record
6. Log the operation

## Important Rules

- NEVER skip searching existing topics before creating new ones
- ALWAYS include citations for new information
- Keep topic files focused - one main concept per file
- Use lowercase-with-hyphens for topic names
- Preserve existing content when updating - add to it, don't replace"""

    def _create_mcp_server(self):
        """Create MCP server with ingest tools."""
        kb_tools = self.kb_tools
        doc_tools = self.doc_tools
        agent_id = self.agent_id

        @tool("parse_document",
              "Parse an external document file (.txt, .html, .md) and extract its content and structure",
              {"file_path": str})
        async def parse_document(args: Dict[str, Any]) -> Dict[str, Any]:
            result = await doc_tools.parse_document(args["file_path"])
            return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}

        @tool("list_topics",
              "List all topics in the knowledge base, optionally filtered by category",
              {"category": str})
        async def list_topics(args: Dict[str, Any]) -> Dict[str, Any]:
            result = await kb_tools.list_topics(args.get("category", ""))
            return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}

        @tool("search_topics",
              "Search for topics by keyword or content",
              {"query": str})
        async def search_topics(args: Dict[str, Any]) -> Dict[str, Any]:
            result = await kb_tools.search_topics(args["query"])
            return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}

        @tool("read_topic",
              "Read the content and metadata of an existing topic",
              {"topic_path": str})
        async def read_topic(args: Dict[str, Any]) -> Dict[str, Any]:
            result = await kb_tools.read_topic(args["topic_path"])
            return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}

        @tool("write_topic",
              "Create or update a topic in the knowledge base",
              {"topic_path": str, "content": str, "title": str, "keywords": list, "related_topics": list, "citation_id": str})
        async def write_topic(args: Dict[str, Any]) -> Dict[str, Any]:
            citations = [args["citation_id"]] if args.get("citation_id") else None
            result = await kb_tools.write_topic(
                topic_path=args["topic_path"],
                content=args["content"],
                title=args["title"],
                keywords=args.get("keywords", []),
                related_topics=args.get("related_topics"),
                citations=citations,
                agent_id=agent_id
            )
            return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}

        @tool("append_to_topic",
              "Add new content to an existing topic (preserves existing content)",
              {"topic_path": str, "additional_content": str, "citation_id": str})
        async def append_to_topic(args: Dict[str, Any]) -> Dict[str, Any]:
            result = await kb_tools.append_to_topic(
                topic_path=args["topic_path"],
                additional_content=args["additional_content"],
                citation_id=args.get("citation_id"),
                agent_id=agent_id
            )
            return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}

        @tool("add_citation",
              "Create a citation record for a source document",
              {"source_document": str, "contributed_topics": list, "summary": str})
        async def add_citation(args: Dict[str, Any]) -> Dict[str, Any]:
            result = await kb_tools.add_citation(
                source_document=args["source_document"],
                contributed_topics=args["contributed_topics"],
                summary=args["summary"],
                agent_id=agent_id
            )
            return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}

        @tool("log_operation",
              "Log an ingest operation for tracking",
              {"operation": str, "details": dict})
        async def log_operation(args: Dict[str, Any]) -> Dict[str, Any]:
            result = await kb_tools.log_operation(
                operation=args["operation"],
                details=args.get("details", {}),
                agent_id=agent_id
            )
            return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}

        @tool("get_kb_stats",
              "Get statistics about the knowledge base",
              {})
        async def get_kb_stats(args: Dict[str, Any]) -> Dict[str, Any]:
            result = await kb_tools.get_stats()
            return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}

        return create_sdk_mcp_server(
            name="ingest-tools",
            version="1.0.0",
            tools=[
                parse_document,
                list_topics,
                search_topics,
                read_topic,
                write_topic,
                append_to_topic,
                add_citation,
                log_operation,
                get_kb_stats
            ]
        )

    def _get_allowed_tools(self) -> List[str]:
        """Get list of allowed tool names for ingest agent."""
        return [
            "mcp__kb__parse_document",
            "mcp__kb__list_topics",
            "mcp__kb__search_topics",
            "mcp__kb__read_topic",
            "mcp__kb__write_topic",
            "mcp__kb__append_to_topic",
            "mcp__kb__add_citation",
            "mcp__kb__log_operation",
            "mcp__kb__get_kb_stats"
        ]

    async def ingest(self, document_path: str) -> str:
        """Ingest a document into the knowledge base.

        Args:
            document_path: Path to the document to ingest

        Returns:
            Summary of what was done
        """
        prompt = f"""Please ingest the following document into the knowledge base:

Document path: {document_path}

Follow these steps:
1. Parse the document to understand its content
2. Check what topics already exist in the knowledge base
3. Search for related existing topics
4. For each significant piece of information:
   - Either update an existing topic or create a new one
   - Include proper citations
5. Create a citation record for this document
6. Log the operation

Provide a summary of what topics were created or updated."""

        return await self.run(prompt)

    async def ingest_content(self, content: str, source_name: str) -> str:
        """Ingest raw content directly (without file).

        Args:
            content: Text content to ingest
            source_name: Name to use for citation

        Returns:
            Summary of what was done
        """
        prompt = f"""Please ingest the following content into the knowledge base:

Source: {source_name}

Content:
---
{content}
---

Follow these steps:
1. Analyze the content to understand its topics
2. Check what topics already exist in the knowledge base
3. Search for related existing topics
4. For each significant piece of information:
   - Either update an existing topic or create a new one
   - Include proper citations referencing "{source_name}"
5. Create a citation record
6. Log the operation

Provide a summary of what topics were created or updated."""

        return await self.run(prompt)
