import json
import asyncio
import urllib.request
import urllib.error


OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "gemma3:latest" 

SYSTEM_PROMPT = """
You are a professional workplace English communication coach.

The user communicates with their manager in English.

For every incoming message:
1. Explain its meaning in natural Persian.
2. Separate explicit meaning from possible intentions.
3. Clearly state what is unknown.
4. Suggest three natural English replies:
   - Short and direct
   - Professional and friendly
   - More formal
5. Explain in Persian when each reply is appropriate.
6. Do not invent deadlines, promises, facts, or missing context.
7. Use natural workplace English. Avoid unnecessarily formal language.

If the context is insufficient, explain the uncertainty.
Do not send messages or claim that a message has been sent.
"""

def get_suggestions(message):
    payload = {
        "model": MODEL,
        "stream": False,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": message}
        ],
        "options": {
            "temperature": 0.3
        }
    }
    
    request = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    
    with urllib.request.urlopen(request, timeout=180) as response:
        result = json.loads(response.read().decode("utf-8"))
    
    return result["message"]["content"]


def main():
    print("\n=== Workplace English Assistant ===")
    print(f"Local model: {MODEL}")
    print("Paste a message from your manager.")
    print("Type 'exit' to quit.\n")

    while True:
        message = input("Manager's message: ").strip()
        
        if message.lower() == "exit":
            print("Goodbye")
            break
        
        if not message:
            continue
        
        try:
            print("\nAnalyzing message...\n")
            answer = get_suggestions(message)
            print(answer)
        except urllib.error.URLError as error:
            print(f"\nCould not connect to Ollama: {error}")
            print("Make sure Ollama is running.")
        except (KeyError, json.JSONDecodeError) as error:
            print(f"\nUnexpected response from Ollama: {error}")
        except TimeoutError:
            print("\nThe request timed out. Try again.")
        
        print("\n" + '-' * 50 + "\n")
    
    


if __name__ == "__main__":
    main()

