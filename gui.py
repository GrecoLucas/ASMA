import tkinter as tk
from tkinter import ttk
import json
from threading import Lock

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
        title = ttk.Label(self.root, text="🏠 Smart Home Energy Management System", style="Title.TLabel")
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
        self.create_devices_panel(left_frame)
        
        # Logs Panel
        self.create_log_panel(right_frame)

    def create_log_panel(self, parent):
        """Create log display panel."""
        log_frame = ttk.LabelFrame(parent, text="💬 Agent Messages", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.log_text = tk.Text(log_frame, bg="#2d2d2d", fg="#00ff88", font=("Courier", 9), state=tk.DISABLED, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)

        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def create_world_panel(self, parent):
        """Create world state display panel."""
        world_frame = ttk.LabelFrame(parent, text="🌍 World State", padding=10)
        world_frame.pack(fill=tk.X, pady=(0, 15))

        # Create a grid for world info
        info_frame = ttk.Frame(world_frame)
        info_frame.pack(fill=tk.X)

        # Row 1: Time and Season
        self.time_label = ttk.Label(info_frame, text="Time: --:-- | Season: ----", style="Value.TLabel")
        self.time_label.grid(row=0, column=0, columnspan=4, sticky=tk.W, pady=5)

        # Row 2: Environmental data
        ttk.Label(info_frame, text="🌡️ Temperature:", style="Heading.TLabel").grid(row=1, column=0, sticky=tk.W, padx=5)
        self.temp_label = ttk.Label(info_frame, text="-- °C", style="Value.TLabel")
        self.temp_label.grid(row=1, column=1, sticky=tk.W, padx=5)

        ttk.Label(info_frame, text="☀️ Solar Production:", style="Heading.TLabel").grid(row=1, column=2, sticky=tk.W, padx=5)
        self.solar_label = ttk.Label(info_frame, text="-- kW", style="Value.TLabel")
        self.solar_label.grid(row=1, column=3, sticky=tk.W, padx=5)

        # Row 3: Price and day
        ttk.Label(info_frame, text="💰 Energy Price:", style="Heading.TLabel").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.price_label = ttk.Label(info_frame, text="-- €/kWh", style="Value.TLabel")
        self.price_label.grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)

        ttk.Label(info_frame, text="📅 Day:", style="Heading.TLabel").grid(row=2, column=2, sticky=tk.W, padx=5, pady=5)
        self.day_label = ttk.Label(info_frame, text="--", style="Value.TLabel")
        self.day_label.grid(row=2, column=3, sticky=tk.W, padx=5, pady=5)

        # Row 4: Energy consumption
        ttk.Label(info_frame, text="⚡ Last Hour Consumption:", style="Heading.TLabel").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.hourly_consumption_label = ttk.Label(info_frame, text="-- kWh", style="Value.TLabel")
        self.hourly_consumption_label.grid(row=3, column=1, sticky=tk.W, padx=5, pady=5)

        ttk.Label(info_frame, text="📊 Daily Total Consumption:", style="Heading.TLabel").grid(row=3, column=2, sticky=tk.W, padx=5, pady=5)
        self.daily_consumption_label = ttk.Label(info_frame, text="-- kWh", style="Value.TLabel")
        self.daily_consumption_label.grid(row=3, column=3, sticky=tk.W, padx=5, pady=5)

    def create_devices_panel(self, parent):
        """Create devices display panel."""
        devices_frame = ttk.LabelFrame(parent, text="⚙️ Devices", padding=10)
        devices_frame.pack(fill=tk.BOTH, expand=True)

        # Scrollable frame for devices
        canvas = tk.Canvas(devices_frame, bg="#1e1e1e", highlightthickness=0)
        scrollbar = ttk.Scrollbar(devices_frame, orient=tk.VERTICAL, command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        self.devices_container = scrollable_frame
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.device_frames = {}

    def add_device_frame(self, device_name, device_type):
        """Add a device display frame."""
        device_frame = ttk.LabelFrame(self.devices_container, text=f"🔧 {device_name.title()}", padding=10)
        device_frame.pack(fill=tk.X, pady=5)

        # Device info labels
        info = {}

        if device_type == "air_conditioner":
            info["priority"] = ttk.Label(device_frame, text="Priority: --", style="Info.TLabel")
            info["priority"].pack(anchor=tk.W, pady=2)

            info["status"] = ttk.Label(device_frame, text="Status: --", style="Heading.TLabel")
            info["status"].pack(anchor=tk.W, pady=2)

            info["temp"] = ttk.Label(device_frame, text="Current Temp: -- °C", style="Heading.TLabel")
            info["temp"].pack(anchor=tk.W, pady=2)

            info["target"] = ttk.Label(device_frame, text="Target Temp: -- °C", style="Heading.TLabel")
            info["target"].pack(anchor=tk.W, pady=2)

            info["power"] = ttk.Label(device_frame, text="Power: -- kW", style="Heading.TLabel")
            info["power"].pack(anchor=tk.W, pady=2)

            info["consumption"] = ttk.Label(device_frame, text="Hourly: -- kWh | Daily: -- kWh", style="Info.TLabel")
            info["consumption"].pack(anchor=tk.W, pady=2)

            info["comfort"] = ttk.Label(device_frame, text="Comfort: ----", style="Info.TLabel")
            info["comfort"].pack(anchor=tk.W, pady=2)

        elif device_type == "refrigerator":
            info["priority"] = ttk.Label(device_frame, text="Priority: --", style="Info.TLabel")
            info["priority"].pack(anchor=tk.W, pady=2)

            info["status"] = ttk.Label(device_frame, text="Compressor: --", style="Heading.TLabel")
            info["status"].pack(anchor=tk.W, pady=2)

            info["temp"] = ttk.Label(device_frame, text="Interior Temp: -- °C", style="Heading.TLabel")
            info["temp"].pack(anchor=tk.W, pady=2)

            info["target"] = ttk.Label(device_frame, text="Target Temp: -- °C", style="Heading.TLabel")
            info["target"].pack(anchor=tk.W, pady=2)

            info["power"] = ttk.Label(device_frame, text="Power: -- kW", style="Heading.TLabel")
            info["power"].pack(anchor=tk.W, pady=2)

            info["consumption"] = ttk.Label(device_frame, text="Hourly: -- kWh | Daily: -- kWh", style="Info.TLabel")
            info["consumption"].pack(anchor=tk.W, pady=2)

        self.device_frames[device_name] = {
            "frame": device_frame,
            "labels": info,
            "type": device_type
        }

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
        for device_name in self.state.get_all_devices():
            if device_name not in self.device_frames:
                device_state = self.state.get_device_state(device_name)
                device_type = device_state.get("device_type", "unknown") if device_state else "unknown"
                self.add_device_frame(device_name, device_type)

            device_state = self.state.get_device_state(device_name)
            device_info = self.device_frames[device_name]

            if device_info["type"] == "air_conditioner":
                status = device_state.get("ac_status", "Unknown")
                current_temp = device_state.get("current_temp") or 0.0
                target_temp = device_state.get("target_temp") or 0.0
                temp_margin = device_state.get("temp_margin") or 0.0
                power_kw = device_state.get("power_kw") or 0.0
                hourly_consumption_kwh = device_state.get("hourly_consumption_kwh") or 0.0
                daily_consumption_kwh = device_state.get("daily_consumption_kwh") or 0.0

                priority = device_state.get("priority", "-")

                # Update labels
                device_info["labels"]["priority"].config(text=f"Priority: {priority}")
                device_info["labels"]["status"].config(
                    text=f"Status: {'🟢 ON' if status == 'ON' else '🔴 OFF'}"
                )
                device_info["labels"]["temp"].config(
                    text=f"Current Temp: {current_temp:.1f} °C"
                )
                device_info["labels"]["target"].config(
                    text=f"Target Temp: {target_temp:.1f} °C ±{temp_margin:.1f}°C"
                )
                device_info["labels"]["power"].config(
                    text=f"Power: {power_kw:.2f} kW"
                )
                device_info["labels"]["consumption"].config(
                    text=f"Hourly: {hourly_consumption_kwh:.3f} kWh | Daily: {daily_consumption_kwh:.3f} kWh"
                )

                # Calculate comfort level
                if current_temp >= target_temp - temp_margin and current_temp <= target_temp + temp_margin:
                    comfort = "✅ Comfortable"
                else:
                    comfort = "❌ Outside range"

                device_info["labels"]["comfort"].config(text=f"Comfort: {comfort}")

            elif device_info["type"] == "refrigerator":
                status = device_state.get("compressor_status", "Unknown")
                current_temp = device_state.get("current_temp") or 0.0
                target_temp = device_state.get("target_temp") or 0.0
                temp_margin = device_state.get("temp_margin") or 0.0
                power_kw = device_state.get("power_kw") or 0.0
                hourly_consumption_kwh = device_state.get("hourly_consumption_kwh") or 0.0
                daily_consumption_kwh = device_state.get("daily_consumption_kwh") or 0.0

                priority = device_state.get("priority", "-")

                # Update labels
                device_info["labels"]["priority"].config(text=f"Priority: {priority}")
                device_info["labels"]["status"].config(
                    text=f"Compressor: {'🟢 RUNNING' if status == 'RUNNING' else '🔴 IDLE'}"
                )
                device_info["labels"]["temp"].config(
                    text=f"Interior Temp: {current_temp:.1f} °C"
                )
                device_info["labels"]["target"].config(
                    text=f"Target Temp: {target_temp:.1f} °C ±{temp_margin:.1f}°C"
                )
                device_info["labels"]["power"].config(
                    text=f"Power: {power_kw:.2f} kW"
                )
                device_info["labels"]["consumption"].config(
                    text=f"Hourly: {hourly_consumption_kwh:.3f} kWh | Daily: {daily_consumption_kwh:.3f} kWh"
                )

        # Update logs
        messages = self.state.get_messages()
        if hasattr(self, 'log_text'):
            self.log_text.config(state=tk.NORMAL)
            self.log_text.delete(1.0, tk.END)
            self.log_text.insert(tk.END, "\n".join(messages))
            self.log_text.see(tk.END)
            self.log_text.config(state=tk.DISABLED)

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
