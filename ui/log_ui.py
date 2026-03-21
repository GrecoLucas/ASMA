import tkinter as tk
from tkinter import ttk

class LogPanel:
    def __init__(self, parent):
        self.frame = ttk.LabelFrame(parent, text="Agent Messages", padding=10)
        self.frame.pack(fill=tk.BOTH, expand=True)

        self.log_text = tk.Text(self.frame, bg="#2d2d2d", fg="#00ff88", font=("Courier", 9), state=tk.DISABLED, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(self.frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)

        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def update_logs(self, messages):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.insert(tk.END, "\n".join(messages))
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
