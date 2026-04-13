import tkinter as tk
from tkinter import ttk

class LogPanel:
    def __init__(self, parent):
        self.frame = ttk.LabelFrame(parent, text="Negotiations Log", padding=10)
        self.frame.pack(fill=tk.BOTH, expand=True)

        # Create text widget with improved font size and wrapping
        self.log_text = tk.Text(
            self.frame, 
            bg="#2d2d2d", 
            fg="#b0f7ff", 
            font=("Consolas", 9), 
            state=tk.DISABLED, 
            wrap=tk.WORD,
            spacing1=2,  # Space before lines
            spacing3=2   # Space after lines
        )
        scrollbar = ttk.Scrollbar(self.frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)

        # Enhanced message semantic colors and formatting
        self.log_text.tag_configure("time", foreground="#666666", font=("Consolas", 8))
        self.log_text.tag_configure("sender", foreground="#00d4ff", font=("Consolas", 9, "bold"))
        self.log_text.tag_configure("receiver", foreground="#8a8aff", font=("Consolas", 9))
        self.log_text.tag_configure("request", foreground="#ffd94a", font=("Consolas", 9))
        self.log_text.tag_configure("accept", foreground="#33ff88", font=("Consolas", 9, "bold"))
        self.log_text.tag_configure("accept_limit", foreground="#33ff88", font=("Consolas", 9, "bold"))
        self.log_text.tag_configure("accept_shed", foreground="#ffcc66", font=("Consolas", 9, "bold"))
        self.log_text.tag_configure("reject", foreground="#ff4d4d", font=("Consolas", 9, "bold"))
        self.log_text.tag_configure("info", foreground="#b0f7ff", font=("Consolas", 9))
        self.log_text.tag_configure("consensus", foreground="#00ff88", font=("Consolas", 9, "bold"))
        self.log_text.tag_configure("commit_no_shed", foreground="#00ff88", font=("Consolas", 9, "bold"))
        self.log_text.tag_configure("commit_with_shed", foreground="#66d9ff", font=("Consolas", 9, "bold"))
        self.log_text.tag_configure("abort", foreground="#ff6666", font=("Consolas", 9, "bold"))
        self.log_text.tag_configure("details", foreground="#9d9dff", font=("Consolas", 8, "italic"))
        self.log_text.tag_configure("separator", foreground="#444444")

        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.last_hour = None

    def _parse_and_format_message(self, line):
        """Parse message and return formatted components with tags."""
        parts = []
        
        # Extract time [HH:MM]
        if line.startswith("["):
            time_end = line.find("]")
            if time_end != -1:
                time_str = line[:time_end+1]
                rest = line[time_end+1:].strip()
                parts.append((time_str + " ", "time"))
                
                # Parse sender -> receiver: content
                if " -> " in rest:
                    arrow_pos = rest.find(" -> ")
                    sender = rest[:arrow_pos].strip()
                    after_arrow = rest[arrow_pos+4:]
                    
                    # Find receiver (before colon)
                    colon_pos = after_arrow.find(":")
                    if colon_pos != -1:
                        receiver = after_arrow[:colon_pos].strip()
                        content = after_arrow[colon_pos+1:].strip()
                        
                        parts.append((sender, "sender"))
                        parts.append((" → ", "info"))
                        parts.append((receiver, "receiver"))
                        parts.append((": ", "info"))
                        
                        # Determine content tag based on message type
                        content_upper = content.upper()
                        if "✓ ON [NO SHED]" in content_upper:
                            parts.append((content, "commit_no_shed"))
                        elif "✓ ON [SHED" in content_upper:
                            parts.append((content, "commit_with_shed"))
                        elif "✓" in content or "CONSENSUS REACHED" in content_upper:
                            parts.append((content, "consensus"))
                        elif "✗" in content or "ABORT" in content_upper:
                            parts.append((content, "abort"))
                        elif "ACCEPTS [LIMIT]" in content_upper:
                            parts.append((content, "accept_limit"))
                        elif "ACCEPTS [SHED" in content_upper:
                            parts.append((content, "accept_shed"))
                        elif "ACCEPTS" in content_upper:
                            parts.append((content, "accept"))
                        elif "REJECTS" in content_upper:
                            parts.append((content, "reject"))
                        elif "REQUESTS" in content_upper or "KW" in content_upper:
                            # Parse out details for special formatting
                            if "(" in content and ")" in content:
                                main_part = content[:content.index("(")]
                                detail_part = content[content.index("("):]
                                parts.append((main_part, "request"))
                                parts.append((detail_part, "details"))
                            else:
                                parts.append((content, "request"))
                        else:
                            parts.append((content, "info"))
                    else:
                        parts.append((after_arrow, "info"))
                else:
                    parts.append((rest, "info"))
            else:
                parts.append((line, "info"))
        else:
            parts.append((line, "info"))
        
        return parts

    def update_logs(self, messages):
        """Update log display with enhanced formatting."""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        
        current_hour = None
        for line in messages:
            # Extract hour for separator
            if line.startswith("["):
                time_end = line.find("]")
                if time_end != -1:
                    time_str = line[1:time_end]
                    hour = time_str.split(":")[0] if ":" in time_str else None
                    
                    # Add separator when hour changes
                    if hour and hour != current_hour:
                        if current_hour is not None:
                            self.log_text.insert(tk.END, "─" * 60 + "\n", "separator")
                        current_hour = hour
            
            # Parse and insert formatted message
            parts = self._parse_and_format_message(line)
            for text, tag in parts:
                self.log_text.insert(tk.END, text, tag)
            self.log_text.insert(tk.END, "\n")
        
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
