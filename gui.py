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
        self.is_paused = False

    def toggle_pause(self):
        with self.lock:
            self.is_paused = not self.is_paused

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
            hour = self.world_state.get("hour", 0)
            minute = self.world_state.get("minute", 0)
            sim_time = f"[{hour:02d}:{minute:02d}]"
            
            if self.messages and isinstance(self.messages[-1], dict):
                last = self.messages[-1]
                if last['sender'] == sender and last['content'] == content and last['time'] == sim_time:
                    if receiver not in last['receivers']:
                        last['receivers'].append(receiver)
                    return
            
            msg = {'time': sim_time, 'sender': sender, 'receivers': [receiver], 'content': content}
            self.messages.append(msg)
            if len(self.messages) > 100:
                self.messages.pop(0)

    def get_messages(self):
        with self.lock:
            formatted = []
            for m in self.messages:
                if isinstance(m, dict):
                    receivers = ", ".join(m['receivers'])
                    formatted.append(f"{m['time']} {m['sender']} -> {receivers}: {m['content']}")
                else:
                    formatted.append(m)
            return formatted


class SimulationGUI:
    def __init__(self, root, state):
        self.root = root
        self.state = state
        self.root.title("ASMA - Smart Home Energy Management System")
        self.root.geometry("1500x750")
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
        
        # Header frame with title and controls
        header_frame = ttk.Frame(self.root)
        header_frame.pack(fill=tk.X, padx=10, pady=5)
        
        title = ttk.Label(header_frame, text="Smart Home Energy Management System", style="Title.TLabel")
        title.pack(side=tk.LEFT, pady=5)
        
        # Play/Pause button
        self.pause_btn = ttk.Button(header_frame, text="⏸ Pause", command=self.toggle_pause)
        self.pause_btn.pack(side=tk.RIGHT, pady=5)

        # Top Frame (World State)
        top_frame = ttk.Frame(self.root)
        top_frame.pack(fill=tk.X, padx=10, pady=(0, 5))
        self.create_world_panel(top_frame)

        # Main content: PanedWindow for Devices (left) and Logs (right)
        paned = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, sashwidth=5, bg="#2d2d2d")
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # Left Frame (Devices) - Larger
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, minsize=700, width=900)

        # Right Frame (Logs) - Narrower
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, minsize=300, width=500)

        # Devices Panel
        self.devices_panel = DevicesPanel(left_frame)
        
        # Logs Panel
        self.log_panel = LogPanel(right_frame)

    def toggle_pause(self):
        self.state.toggle_pause()
        if self.state.is_paused:
            self.pause_btn.config(text="▶ Play")
        else:
            self.pause_btn.config(text="⏸ Pause")

    def create_world_panel(self, parent):
        """Create world state display panel."""
        world_frame = ttk.LabelFrame(parent, text="World State", padding=10)
        world_frame.pack(fill=tk.X)

        # Create a grid for world info
        info_frame = ttk.Frame(world_frame)
        info_frame.pack(fill=tk.X)

        # Row 1: Time, Season, Temp, Solar, Price, Day
        self.time_label = ttk.Label(info_frame, text="Time: --:-- | Season: ----", style="Value.TLabel")
        self.time_label.grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=2)

        ttk.Label(info_frame, text="Temp:", style="Heading.TLabel").grid(row=0, column=2, sticky=tk.W, padx=5)
        self.temp_label = ttk.Label(info_frame, text="-- °C", style="Value.TLabel")
        self.temp_label.grid(row=0, column=3, sticky=tk.W, padx=5)

        ttk.Label(info_frame, text="Solar:", style="Heading.TLabel").grid(row=0, column=4, sticky=tk.W, padx=5)
        self.solar_label = ttk.Label(info_frame, text="-- kW", style="Value.TLabel")
        self.solar_label.grid(row=0, column=5, sticky=tk.W, padx=5)

        ttk.Label(info_frame, text="Price:", style="Heading.TLabel").grid(row=0, column=6, sticky=tk.W, padx=5)
        self.price_label = ttk.Label(info_frame, text="-- €/kWh", style="Value.TLabel")
        self.price_label.grid(row=0, column=7, sticky=tk.W, padx=5)
        
        ttk.Label(info_frame, text="Day:", style="Heading.TLabel").grid(row=0, column=8, sticky=tk.W, padx=5)
        self.day_label = ttk.Label(info_frame, text="--", style="Value.TLabel")
        self.day_label.grid(row=0, column=9, sticky=tk.W, padx=5)

        # Row 2: Consumptions, Costs, renewable, power usage
        ttk.Label(info_frame, text="Last Hour Cons:", style="Heading.TLabel").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        self.hourly_consumption_label = ttk.Label(info_frame, text="-- kWh", style="Value.TLabel")
        self.hourly_consumption_label.grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)

        ttk.Label(info_frame, text="Daily Cons:", style="Heading.TLabel").grid(row=1, column=2, sticky=tk.W, padx=5, pady=2)
        self.daily_consumption_label = ttk.Label(info_frame, text="-- kWh", style="Value.TLabel")
        self.daily_consumption_label.grid(row=1, column=3, sticky=tk.W, padx=5, pady=2)

        ttk.Label(info_frame, text="Daily Grid Cost:", style="Heading.TLabel").grid(row=1, column=4, sticky=tk.W, padx=5, pady=2)
        self.cost_label = ttk.Label(info_frame, text="-- €", style="Value.TLabel")
        self.cost_label.grid(row=1, column=5, sticky=tk.W, padx=5, pady=2)

        ttk.Label(info_frame, text="Renewable Share:", style="Heading.TLabel").grid(row=1, column=6, sticky=tk.W, padx=5, pady=2)
        self.renewable_label = ttk.Label(info_frame, text="-- %", style="Value.TLabel")
        self.renewable_label.grid(row=1, column=7, sticky=tk.W, padx=5, pady=2)

        ttk.Label(info_frame, text="Net Power:", style="Heading.TLabel").grid(row=1, column=8, sticky=tk.W, padx=5, pady=2)
        self.power_usage_label = ttk.Label(info_frame, text="-- kW / 7.00 kW", style="Value.TLabel")
        self.power_usage_label.grid(row=1, column=9, sticky=tk.W, padx=5, pady=2)



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
        self.cost_label.config(text=f"{world.get('daily_cost_euro') or 0.0:.3f} €", foreground="#ffb347")
        
        # Calculate renewable percentage (capped at 100%)
        total_kwh = world.get('daily_consumption_total_kwh') or 0.0
        renewable_kwh = world.get('daily_renewable_kwh') or 0.0
        pct = (renewable_kwh / total_kwh * 100) if total_kwh > 0 else 0.0
        pct = min(pct, 100.0)  # Cap at 100%
        self.renewable_label.config(text=f"{pct:.1f} %", foreground="#00ff88")

        # Calculate current total power consumption from all devices
        from config import MAX_POWER_KW
        total_power = 0.0
        device_names = self.state.get_all_devices()
        for device_name in device_names:
            device_state = self.state.get_device_state(device_name)
            total_power += device_state.get("power_kw", 0.0)

        # Update power usage display with color coding
        # For Net power, it can be negative (injecting to grid).
        power_percentage = (total_power / MAX_POWER_KW) * 100 if MAX_POWER_KW > 0 else 0
        if total_power < 0:
            power_color = "#00d4ff" # Blue - injecting
        elif power_percentage >= 100:
            power_color = "#ff3333"  # Red - at or over limit
        elif power_percentage >= 85:
            power_color = "#ff9900"  # Orange - warning
        elif power_percentage >= 70:
            power_color = "#ffcc00"  # Yellow - caution
        else:
            power_color = "#00ff88"  # Green - normal

        self.power_usage_label.config(
            text=f"{total_power:.2f} kW / {MAX_POWER_KW:.2f} kW",
            foreground=power_color
        )

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
