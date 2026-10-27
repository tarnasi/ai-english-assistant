
import json
import queue
import threading
import urllib.request
import urllib.error
import tkinter as tk
from tkinter import ttk, messagebox


OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "gemma3:latest"



SYSTEM_PROMPT = """
You are a careful, practical workplace English coach.
The user receives messages from their manager and needs help understanding
them and drafting an appropriate reply.

IMPORTANT:
The manager wrote the incoming message. The user is the recipient.
Never reverse their roles.

For every incoming message, use this structure:

1. MEANING IN PERSIAN
Translate the original message accurately into natural Persian.
Do not turn a statement into a question or add meaning that is not present.
Use Persian script only; do not add Persian transliteration in Latin letters.

2. EXPLICIT REQUEST
Explain briefly what the manager actually said or asked.

3. POSSIBLE INTENTION
Mention only plausible interpretations supported by the wording.
Do not assume hidden motives, urgency, blame, or dissatisfaction.
If the intention is unknown, say so.

4. WHAT IS UNKNOWN
Mention only missing information that matters for choosing a reply.

5. THREE SUGGESTED REPLIES
A. Short and direct.
B. Professional and friendly.
C. More formal but still natural.

For each reply, explain its tone and appropriate use in Persian.

STRICT RULES FOR SUGGESTED REPLIES:
- Never claim an action has already been completed unless the user confirmed it.
  For example, do not suggest "Sent" when the user has not said it was sent.
- Never admit fault, apologize for a mistake, or accept blame unless
  the user has confirmed responsibility or explicitly wants to apologize.
- Never invent facts, reasons, questions, deadlines, or commitments.
- Do not promise to send, review, investigate, or follow up by a specific time
  unless the user has provided that information.
- When responsibility or context is unclear, prefer a neutral response
  that acknowledges the message without admitting fault.
- Do not make the user sound defensive, excessively apologetic, or submissive.
- Keep English replies concise, idiomatic, and appropriate for a workplace.
- Do not make the formal option unnecessarily stiff.
- Avoid phrases that imply more than the user has agreed to do.

6. BEST DEFAULT
Choose the safest natural reply based only on known information.
Explain briefly why it is appropriate.
If no reply can be safely chosen without more context, say what needs clarifying.

Be concise and practical.
Never claim a message has been sent.
FINAL SAFETY CHECK BEFORE ANSWERING:
Review all three suggested replies.
Remove any apology, admission of fault, claim of completed action,
or future commitment that is not supported by the user's context.
If the manager's message asks for an explanation but the facts are unknown,
prefer a neutral clarification question.
Do not label an apology as "without admitting fault."
Persian explanations must use Persian script only; omit transliteration.
"""



def get_suggestions(message):
    payload = {
        "model": MODEL,
        "stream": False,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": message},
        ],
        "options": {"temperature": 0.2},
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


class EnglishAssistant:
    def __init__(self, root):
        self.root = root
        self.root.title("Workplace English Assistant")
        self.root.geometry("850x720")
        self.root.minsize(650, 550)

        self.results = queue.Queue()

        container = ttk.Frame(root, padding=14)
        container.pack(fill="both", expand=True)

        ttk.Label(
            container,
            text="Workplace English Assistant",
            font=("TkDefaultFont", 18, "bold"),
        ).pack(anchor="w")

        ttk.Label(
            container,
            text="Paste your manager's message below. Nothing is sent to Telegram.",
        ).pack(anchor="w", pady=(4, 10))

        self.message_box = tk.Text(container, height=6, wrap="word")
        self.message_box.pack(fill="x", pady=(0, 10))

        controls = ttk.Frame(container)
        controls.pack(fill="x", pady=(0, 10))

        self.analyze_button = ttk.Button(
            controls,
            text="Analyze message",
            command=self.analyze,
        )
        self.analyze_button.pack(side="left")

        ttk.Button(
            controls,
            text="Clear",
            command=self.clear,
        ).pack(side="left", padx=8)

        self.status = tk.StringVar(value=f"Local model: {MODEL}")
        ttk.Label(
            container,
            textvariable=self.status,
        ).pack(anchor="w", pady=(0, 6))

        ttk.Label(
            container,
            text="Analysis and suggested replies",
            font=("TkDefaultFont", 12, "bold"),
        ).pack(anchor="w")

        output_frame = ttk.Frame(container)
        output_frame.pack(fill="both", expand=True, pady=(6, 10))

        self.output = tk.Text(
            output_frame,
            wrap="word",
            state="disabled",
            font=("TkDefaultFont", 12),
            padx=10,
            pady=10,
        )

        scrollbar = ttk.Scrollbar(
            output_frame,
            orient="vertical",
            command=self.output.yview,
        )
        self.output.configure(yscrollcommand=scrollbar.set)

        self.output.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        bottom = ttk.Frame(container)
        bottom.pack(fill="x")

        ttk.Button(
            bottom,
            text="Copy selected text",
            command=self.copy_selected,
        ).pack(side="left")

        ttk.Button(
            bottom,
            text="Copy all results",
            command=self.copy_all,
        ).pack(side="left", padx=8)

        self.root.after(100, self.check_results)

    def analyze(self):
        message = self.message_box.get("1.0", "end").strip()

        if not message:
            messagebox.showinfo(
                "Message needed",
                "Paste your manager's message first.",
            )
            return

        self.analyze_button.configure(state="disabled")
        self.status.set("Analyzing locally with Ollama...")
        self.show_output("Analyzing message. Please wait...")

        thread = threading.Thread(
            target=self.worker,
            args=(message,),
            daemon=True,
        )
        thread.start()

    def worker(self, message):
        try:
            answer = get_suggestions(message)
            self.results.put(("success", answer))
        except urllib.error.URLError as error:
            self.results.put((
                "error",
                f"Could not connect to Ollama.\n\n"
                f"Check that Ollama is running.\n\nDetails: {error}",
            ))
        except (KeyError, json.JSONDecodeError) as error:
            self.results.put(("error", f"Unexpected Ollama response:\n{error}"))
        except TimeoutError:
            self.results.put((
                "error",
                "The request timed out. Try again.",
            ))
        except Exception as error:
            self.results.put(("error", f"Unexpected error:\n{error}"))

    def check_results(self):
        try:
            while True:
                kind, content = self.results.get_nowait()
                self.show_output(content)
                self.analyze_button.configure(state="normal")

                if kind == "success":
                    self.status.set("Analysis complete.")
                else:
                    self.status.set("Analysis failed.")
        except queue.Empty:
            pass

        self.root.after(100, self.check_results)

    def show_output(self, text):
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.insert("1.0", text)
        self.output.configure(state="disabled")

    def copy_selected(self):
        try:
            selected = self.output.get("sel.first", "sel.last")
        except tk.TclError:
            messagebox.showinfo(
                "Select text",
                "Select some text in the results first.",
            )
            return

        self.root.clipboard_clear()
        self.root.clipboard_append(selected)
        self.status.set("Selected text copied.")

    def copy_all(self):
        content = self.output.get("1.0", "end").strip()

        if not content:
            return

        self.root.clipboard_clear()
        self.root.clipboard_append(content)
        self.status.set("All results copied.")

    def clear(self):
        self.message_box.delete("1.0", "end")
        self.show_output("")
        self.status.set(f"Local model: {MODEL}")

    def run(self):
        self.root.mainloop()


def main():
    root = tk.Tk()
    EnglishAssistant(root).run()


if __name__ == "__main__":
    main()
