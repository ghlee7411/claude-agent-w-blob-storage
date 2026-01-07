"""
Example scripts demonstrating the Knowledge Base Agent capabilities
"""

import os
from agent import KnowledgeBaseAgent


def example_1_basic_storage():
    """Example 1: Basic file storage operations"""
    print("=" * 60)
    print("Example 1: Basic File Storage Operations")
    print("=" * 60)
    
    agent = KnowledgeBaseAgent()
    
    # Store a document
    message = """
    Please store the following information in a file called 'tech_info/python.txt':
    
    Python is a high-level programming language known for its simplicity and readability.
    It was created by Guido van Rossum and first released in 1991.
    Python supports multiple programming paradigms including procedural, object-oriented, and functional programming.
    """
    
    print(f"\nUser: {message}")
    response = agent.run(message)
    print(f"\nAgent: {response}\n")


def example_2_knowledge_base():
    """Example 2: Building a knowledge base"""
    print("=" * 60)
    print("Example 2: Building a Knowledge Base")
    print("=" * 60)
    
    agent = KnowledgeBaseAgent()
    
    # Add multiple documents
    documents = [
        ("tech_info/javascript.txt", "JavaScript is a programming language commonly used for web development."),
        ("tech_info/java.txt", "Java is a class-based, object-oriented programming language."),
        ("tech_info/go.txt", "Go is a statically typed, compiled programming language designed at Google.")
    ]
    
    for file_path, content in documents:
        message = f"Please store this information in '{file_path}': {content}"
        print(f"\nUser: {message}")
        response = agent.run(message)
        print(f"Agent: {response}")
    
    # List all files
    message = "What files do we have in the tech_info directory?"
    print(f"\n\nUser: {message}")
    response = agent.run(message)
    print(f"Agent: {response}\n")


def example_3_search_and_query():
    """Example 3: Searching and querying the knowledge base"""
    print("=" * 60)
    print("Example 3: Search and Query")
    print("=" * 60)
    
    agent = KnowledgeBaseAgent()
    
    # Search for content
    message = "Search for files that mention 'programming language'"
    print(f"\nUser: {message}")
    response = agent.run(message)
    print(f"\nAgent: {response}")
    
    # Ask a question that requires reading files
    message = "Tell me about Python based on what's stored in our knowledge base"
    print(f"\n\nUser: {message}")
    response = agent.run(message)
    print(f"\nAgent: {response}\n")


def example_4_update_knowledge():
    """Example 4: Updating existing knowledge"""
    print("=" * 60)
    print("Example 4: Update Existing Knowledge")
    print("=" * 60)
    
    agent = KnowledgeBaseAgent()
    
    # Update a document
    message = """
    Please append this additional information to 'tech_info/python.txt':
    
    Python 3.0, released in 2008, introduced many major changes to the language.
    Popular Python frameworks include Django for web development and PyTorch for machine learning.
    """
    
    print(f"\nUser: {message}")
    response = agent.run(message)
    print(f"\nAgent: {response}")
    
    # Read the updated content
    message = "Show me the complete content of tech_info/python.txt"
    print(f"\n\nUser: {message}")
    response = agent.run(message)
    print(f"\nAgent: {response}\n")


def run_all_examples():
    """Run all examples sequentially"""
    try:
        example_1_basic_storage()
        example_2_knowledge_base()
        example_3_search_and_query()
        example_4_update_knowledge()
        
        print("\n" + "=" * 60)
        print("All examples completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\nError running examples: {e}")
        print("Make sure ANTHROPIC_API_KEY is set in your environment")


if __name__ == "__main__":
    import sys
    
    # Check for API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY environment variable not set")
        print("Please set it with: export ANTHROPIC_API_KEY='your-api-key'")
        sys.exit(1)
    
    run_all_examples()
