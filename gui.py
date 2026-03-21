import tkinter as tk
from tkinter import ttk
import json
from threading import Lock
from ui.log_ui import LogPanel
from ui.agents_ui import DevicesPanel

class SimulationState:
    """Thread-safe storage for simulation state."""
    def __init__(self):
        self.lock = Lock()
        self.world_state = {
            "hour": 0,
            "temperature": 0,
            "solar_production": 0,
            "energy_price": 0,
            "season": "winter",
            "day": 1,
            "hourly_consumption_total_kwh": 0,
            "daily_consumption_total_kwh": 0,
        }
        self.devices = {}
        self.messages = []

    def update_world_state(self, state):
        with self.lock:
            self.world_state = state.copy()

    def update_device_state(self, device_name, state_data):
        with self.lock:
            self.devices[device_name] = state_data

    def get_world_state(self):
        with self.lock:
            return self.world_state.copy()

    def get_device_state(self, device_name):
        with self.lock:
            return self.devices.get(device_name, {}).copy() if device_name in self.devices else {}

    def get_all_devices(self):
        with self.lock:
            return list(self.devices.keys())

    def add_message(self, sender, receiver, content):
        with self.lock:
            from datetime import datetime
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.messages.append(f"[{timestamp}] {sender} -> {receiver}: {content}")
            if len(self.messages) > 100:
                self.messages.pop(0)

    def get_messages(self):
        with self.lock:
            return self.messages.copy()


class SimulationGUI:
    def __init__(self, root, state):
        self.root = root
        self.state = state
        self.root.title("ASMA - Smart Home Energy Management System")
        self.root.geometry("900x600")
        self.root.configure(bg="#1e1e1e")

        # Configure styles
        self.setup_styles()

        # Create main frames
        self.create_widgets()

        # Start updating display
        self.update_display()

    def setup_styles(self):
        """Configure custom styles."""
        style = ttk.Style()
        style.theme_use("clam")

        # Dark theme
        style.configure("TFrame", background="#1e1e1e")
        style.configure("TLabel", background="#1e1e1e", foreground="#e0e0e0")
        style.configure("TLabelframe", background="#1e1e1e", foreground="#e0e0e0")
        style.configure("TLabelframe.Label", background="#1e1e1e", foreground="#00d4ff")

        # Title style
        style.configure("Title.TLabel", background="#1e1e1e", foreground="#00d4ff", font=("Arial", 16, "bold"))
        style.configure("Heading.TLabel", background="#1e1e1e", foreground="#ffffff", font=("Arial", 11, "bold"))
        style.configure("Value.TLabel", background="#1e1e1e", foreground="#00ff88", font=("Courier", 12, "bold"))
        style.configure("Info.TLabel", background="#1e1e1e", foreground="#b0b0b0", font=("Arial", 10))

    def create_widgets(self):
        """Create main GUI widgets."""
        # Title outside the paned window
        title = ttk.Label(self.root, text="Smart Home Energy Management System", style="Title.TLabel")
        title.pack(pady=10)

        # PanedWindow for Left/Right separation
        paned = tk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # Left Frame
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, minsize=400)

        # Right Frame (Logs)
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, minsize=350)

        # World State Panel
        self.create_world_panel(left_frame)

        # Devices Panel
        self.devices_panel = DevicesPanel(left_frame)
        
        # Logs Panel
        self.log_panel = LogPanel(right_frame)

    def create_world_panel(self, parent):
        """Create world state display panel."""
        world_frame = ttk.LabelFrame(parent, text="World State", padding=10)
        world_frame.pack(fill=tk.X, pady=(0, 15))

        # Create a grid for world info
        info_frame = ttk.Frame(world_frame)
        info_frame.pack(fill=tk.X)

        # Row 1: Time and Season
        self.time_label = ttk.Label(info_frame, text="Time: --:-- | Season: ----", style="Value.TLabel")
        self.time_label.grid(row=0, column=0, columnspan=4, sticky=tk.W, pady=5)

        # Row 2: Environmental data
        ttk.Label(info_frame, text="Temperature:", style="Heading.TLabel").grid(row=1, column=0, sticky=tk.W, padx=5)
        self.temp_label = ttk.Label(info_frame, text="-- °C", style="Value.TLabel")
        self.temp_label.grid(row=1, column=1, sticky=tk.W, padx=5)

        ttk.Label(info_frame, text="Solar Production:", style="Heading.TLabel").grid(row=1, column=2, sticky=tk.W, padx=5)
        self.solar_label = ttk.Label(info_frame, text="-- kW", style="Value.TLabel")
        self.solar_label.grid(row=1, column=3, sticky=tk.W, padx=5)

        # Row 3: Price and day
        ttk.Label(info_frame, text="Energy Price:", style="Heading.TLabel").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.price_label = ttk.Label(info_frame, text="-- €/kWh", style="Value.TLabel")
        self.price_label.grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)

        ttk.Label(info_frame, text="Day:", style="Heading.TLabel").grid(row=2, column=2, sticky=tk.W, padx=5, pady=5)
        self.day_label = ttk.Label(info_frame, text="--", style="Value.TLabel")
        self.day_label.grid(row=2, column=3, sticky=tk.W, padx=5, pady=5)

        # Row 4: Energy consumption
        ttk.Label(info_frame, text="Last Hour Consumption:", style="Heading.TLabel").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.hourly_consumption_label = ttk.Label(info_frame, text="-- kWh", style="Value.TLabel")
        self.hourly_consumption_label.grid(row=3, column=1, sticky=tk.W, padx=5, pady=5)

        ttk.Label(info_frame, text="Daily Total Consumption:", style="Heading.TLabel").grid(row=3, column=2, sticky=tk.W, padx=5, pady=5)
        self.daily_consumption_label = ttk.Label(info_frame, text="-- kWh", style="Value.TLabel")
        self.daily_consumption_label.grid(row=3, column=3, sticky=tk.W, padx=5, pady=5)



    def update_display(self):
        """Update the GUI with current state data."""
        # Update world state
        world = self.state.get_world_state()

        hour = world.get("hour", 0)
        minute = world.get("minute", 0)
        season = world.get("season", "unknown").title()
        self.time_label.config(text=f"Time: {hour:02d}:{minute:02d} | Season: {season}")
        self.temp_label.config(text=f"{world.get('temperature') or 0.0:.1f} °C")
        self.solar_label.config(text=f"{world.get('solar_production') or 0.0:.2f} kW")
        self.price_label.config(text=f"{world.get('energy_price') or 0.0:.3f} €/kWh")
        self.day_label.config(text=f"Day {world.get('day') or 0}")
        self.hourly_consumption_label.config(text=f"{world.get('hourly_consumption_total_kwh') or 0.0:.3f} kWh")
        self.daily_consumption_label.config(text=f"{world.get('daily_consumption_total_kwh') or 0.0:.3f} kWh")

        # Update device states
        self.devices_panel.update_devices(self.state)

        # Update logs
        messages = self.state.get_messages()
        if hasattr(self, 'log_panel'):
            self.log_panel.update_logs(messages)

        # Schedule next update
        self.root.after(1000, self.update_display)


# Global state object
simulation_state = SimulationState()


def get_simulation_state():
    """Get the global simulation state."""
    return simulation_state


def start_gui():
    """Start the GUI."""
    root = tk.Tk()
    gui = SimulationGUI(root, simulation_state)
    root.mainloop()


if __name__ == "__main__":
    start_gui()
