#!/usr/bin/env python3
"""
Test script to verify Google ADK Runner API usage
Run this to understand the correct way to use InMemoryRunner
"""

import asyncio
from agents.postcall_orchestrator import postcall_orchestrator
from google.adk.runners import InMemoryRunner

# Sample test input
test_input = """
Rep: Hi John, thanks for taking time today.

Prospect: Hi, thanks for reaching out. I'm interested in your data solution.

Rep: Great! Can you tell me about your current challenges?

Prospect: We're processing 2TB daily and our ETL takes 12 hours. We need something faster.

Rep: Our platform can reduce that to under 90 minutes. Would you like to see a demo?

Prospect: Yes, let's schedule one for next Tuesday.

Rep: Perfect! I'll send you a calendar invite today.
"""

print("="*60)
print("Google ADK Runner API Test")
print("="*60)

# Test different API patterns
print("\n1. Testing Pattern 1: runner.run(state_dict)")
print("-"*60)
try:
    runner1 = InMemoryRunner(postcall_orchestrator)
    result1 = asyncio.run(runner1.run({"input": test_input}))
    print("✅ SUCCESS: Pattern 1 works!")
    print(f"Result keys: {result1.keys() if isinstance(result1, dict) else type(result1)}")
except TypeError as e:
    print(f"❌ FAILED: {e}")
except Exception as e:
    print(f"❌ ERROR: {e}")

print("\n2. Testing Pattern 2: runner.run() with no args")
print("-"*60)
try:
    runner2 = InMemoryRunner(postcall_orchestrator, input_data=test_input)
    result2 = asyncio.run(runner2.run())
    print("✅ SUCCESS: Pattern 2 works!")
    print(f"Result keys: {result2.keys() if isinstance(result2, dict) else type(result2)}")
except TypeError as e:
    print(f"❌ FAILED: {e}")
except Exception as e:
    print(f"❌ ERROR: {e}")

print("\n3. Testing Pattern 3: Direct agent call")
print("-"*60)
try:
    # Try calling the agent directly
    from agents.analyst_agent_server import analyst_agent
    
    # This pattern might work depending on ADK version
    result3 = analyst_agent.process(test_input)
    print("✅ SUCCESS: Pattern 3 works!")
    print(f"Result: {result3}")
except AttributeError as e:
    print(f"❌ FAILED: {e}")
except Exception as e:
    print(f"❌ ERROR: {e}")

print("\n4. Testing Pattern 4: Check InMemoryRunner signature")
print("-"*60)
try:
    import inspect
    
    # Get InMemoryRunner.__init__ signature
    init_sig = inspect.signature(InMemoryRunner.__init__)
    print(f"InMemoryRunner.__init__ signature: {init_sig}")
    
    # Get run method signature
    run_sig = inspect.signature(InMemoryRunner.run)
    print(f"InMemoryRunner.run signature: {run_sig}")
    
    print("\n✅ Check the signatures above to understand correct usage")
except Exception as e:
    print(f"❌ ERROR: {e}")

print("\n5. Testing Pattern 5: Check available methods")
print("-"*60)
try:
    runner5 = InMemoryRunner(postcall_orchestrator)
    methods = [m for m in dir(runner5) if not m.startswith('_')]
    print(f"Available methods: {methods}")
    
    # Try to find the right method
    if hasattr(runner5, 'execute'):
        print("\nFound 'execute' method - trying it...")
        result5 = asyncio.run(runner5.execute(test_input))
        print(f"✅ SUCCESS: execute() works! Result: {type(result5)}")
    elif hasattr(runner5, 'start'):
        print("\nFound 'start' method - trying it...")
        result5 = asyncio.run(runner5.start(test_input))
        print(f"✅ SUCCESS: start() works! Result: {type(result5)}")
except Exception as e:
    print(f"❌ ERROR: {e}")

print("\n" + "="*60)
print("Test Complete")
print("="*60)
print("\nRecommendation: Use the pattern that succeeded above in app.py")