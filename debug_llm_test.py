#!/usr/bin/env python3

import os
from dotenv import load_dotenv
from groq import Groq

# Load environment variables
load_dotenv()

# Test what the LLM actually returns
api_key = os.getenv('GROQ_API_KEY')
if not api_key:
    print("No GROQ_API_KEY found")
    exit(1)

print(f"Using API key: {api_key[:20]}...")

# Try to initialize Groq client with fallback methods
client = None
try:
    # Try basic initialization
    client = Groq(api_key=api_key)
    print("Groq client initialized successfully (method 1)")
except Exception as e:
    print(f"Groq init attempt 1 failed: {e}")
    
    # Try with explicit httpx client
    try:
        import httpx
        clean_client = httpx.Client()
        client = Groq(api_key=api_key, http_client=clean_client)
        print("Groq client initialized with custom httpx client (method 2)")
    except Exception as e2:
        print(f"Groq init attempt 2 failed: {e2}")
        exit(1)

response = client.chat.completions.create(
    model="llama-3.3-70b-versatile",
    messages=[
        {
            "role": "system",
            "content": "You are a helpful assistant that generates JSON arrays. Always respond with valid JSON only."
        },
        {
            "role": "user", 
            "content": "Generate a JSON array with one object containing pattern_id: 0, pattern_name: 'Test Pattern', and difficulty: 'easy'"
        }
    ],
    temperature=0.7,
    max_tokens=1000
)

print("Raw response:")
print(response.choices[0].message.content)
print("\n" + "="*50 + "\n")

# Try to parse it
import json
try:
    parsed = json.loads(response.choices[0].message.content)
    print("Parsed successfully:")
    print(parsed)
except Exception as e:
    print(f"Parsing failed: {e}")
