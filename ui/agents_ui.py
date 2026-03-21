import tkinter as tk
from tkinter import ttk

class DevicesPanel:
    def __init__(self, parent):
        self.frame = ttk.LabelFrame(parent, text="Devices", padding=10)
        self.frame.pack(fill=tk.BOTH, expand=True)

        # Scrollable frame for devices
        canvas = tk.Canvas(self.frame, bg="#1e1e1e", highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.frame, orient=tk.VERTICAL, command=canvas.yview)
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
        device_frame = ttk.LabelFrame(self.devices_container, text=f"{device_name.title()}", padding=10)
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

    def update_devices(self, state):
        for device_name in state.get_all_devices():
            if device_name not in self.device_frames:
                device_state = state.get_device_state(device_name)
                device_type = device_state.get("device_type", "unknown") if device_state else "unknown"
                self.add_device_frame(device_name, device_type)

            device_state = state.get_device_state(device_name)
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
