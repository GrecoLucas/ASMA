import tkinter as tk
from tkinter import ttk

class LogPanel:
    def __init__(self, parent):
        self.frame = ttk.LabelFrame(parent, text="Agent Messages", padding=10)
        self.frame.pack(fill=tk.BOTH, expand=True)

        self.log_text = tk.Text(self.frame, bg="#2d2d2d", fg="#b0f7ff", font=("Courier", 9), state=tk.DISABLED, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(self.frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)

        # Message semantic colors
        self.log_text.tag_configure("request", foreground="#ffd94a")
        self.log_text.tag_configure("accept", foreground="#33ff88")
        self.log_text.tag_configure("reject", foreground="#ff4d4d")
        self.log_text.tag_configure("default", foreground="#b0f7ff")

        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _line_tag(self, line):
        text = line.upper()
        if "REPLY REJECT" in text or "ABORT" in text or "SHED" in text:
            return "reject"
        if "REPLY ACCEPT" in text or "CONSENSUS REACHED" in text:
            return "accept"
        if "[REQUEST" in text or "REQUESTS POWER" in text:
            return "request"
        return "default"

    def update_logs(self, messages):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        for line in messages:
            self.log_text.insert(tk.END, f"{line}\n", self._line_tag(line))
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
