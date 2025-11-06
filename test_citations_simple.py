#!/usr/bin/env python3
"""
Simple test to verify citations are working with Anthropic API
"""
import os
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

# Test 1: Simple search_result with citations enabled
print("=" * 80)
print("TEST 1: Simple search_result with citations")
print("=" * 80)

search_results = [
    {
        "type": "search_result",
        "source": "test_source",
        "title": "Medical Results",
        "content": [{
            "type": "text",
            "text": "The 30-day mortality rate was 23.8% in the surgical group and 71.4% in the control group."
        }],
        "citations": {"enabled": True}
    }
]

instruction = {
    "type": "text",
    "text": "What was the mortality rate in the surgical group? Quote the exact text."
}

content = search_results + [instruction]

try:
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=500,
        messages=[{"role": "user", "content": content}]
    )

    print(f"\nResponse content blocks: {len(response.content)}")
    for i, block in enumerate(response.content):
        print(f"\nBlock {i}:")
        print(f"  Type: {block.type}")
        print(f"  Text: {block.text[:200]}...")
        print(f"  Has citations attr: {hasattr(block, 'citations')}")
        if hasattr(block, 'citations'):
            print(f"  Citations value: {block.citations}")
            print(f"  Citations type: {type(block.citations)}")

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()

# Test 2: Try with alternative model
print("\n\n" + "=" * 80)
print("TEST 2: Try with claude-sonnet-4-5 (latest stable)")
print("=" * 80)

try:
    response2 = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=500,
        messages=[{"role": "user", "content": content}]
    )

    print(f"\nResponse content blocks: {len(response2.content)}")
    for i, block in enumerate(response2.content):
        print(f"\nBlock {i}:")
        print(f"  Type: {block.type}")
        print(f"  Has citations attr: {hasattr(block, 'citations')}")
        if hasattr(block, 'citations'):
            print(f"  Citations value: {block.citations}")

except Exception as e:
    print(f"\n❌ Error: {e}")
