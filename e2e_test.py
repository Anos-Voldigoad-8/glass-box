#!/usr/bin/env python3
"""
End-to-end test of GLASS BOX functionality.
This script demonstrates:
1. Starting the GLASS BOX backend
2. Using the SDK to create traces
3. Verifying data is stored in the backend
"""

import subprocess
import time
import requests
import json
import sys
import os

def test_glassbox_e2e():
    """Test the full GLASS BOX stack."""
    print("Starting GLASS BOX End-to-End Test")
    print("=" * 50)
    
    # Start the backend server
    print("Starting backend server...")
    server_process = subprocess.Popen(
        [sys.executable, "-m", "server.app"],
        cwd=".",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Give the server time to start
    time.sleep(3)
    
    try:
        # Check if server is running
        print("Checking server health...")
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code == 200:
            print("SUCCESS: Server is healthy!")
            print(f"   Response: {response.json()}")
        else:
            print(f"ERROR: Server health check failed: {response.status_code}")
            return False
            
        # Test SDK functionality
        print("\nTesting SDK...")
        sys.path.insert(0, os.path.join(os.getcwd(), "glassbox"))
        import glassbox as gb
        
        # Configure SDK to point to our local server
        gb.configure(endpoint="http://localhost:8000")
        print("SUCCESS: SDK configured")
        
        # Create a test trace
        print("\nCreating test trace...")
        with gb.trace("e2e-test-workflow", agent_name="test-agent") as trace:
            trace.metadata["test_type"] = "end-to-end"
            
            with gb.step("data_processing", "tool_call") as step:
                step.log("Starting data processing", level="info")
                # Simulate some work
                time.sleep(0.1)
                step.set_metadata("records_processed", 1500)
                step.log("Processed 1500 records", level="info")
                
            with gb.step("model_inference", "llm_call") as step:
                step.log("Running LLM inference", level="info")
                # Mock LLM response
                class MockResponse:
                    class Usage:
                        def __init__(self):
                            self.prompt_tokens = 50
                            self.completion_tokens = 100
                            self.total_tokens = 150
                    
                    def __init__(self):
                        self.usage = self.Usage()
                        self.model = "gpt-4"
                
                response = MockResponse()
                messages = [{"role": "user", "content": "Analyze this data"}]
                gb.capture_llm_call("gpt-4", messages, response)
                step.set_metadata("confidence_score", 0.95)
                
            with gb.step("result_validation", "reasoning") as step:
                step.log("Validating results", level="info")
                # Simulate validation
                validation_passed = True
                step.set_metadata("validation_passed", validation_passed)
                if validation_passed:
                    step.log("Validation passed", level="info")
                else:
                    step.log("Validation failed", level="error")
        
        print("SUCCESS: Test trace created successfully")
        
        # Give time for background flushing
        print("\nWaiting for background flush...")
        time.sleep(3)
        
        # Check if trace was stored
        print("\nVerifying data storage...")
        response = requests.get("http://localhost:8000/sessions", timeout=5)
        if response.status_code == 200:
            traces = response.json()
            print(f"SUCCESS: Retrieved {len(traces)} traces from backend")
            
            if len(traces) > 0:
                latest_trace = traces[0]
                print(f"   Latest trace ID: {latest_trace['id']}")
                print(f"   Trace name: {latest_trace['name']}")
                print(f"   Agent: {latest_trace['agent_name']}")
                print(f"   Status: {latest_trace['status']}")
                print(f"   Spans count: {len(latest_trace['spans'])}")
                
                # Show span details
                for i, span in enumerate(latest_trace['spans']):
                    print(f"     Span {i+1}: {span['name']} ({span['span_type']}) - {span['status']}")
                    
                return True
            else:
                print("WARNING: No traces found in backend")
                return False
        else:
            print(f"ERROR: Failed to retrieve traces: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"ERROR: {e}")
        return False
        
    finally:
        # Clean up server
        print("\nStopping server...")
        server_process.terminate()
        try:
            server_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server_process.kill()
        print("SUCCESS: Server stopped")

if __name__ == "__main__":
    success = test_glassbox_e2e()
    print("\n" + "=" * 50)
    if success:
        print("E2E TEST PASSED!")
        sys.exit(0)
    else:
        print("E2E TEST FAILED!")
        sys.exit(1)