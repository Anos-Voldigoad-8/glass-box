"""
Example Agent Demonstrating GLASS BOX SDK Usage

This example shows how to instrument a multi-agent system with the GLASS BOX SDK.
"""

import time
import random
import openai  # This would be your actual LLM client
from typing import List, Dict, Any

from glassbox.glassbox import configure, trace, step, capture_llm_call, trace_decorator, log

# Configure the SDK (in real usage, this would point to your backend)
configure(
    endpoint="http://localhost:8000",  # GLASS BOX backend
    batch_size=5,
    flush_interval=2.0
)

# Mock LLM client for demonstration
class MockLLMClient:
    """Mock LLM client that simulates API calls with token usage."""
    
    def __init__(self, model_name: str = "gpt-4"):
        self.model_name = model_name
    
    def chat_completion(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """Simulate a chat completion call."""
        # Simulate processing time
        time.sleep(random.uniform(0.5, 2.0))
        
        # Generate mock response
        response_text = f"This is a simulated response to: {messages[-1]['content'][:50]}..."
        
        # Mock token usage
        prompt_tokens = sum(len(msg['content'].split()) for msg in messages) * 1.3
        completion_tokens = len(response_text.split()) * 1.3
        
        return {
            "id": f"chatcmpl-{hash(str(messages))}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": self.model_name,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response_text
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": int(prompt_tokens),
                "completion_tokens": int(completion_tokens),
                "total_tokens": int(prompt_tokens + completion_tokens)
            }
        }

# Initialize mock LLM client
llm_client = MockLLMClient()

@trace_decorator(agent_name="research-agent")
def research_agent(user_query: str) -> str:
    """
    Research agent that gathers information based on user query.
    """
    with step("analyze_query", "reasoning"):
        # Analyze the user query to determine research approach
        analysis_prompt = f"Analyze this research query and determine the best approach: {user_query}"
        messages = [{"role": "user", "content": analysis_prompt}]
        
        with step("llm-analysis", "llm_call"):
            response = llm_client.chat_completion(messages)
            capture_llm_call("gpt-4", messages, response)
        
        research_plan = response['choices'][0]['message']['content']
        log(f"Research plan: {research_plan[:100]}...", level="info")
    
    # Simulate gathering information from multiple sources
    sources = []
    for i in range(3):
        with step(f"gather_source_{i+1}", "tool_call"):
            # Simulate web search or database query
            time.sleep(random.uniform(0.3, 1.0))
            
            search_query = f"Information about {user_query} source {i+1}"
            sources.append({
                "title": f"Source {i+1}: {search_query}",
                "content": f"Detailed information about {user_query} from source {i+1}",
                "relevance": round(random.uniform(0.7, 0.95), 2)
            })
            
            log(f"Gathered source {i+1}: {search_query}", level="info")
    
    with step("synthesize_information", "reasoning"):
        # Synthesize information from all sources
        synthesis_prompt = f"""
        Based on the following sources, provide a comprehensive answer to: {user_query}
        
        Sources:
        {chr(10).join([f"- {s['title']}: {s['content'][:100]}..." for s in sources])}
        """
        
        messages = [{"role": "user", "content": synthesis_prompt}]
        
        with step("llm-synthesis", "llm_call"):
            response = llm_client.chat_completion(messages)
            capture_llm_call("gpt-4", messages, response)
        
        synthesis = response['choices'][0]['message']['content']
        log(f"Synthesis complete: {len(synthesis)} characters", level="info")
    
    return synthesis

@trace_decorator(agent_name="writing-agent")
def writing_agent(research_content: str, tone: str = "informative") -> str:
    """
    Writing agent that creates content based on research.
    """
    with step("plan_content", "reasoning"):
        # Plan the content structure
        planning_prompt = f"""
        Create an outline for a {tone} piece based on this research:
        {research_content[:200]}...
        """
        
        messages = [{"role": "user", "content": planning_prompt}]
        
        with step("llm-planning", "llm_call"):
            response = llm_client.chat_completion(messages)
            capture_llm_call("gpt-4", messages, response)
        
        outline = response['choices'][0]['message']['content']
        log(f"Created outline: {outline[:50]}...", level="info")
    
    with step("write_content", "tool_call"):
        # Write the actual content
        writing_prompt = f"""
        Write a {tone} article based on this outline:
        {outline}
        
        Use information from this research:
        {research_content[:300]}...
        """
        
        messages = [{"role": "user", "content": writing_prompt}]
        
        with step("llm-writing", "llm_call"):
            response = llm_client.chat_completion(messages)
            capture_llm_call("gpt-4", messages, response)
        
        content = response['choices'][0]['message']['content']
        word_count = len(content.split())
        log(f"Writing complete: {word_count} words", level="info")
    
    return content

@trace_decorator(agent_name="editor-agent")
def edit_article(content: str) -> str:
    """
    Editor agent that reviews and improves content.
    """
    with step("review_content", "reasoning"):
        # Review the content for quality
        review_prompt = f"""
        Review and improve the following content for clarity, grammar, and flow:
        
        {content[:400]}...
        """
        
        messages = [{"role": "user", "content": review_prompt}]
        
        with step("llm-review", "llm_call"):
            response = llm_client.chat_completion(messages)
            capture_llm_call("gpt-4", messages, response)
        
        feedback = response['choices'][0]['message']['content']
        log(f"Review completed with feedback", level="info")
    
    with step("edit_content", "tool_call"):
        # Apply edits based on feedback
        edit_prompt = f"""
        Please revise the following content based on this feedback:
        
        ORIGINAL CONTENT:
        {content[:500]}...
        
        FEEDBACK:
        {feedback}
        
        Provide the improved version:
        """
        
        messages = [{"role": "user", "content": edit_prompt}]
        
        with step("llm-edit", "llm_call"):
            response = llm_client.chat_completion(messages)
            capture_llm_call("gpt-4", messages, response)
        
        edited_content = response['choices'][0]['message']['content']
        improvement = len(edited_content.split()) - len(content.split())
        log(f"Editing complete: {improvement:+d} words change", level="info")
    
    return edited_content

def main():
    """Main function demonstrating the multi-agent workflow."""
    print("[START] Starting GLASS BOX Multi-Agent Demo...")
    
    # Example user query
    user_query = "What are the latest developments in renewable energy storage technology?"
    
    print(f"\n[QUERY] User Query: {user_query}")
    print("=" * 50)
    
    # Step 1: Research
    print("\n[PHASE 1] Research")
    research_result = research_agent(user_query)
    print(f"Research completed: {len(research_result.split())} words")
    
    # Step 2: Writing
    print("\n[PHASE 2] Writing")
    draft_content = writing_agent(research_result, tone="informative")
    print(f"Draft created: {len(draft_content.split())} words")
    
    # Step 3: Editing
    print("\n[PHASE 3] Editing")
    final_content = edit_article(draft_content)
    print(f"Final article: {len(final_content.split())} words")
    
    print("\n" + "=" * 50)
    print("[OUTPUT] FINAL OUTPUT:")
    print("=" * 50)
    print(final_content)
    print("=" * 50)
    
    print("\n[DONE] Demo complete! Check your GLASS BOX dashboard for traces.")
    
    # Give time for background flushing
    time.sleep(3)

if __name__ == "__main__":
    main()
