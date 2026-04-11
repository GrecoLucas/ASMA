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
        self.current_col = 0
        self.current_row = 0

    def add_device_frame(self, device_name, device_type):
        """Add a device display frame."""
        device_frame = ttk.LabelFrame(self.devices_container, text=f"{device_name.title()}", padding=10)
        device_frame.grid(row=self.current_row, column=self.current_col, padx=10, pady=10, sticky="nsew")
        
        self.current_col += 1
        if self.current_col > 2: # 3 items per row
            self.current_col = 0
            self.current_row += 1

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

        elif device_type == "washing_machine":
            info["priority"] = ttk.Label(device_frame, text="Priority: --", style="Info.TLabel")
            info["priority"].pack(anchor=tk.W, pady=2)

            info["motor_status"] = ttk.Label(device_frame, text="Motor: --", style="Heading.TLabel")
            info["motor_status"].pack(anchor=tk.W, pady=2)

            info["pending_clothes"] = ttk.Label(device_frame, text="Pending Clothes: --", style="Heading.TLabel")
            info["pending_clothes"].pack(anchor=tk.W, pady=2)

            info["wash_cycles"] = ttk.Label(device_frame, text="Wash Cycles Remaining: --", style="Heading.TLabel")
            info["wash_cycles"].pack(anchor=tk.W, pady=2)

            info["power"] = ttk.Label(device_frame, text="Power: -- kW", style="Heading.TLabel")
            info["power"].pack(anchor=tk.W, pady=2)

            info["consumption"] = ttk.Label(device_frame, text="Hourly: -- kWh | Daily: -- kWh", style="Info.TLabel")
            info["consumption"].pack(anchor=tk.W, pady=2)

        elif device_type == "dish_washer":
            info["priority"] = ttk.Label(device_frame, text="Priority: --", style="Info.TLabel")
            info["priority"].pack(anchor=tk.W, pady=2)

            info["motor_status"] = ttk.Label(device_frame, text="Motor: --", style="Heading.TLabel")
            info["motor_status"].pack(anchor=tk.W, pady=2)

            info["pending_dishes"] = ttk.Label(device_frame, text="Pending Dishes: --", style="Heading.TLabel")
            info["pending_dishes"].pack(anchor=tk.W, pady=2)

            info["wash_cycles"] = ttk.Label(device_frame, text="Wash Cycles Remaining: --", style="Heading.TLabel")
            info["wash_cycles"].pack(anchor=tk.W, pady=2)

            info["power"] = ttk.Label(device_frame, text="Power: -- kW", style="Heading.TLabel")
            info["power"].pack(anchor=tk.W, pady=2)

            info["consumption"] = ttk.Label(device_frame, text="Hourly: -- kWh | Daily: -- kWh", style="Info.TLabel")
            info["consumption"].pack(anchor=tk.W, pady=2)

        elif device_type == "battery":
            info["priority"] = ttk.Label(device_frame, text="Priority: --", style="Info.TLabel")
            info["priority"].pack(anchor=tk.W, pady=2)

            info["status"] = ttk.Label(device_frame, text="Status: --", style="Heading.TLabel")
            info["status"].pack(anchor=tk.W, pady=2)

            info["charge"] = ttk.Label(device_frame, text="Charge: -- / -- kWh (--%)", style="Heading.TLabel")
            info["charge"].pack(anchor=tk.W, pady=2)

            info["power"] = ttk.Label(device_frame, text="Power Flow: -- kW", style="Heading.TLabel")
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
                max_power_kw = device_state.get("max_power_kw") or 0.0
                hourly_consumption_kwh = device_state.get("hourly_consumption_kwh") or 0.0
                daily_consumption_kwh = device_state.get("daily_consumption_kwh") or 0.0

                priority = device_state.get("priority", "-")

                # Update labels
                device_info["labels"]["priority"].config(text=f"Priority: {priority}")

                # Status with color coding
                if status == 'ON':
                    status_text = "Status: ON"
                    status_color = "#00ff88"  # Green
                else:
                    status_text = "Status: OFF"
                    status_color = "#ff3333"  # Red
                device_info["labels"]["status"].config(text=status_text, foreground=status_color)
                device_info["labels"]["temp"].config(
                    text=f"Current Temp: {current_temp:.1f} °C"
                )
                device_info["labels"]["target"].config(
                    text=f"Target Temp: {target_temp:.1f} °C ±{temp_margin:.1f}°C"
                )
                device_info["labels"]["power"].config(
                    text=f"Power: {power_kw:.2f} kW / {max_power_kw:.2f} kW"
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
                max_power_kw = device_state.get("max_power_kw") or 0.0
                hourly_consumption_kwh = device_state.get("hourly_consumption_kwh") or 0.0
                daily_consumption_kwh = device_state.get("daily_consumption_kwh") or 0.0

                priority = device_state.get("priority", "-")

                # Update labels
                device_info["labels"]["priority"].config(text=f"Priority: {priority}")

                # Status with color coding
                if status == 'RUNNING':
                    status_text = "Status: ON"
                    status_color = "#00ff88"  # Green
                else:
                    status_text = "Status: OFF"
                    status_color = "#ff3333"  # Red
                device_info["labels"]["status"].config(text=status_text, foreground=status_color)
                device_info["labels"]["temp"].config(
                    text=f"Interior Temp: {current_temp:.1f} °C"
                )
                device_info["labels"]["target"].config(
                    text=f"Target Temp: {target_temp:.1f} °C ±{temp_margin:.1f}°C"
                )
                device_info["labels"]["power"].config(
                    text=f"Power: {power_kw:.2f} kW / {max_power_kw:.2f} kW"
                )
                device_info["labels"]["consumption"].config(
                    text=f"Hourly: {hourly_consumption_kwh:.3f} kWh | Daily: {daily_consumption_kwh:.3f} kWh"
                )
            elif device_info["type"] == "washing_machine":
                motor_status = device_state.get("motor_status", "Unknown")
                pending_clothes = device_state.get("pending_clothes", 0)
                wash_cycles_remaining = device_state.get("cycle_steps_remaining", 0)
                power_kw = device_state.get("power_kw", 0.0)
                max_power_kw = device_state.get("max_power_kw", 0.0)
                hourly_consumption_kwh = device_state.get("hourly_consumption_kwh", 0.0)
                daily_consumption_kwh = device_state.get("daily_consumption_kwh", 0.0)

                priority = device_state.get("priority", "-")

                # Update labels
                device_info["labels"]["priority"].config(text=f"Priority: {priority}")

                # Motor status with color coding
                if motor_status == 'WASHING':
                    motor_text = "Motor: ON"
                    motor_color = "#00ff88"  # Green
                else:
                    motor_text = "Motor: OFF"
                    motor_color = "#ff3333"  # Red
                device_info["labels"]["motor_status"].config(text=motor_text, foreground=motor_color)
                device_info["labels"]["pending_clothes"].config(
                    text=f"Pending Clothes: {pending_clothes}"
                )
                device_info["labels"]["wash_cycles"].config(
                    text=f"Wash Cycles Remaining: {wash_cycles_remaining}"
                )
                device_info["labels"]["power"].config(
                    text=f"Power: {power_kw:.2f} kW / {max_power_kw:.2f} kW"
                )
                device_info["labels"]["consumption"].config(
                    text=f"Hourly: {hourly_consumption_kwh:.3f} kWh | Daily: {daily_consumption_kwh:.3f} kWh"
                )

            elif device_info["type"] == "battery":
                status = device_state.get("status", "IDLE")
                power_kw = device_state.get("power_kw", 0.0)
                battery_flow = device_state.get("battery_flow_kw", power_kw)
                charge = device_state.get("charge_kwh", 0.0)
                capacity = device_state.get("capacity_kwh", 0.0)
                pct = device_state.get("charge_percent", 0.0)
                hourly_consumption_kwh = device_state.get("hourly_consumption_kwh", 0.0)
                daily_consumption_kwh = device_state.get("daily_consumption_kwh", 0.0)
                
                device_info["labels"]["priority"].config(text="Priority: 5")
                
                if "CHARGING & DISCHARGING" in status: status_color = "#00ff88"
                elif status == "CHARGING": status_color = "#00ff88"
                elif status == "DISCHARGING": status_color = "#ffb347"
                else: status_color = "#00d4ff" if status == "FULL" else "#b0b0b0"
                
                device_info["labels"]["status"].config(text=f"Status: {status}", foreground=status_color)
                
                flow = "IDLE"
                if "CHARGING & DISCHARGING" in status:
                    # In this state, battery_flow > 0 means net charge, < 0 means net discharge
                    if battery_flow > 0.01: flow = f"NET CHARGE at {battery_flow:.2f} kW"
                    elif battery_flow < -0.01: flow = f"NET DISCHARGE at {abs(battery_flow):.2f} kW"
                    else: flow = "NET ZERO (Equal Chg/Dis)"
                elif battery_flow > 0.01: flow = f"CHARGING at {battery_flow:.2f} kW"
                elif battery_flow < -0.01: flow = f"DISCHARGING at {abs(battery_flow):.2f} kW"
                
                device_info["labels"]["power"].config(text=f"Battery Flow: {flow}")
                
                device_info["labels"]["charge"].config(text=f"Charge: {charge:.2f} / {capacity:.2f} kWh ({pct:.0f}%)")
                device_info["labels"]["consumption"].config(text=f"Hourly: {hourly_consumption_kwh:.3f} kWh | Daily: {daily_consumption_kwh:.3f} kWh")

