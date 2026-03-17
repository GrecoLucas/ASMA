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
            "day": 1
        }
        self.devices = {}

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
        # Main container
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Title
        title = ttk.Label(main_frame, text="🏠 Smart Home Energy Management System", style="Title.TLabel")
        title.pack(pady=(0, 15))

        # World State Panel
        self.create_world_panel(main_frame)

        # Devices Panel
        self.create_devices_panel(main_frame)

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

        # Row 3: Price
        ttk.Label(info_frame, text="💰 Energy Price:", style="Heading.TLabel").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.price_label = ttk.Label(info_frame, text="-- €/kWh", style="Value.TLabel")
        self.price_label.grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)

        ttk.Label(info_frame, text="📅 Day:", style="Heading.TLabel").grid(row=2, column=2, sticky=tk.W, padx=5, pady=5)
        self.day_label = ttk.Label(info_frame, text="--", style="Value.TLabel")
        self.day_label.grid(row=2, column=3, sticky=tk.W, padx=5, pady=5)

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
            info["status"] = ttk.Label(device_frame, text="Status: --", style="Heading.TLabel")
            info["status"].pack(anchor=tk.W, pady=2)

            info["temp"] = ttk.Label(device_frame, text="Current Temp: -- °C", style="Heading.TLabel")
            info["temp"].pack(anchor=tk.W, pady=2)

            info["target"] = ttk.Label(device_frame, text="Target Temp: -- °C", style="Heading.TLabel")
            info["target"].pack(anchor=tk.W, pady=2)

            info["comfort"] = ttk.Label(device_frame, text="Comfort: ----", style="Info.TLabel")
            info["comfort"].pack(anchor=tk.W, pady=2)

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
        season = world.get("season", "unknown").title()
        self.time_label.config(text=f"Time: {hour:02d}:00 | Season: {season}")
        self.temp_label.config(text=f"{world.get('temperature', 0):.1f} °C")
        self.solar_label.config(text=f"{world.get('solar_production', 0):.2f} kW")
        self.price_label.config(text=f"{world.get('energy_price', 0):.3f} €/kWh")
        self.day_label.config(text=f"Day {world.get('day', 0)}")

        # Update device states
        for device_name in self.state.get_all_devices():
            if device_name not in self.device_frames:
                self.add_device_frame(device_name, "air_conditioner")

            device_state = self.state.get_device_state(device_name)
            device_info = self.device_frames[device_name]

            if device_info["type"] == "air_conditioner":
                status = device_state.get("ac_status", "Unknown")
                current_temp = device_state.get("current_temp", 0)
                target_temp = device_state.get("target_temp", 0)
                temp_margin = device_state.get("temp_margin", 0)

                # Update labels
                device_info["labels"]["status"].config(
                    text=f"Status: {'🟢 ON' if status == 'ON' else '🔴 OFF'}"
                )
                device_info["labels"]["temp"].config(
                    text=f"Current Temp: {current_temp:.1f} °C"
                )
                device_info["labels"]["target"].config(
                    text=f"Target Temp: {target_temp:.1f} °C ±{temp_margin:.1f}°C"
                )

                # Calculate comfort level
                if current_temp >= target_temp - temp_margin and current_temp <= target_temp + temp_margin:
                    comfort = "✅ Comfortable"
                else:
                    comfort = "❌ Outside range"

                device_info["labels"]["comfort"].config(text=f"Comfort: {comfort}")

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
