"""Basic test for GLASS BOX SDK."""

import glassbox as gb
import time


def example_function():
    """Example function to trace."""
    time.sleep(0.01)  # Simulate work
    return "Hello, World!"


def example_agent_workflow():
    """Example agent workflow with tracing."""
    with gb.trace("agent.research_task", agent_name="research-agent"):
        # Log some information
        print("Starting research task...")
        
        # Trace a function call
        with gb.step("search_web", "tool_call"):
            time.sleep(0.02)
            results = ["result1", "result2", "result3"]
            
        # Trace another step
        with gb.step("analyze_results", "reasoning"):
            time.sleep(0.01)
            summary = f"Found {len(results)} results"
            
        return summary


@gb.trace("decorated_function")
def decorated_function(x, y):
    """Function traced with decorator."""
    time.sleep(0.01)
    return x + y


def main():
    """Main function demonstrating SDK usage."""
    print("Testing GLASS BOX SDK...")
    
    # Test context manager trace
    with gb.trace("manual-trace", agent_name="test-agent"):
        result1 = example_function()
        print(f"Function result: {result1}")
    
    # Test decorator
    result2 = decorated_function(5, 3)
    print(f"Decorated function result: {result2}")
    
    # Test complex workflow
    result3 = example_agent_workflow()
    print(f"Workflow result: {result3}")
    
    print("Test completed!")


if __name__ == "__main__":
    main()