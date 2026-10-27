
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
You are a careful workplace English communication coach.
The user receives messages from their manager and wants help replying.
The incoming message is written by the manager, not by the user.

Return ONLY one valid JSON object, without Markdown or extra text.
Use exactly this structure:
{
  "meaning_fa": "Accurate, natural Persian translation of the manager's original message",
  "explicit_request_fa": "What the manager explicitly says or asks, in Persian",
  "possible_intention_fa": "Plausible intentions in Persian, or say unclear",
  "unknowns_fa": "Important missing context in Persian, or say none",
  "replies": [
    {
      "id": "A",
      "tone_fa": "Short description of tone in Persian",
      "text": "Natural English reply",
      "translation_fa": "Accurate Persian translation of this exact English reply",
      "when_fa": "When this reply is appropriate, in Persian"
    },
    {
      "id": "B",
      "tone_fa": "Short description of tone in Persian",
      "text": "Natural English reply",
      "translation_fa": "Accurate Persian translation of this exact English reply",
      "when_fa": "When this reply is appropriate, in Persian"
    },
    {
      "id": "C",
      "tone_fa": "Short description of tone in Persian",
      "text": "Natural English reply",
      "translation_fa": "Accurate Persian translation of this exact English reply",
      "when_fa": "When this reply is appropriate, in Persian"
    }
  ],
  "best_reply_id": "A",
  "best_reason_fa": "Why this is the safest suitable reply, in Persian"
}

Rules:
- All explanations and translations must use Persian script.
- Translate the manager's message faithfully without adding meaning.
- Translate each suggested reply accurately. The translation must match its English text.
- Separate facts from possible intentions. Never invent hidden motives.
- Never assume the user is responsible for an omission or mistake.
- Never apologize for an alleged mistake unless the user explicitly confirms responsibility.
- Do not promise to review, investigate, fix, or double-check anything unless the user asks to make that commitment.
- Never invent facts, deadlines, or commitments.
- If context is missing, prefer a neutral clarification question.
- Keep English replies concise, natural, and suitable for workplace communication.
- Make the three replies meaningfully different in tone.
- All three replies must follow the safety rules above.
- The best reply must be A, B, or C.
- Return valid JSON with every required key.
"""


def get_suggestions(message):
    payload = {
        "model": MODEL,
        "stream": False,
        "format": "json",
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

    raw = result["message"]["content"].strip()
    start = raw.find("{")
    end = raw.rfind("}")

    if start == -1 or end < start:
        raise ValueError("The model did not return a JSON object.")

    data = json.loads(raw[start:end + 1])

    required = [
        "meaning_fa",
        "explicit_request_fa",
        "possible_intention_fa",
        "unknowns_fa",
        "replies",
        "best_reply_id",
        "best_reason_fa",
    ]

    for key in required:
        if key not in data:
            raise ValueError(f"Missing field: {key}")

    if not isinstance(data["replies"], list) or len(data["replies"]) != 3:
        raise ValueError("The model must return exactly three replies.")

    expected_ids = {"A", "B", "C"}
    actual_ids = {reply.get("id") for reply in data["replies"]}

    if actual_ids != expected_ids:
        raise ValueError("Replies must have IDs A, B, and C.")

    for reply in data["replies"]:
        for key in ("id", "tone_fa", "text", "translation_fa", "when_fa"):
            if key not in reply:
                raise ValueError(f"A reply is missing the field: {key}")

    if data["best_reply_id"] not in expected_ids:
        raise ValueError("Invalid recommended reply ID.")

    return data


class EnglishAssistant:
    def __init__(self, root):
        self.root = root
        self.root.title("Workplace English Assistant")
        self.root.geometry("1000x900")
        self.root.minsize(700, 650)

        self.results = queue.Queue()
        self.reply_vars = {}

        style = ttk.Style()
        style.configure("Analyze.TButton", padding=(12, 7))
        style.configure("Copy.TButton", padding=(10, 5))
        style.configure("Card.TLabelframe", padding=12)
        style.configure(
            "Card.TLabelframe.Label",
            font=("TkDefaultFont", 12, "bold"),
        )

        outer = ttk.Frame(root, padding=16)
        outer.pack(fill="both", expand=True)

        ttk.Label(
            outer,
            text="Workplace English Assistant",
            font=("TkDefaultFont", 19, "bold"),
        ).pack(anchor="w")

        ttk.Label(
            outer,
            text=(
                "Paste your manager's message. "
                "Analysis stays local; nothing is sent to Telegram."
            ),
            wraplength=900,
        ).pack(anchor="w", pady=(5, 12))

        # More visible message input box
        input_frame = tk.Frame(
            outer,
            highlightthickness=2,
            highlightbackground="#7A9CC6",
            highlightcolor="#3678C8",
            bd=0,
            padx=2,
            pady=2,
        )
        input_frame.pack(fill="x", pady=(0, 10))

        self.message_box = tk.Text(
            input_frame,
            height=5,
            wrap="word",
            font=("TkDefaultFont", 12),
            relief="flat",
            padx=10,
            pady=10,
            undo=True,
        )
        self.message_box.pack(fill="both", expand=True)
        self.message_box.bind(
            "<FocusIn>",
            lambda event: input_frame.configure(
                highlightbackground="#3678C8"
            ),
        )
        self.message_box.bind(
            "<FocusOut>",
            lambda event: input_frame.configure(
                highlightbackground="#7A9CC6"
            ),
        )

        controls = ttk.Frame(outer)
        controls.pack(fill="x", pady=(0, 8))

        self.analyze_button = ttk.Button(
            controls,
            text="Analyze message",
            style="Analyze.TButton",
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
            outer,
            textvariable=self.status,
        ).pack(anchor="w", pady=(0, 8))

        # Scrollable results
        area = ttk.Frame(outer)
        area.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(
            area,
            highlightthickness=0,
            borderwidth=0,
        )
        scrollbar = ttk.Scrollbar(
            area,
            orient="vertical",
            command=self.canvas.yview,
        )

        self.results_frame = ttk.Frame(
            self.canvas,
            padding=(4, 4, 10, 12),
        )

        self.window_id = self.canvas.create_window(
            (0, 0),
            window=self.results_frame,
            anchor="nw",
        )
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.results_frame.bind(
            "<Configure>",
            lambda event: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            ),
        )
        self.canvas.bind(
            "<Configure>",
            lambda event: self.canvas.itemconfigure(
                self.window_id,
                width=event.width,
            ),
        )

        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Mouse-wheel scrolling on the results/cards area (macOS)
        self.canvas.bind_all("<MouseWheel>", self.on_mousewheel)
        # Linux mouse wheel support
        self.canvas.bind_all("<Button-4>", self.on_mousewheel_linux)
        self.canvas.bind_all("<Button-5>", self.on_mousewheel_linux)

        self.analysis_label = ttk.Label(
            self.results_frame,
            text="Your analysis will appear here.",
            wraplength=850,
            justify="left",
        )
        self.analysis_label.pack(fill="x", anchor="w", pady=(0, 14))

        self.cards_frame = ttk.Frame(self.results_frame)
        self.cards_frame.pack(fill="x", expand=True)

        self.render_empty_cards()
        self.root.after(100, self.check_results)

    def pointer_over_results(self, event):
        x = event.x_root
        y = event.y_root

        left = self.canvas.winfo_rootx()
        top = self.canvas.winfo_rooty()
        right = left + self.canvas.winfo_width()
        bottom = top + self.canvas.winfo_height()

        return left <= x <= right and top <= y <= bottom

    def on_mousewheel(self, event):
        if not self.pointer_over_results(event):
            return

        if event.delta == 0:
            return

        # macOS commonly uses small positive/negative delta values
        amount = -1 if event.delta > 0 else 1
        self.canvas.yview_scroll(amount, "units")

    def on_mousewheel_linux(self, event):
        if not self.pointer_over_results(event):
            return

        if event.num == 4:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self.canvas.yview_scroll(1, "units")

    def render_empty_cards(self):
        for widget in self.cards_frame.winfo_children():
            widget.destroy()

        self.reply_vars = {}

        for reply_id in ("A", "B", "C"):
            card = ttk.LabelFrame(
                self.cards_frame,
                text=f"Reply {reply_id}",
                style="Card.TLabelframe",
            )
            card.pack(fill="x", pady=6)

            tone = tk.StringVar(value="Waiting for analysis...")
            english = tk.StringVar(value="")
            translation = tk.StringVar(value="")
            when = tk.StringVar(value="")

            ttk.Label(
                card,
                textvariable=tone,
            ).pack(anchor="w")

            ttk.Label(
                card,
                textvariable=english,
                wraplength=850,
                justify="left",
                font=("TkDefaultFont", 12, "bold"),
            ).pack(fill="x", anchor="w", pady=(8, 4))

            # Persian translation directly below the English reply
            ttk.Label(
                card,
                textvariable=translation,
                wraplength=850,
                justify="left",
                foreground="#356B45",
                font=("TkDefaultFont", 11),
            ).pack(fill="x", anchor="w", pady=(0, 8))

            ttk.Label(
                card,
                textvariable=when,
                wraplength=850,
                justify="left",
            ).pack(fill="x", anchor="w")

            ttk.Button(
                card,
                text=f"Copy English reply {reply_id}",
                style="Copy.TButton",
                command=lambda rid=reply_id: self.copy_reply(rid),
            ).pack(anchor="e", pady=(8, 0))

            self.reply_vars[reply_id] = {
                "card": card,
                "tone": tone,
                "english": english,
                "translation": translation,
                "when": when,
            }

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
        self.analysis_label.configure(text="Analyzing message. Please wait...")
        self.render_empty_cards()

        threading.Thread(
            target=self.worker,
            args=(message,),
            daemon=True,
        ).start()

    def worker(self, message):
        try:
            self.results.put(("success", get_suggestions(message)))
        except urllib.error.URLError as error:
            self.results.put((
                "error",
                "Could not connect to Ollama. Check that Ollama is running.\n"
                f"{error}",
            ))
        except (KeyError, json.JSONDecodeError, ValueError) as error:
            self.results.put((
                "error",
                f"Could not parse the model response:\n{error}",
            ))
        except TimeoutError:
            self.results.put((
                "error",
                "The request timed out. Please try again.",
            ))
        except Exception as error:
            self.results.put(("error", f"Unexpected error:\n{error}"))

    def check_results(self):
        try:
            while True:
                kind, content = self.results.get_nowait()
                self.analyze_button.configure(state="normal")

                if kind == "error":
                    self.status.set("Analysis failed.")
                    self.analysis_label.configure(text=content)
                else:
                    self.status.set("Analysis complete.")
                    self.show_analysis(content)

        except queue.Empty:
            pass

        self.root.after(100, self.check_results)

    def show_analysis(self, data):
        summary = (
            "ORIGINAL MESSAGE\n"
            f"{self.message_box.get('1.0', 'end').strip()}\n\n"
            "ترجمه فارسی پیام اصلی\n"
            f"{data['meaning_fa']}\n\n"
            "درخواست صریح مدیر\n"
            f"{data['explicit_request_fa']}\n\n"
            "برداشت احتمالی\n"
            f"{data['possible_intention_fa']}\n\n"
            "موارد نامشخص\n"
            f"{data['unknowns_fa']}\n\n"
            "دلیل انتخاب پاسخ پیشنهادی\n"
            f"{data['best_reason_fa']}"
        )
        self.analysis_label.configure(text=summary)

        for reply in data["replies"]:
            rid = reply["id"]
            vars_ = self.reply_vars[rid]

            prefix = (
                "★ RECOMMENDED — "
                if rid == data["best_reply_id"]
                else ""
            )
            vars_["card"].configure(text=f"{prefix}Reply {rid}")
            vars_["tone"].set(reply["tone_fa"])
            vars_["english"].set(reply["text"])
            vars_["translation"].set(
                f"ترجمه فارسی: {reply['translation_fa']}"
            )
            vars_["when"].set(
                f"چه زمانی مناسب است؟ {reply['when_fa']}"
            )

        self.canvas.yview_moveto(0)

    def copy_reply(self, reply_id):
        text = self.reply_vars[reply_id]["english"].get().strip()

        if not text:
            return

        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.status.set(f"English reply {reply_id} copied to clipboard.")

    def clear(self):
        self.message_box.delete("1.0", "end")
        self.analysis_label.configure(
            text="Your analysis will appear here."
        )
        self.render_empty_cards()
        self.canvas.yview_moveto(0)
        self.status.set(f"Local model: {MODEL}")

    def run(self):
        self.root.mainloop()


def main():
    root = tk.Tk()
    EnglishAssistant(root).run()


if __name__ == "__main__":
    main()
