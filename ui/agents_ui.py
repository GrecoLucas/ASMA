import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk

class DevicesPanel:
    def __init__(self, parent):
        self.frame = ttk.LabelFrame(parent, text="Devices", padding=10)
        self.frame.pack(fill=tk.BOTH, expand=True)

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

        self.cog_frames = []
        try:
            cog_image = Image.open('ui/cog.gif')
            while True:
                frame = cog_image.convert('RGBA').resize((40, 40), Image.LANCZOS)
                self.cog_frames.append(ImageTk.PhotoImage(frame))
                cog_image.seek(cog_image.tell() + 1)
        except EOFError:
            pass

    def add_device_frame(self, device_name, device_type):
        device_frame = ttk.LabelFrame(self.devices_container, text=f"{device_name.title()}", padding=10)
        device_frame.grid(row=self.current_row, column=self.current_col, padx=10, pady=10, sticky="nsew")

        self.current_col += 1
        if self.current_col > 2:
            self.current_col = 0
            self.current_row += 1

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

        elif device_type == "heater":
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
            info["status"] = ttk.Label(device_frame, text="State: --", style="Heading.TLabel")
            info["status"].pack(anchor=tk.W, pady=2)
            info["level"] = ttk.Label(device_frame, text="Charge Level: -- %", style="Heading.TLabel")
            info["level"].pack(anchor=tk.W, pady=2)
            info["power_provided"] = ttk.Label(device_frame, text="Provided to House: -- kW", style="Heading.TLabel")
            info["power_provided"].pack(anchor=tk.W, pady=2)
            info["solar_charge"] = ttk.Label(device_frame, text="Solar Charge: -- kW", style="Heading.TLabel")
            info["solar_charge"].pack(anchor=tk.W, pady=2)

        elif device_type == "air_fryer":
            info["priority"] = ttk.Label(device_frame, text="Priority: --", style="Info.TLabel")
            info["priority"].pack(anchor=tk.W, pady=2)
            info["status"] = ttk.Label(device_frame, text="Status: --", style="Heading.TLabel")
            info["status"].pack(anchor=tk.W, pady=2)
            info["timer"] = ttk.Label(device_frame, text="Remaining: -- min", style="Heading.TLabel")
            info["timer"].pack(anchor=tk.W, pady=2)
            info["power"] = ttk.Label(device_frame, text="Power: -- kW", style="Heading.TLabel")
            info["power"].pack(anchor=tk.W, pady=2)
            info["consumption"] = ttk.Label(device_frame, text="Hourly: -- kWh | Daily: -- kWh", style="Info.TLabel")
            info["consumption"].pack(anchor=tk.W, pady=2)



        # GIF pinned to the top-right corner of the LabelFrame.
        # x=-5, y=20 nudges it just inside the border and below the title text.
        animation_label = tk.Label(device_frame, bg="#1e1e1e", bd=0, highlightthickness=0)
        animation_label.place(relx=1.0, rely=0.0, anchor="ne", x=-5, y=0)

        self.device_frames[device_name] = {
            "frame": device_frame,
            "labels": info,
            "type": device_type,
            "animation_label": animation_label,
            "animating": False,
            "current_image": None
        }

    def start_animation(self, label, device_name):
        def animate(frame=0):
            if self.device_frames[device_name]['animating']:
                photo = self.cog_frames[frame]
                self.device_frames[device_name]['current_image'] = photo
                label.config(image=photo)
                label.image = photo
                label.after(100, animate, (frame + 1) % len(self.cog_frames))
        animate()

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

                device_info["labels"]["priority"].config(text=f"Priority: {priority}")
                if status == 'ON':
                    status_text, status_color = "Status: ON", "#00ff88"
                else:
                    status_text, status_color = "Status: OFF", "#ff3333"
                device_info["labels"]["status"].config(text=status_text, foreground=status_color)
                device_info["labels"]["temp"].config(text=f"Current Temp: {current_temp:.1f} °C")
                device_info["labels"]["target"].config(text=f"Target Temp: {target_temp:.1f} °C ±{temp_margin:.1f}°C")
                device_info["labels"]["power"].config(text=f"Power: {power_kw:.2f} kW / {max_power_kw:.2f} kW")
                device_info["labels"]["consumption"].config(text=f"Hourly: {hourly_consumption_kwh:.3f} kWh | Daily: {daily_consumption_kwh:.3f} kWh")
                comfort = "✅ Comfortable" if target_temp - temp_margin <= current_temp <= target_temp + temp_margin else "❌ Outside range"
                device_info["labels"]["comfort"].config(text=f"Comfort: {comfort}")
                is_on = status == 'ON'

            elif device_info["type"] == "heater":
                status = device_state.get("heater_status", "Unknown")
                current_temp = device_state.get("current_temp") or 0.0
                target_temp = device_state.get("target_temp") or 0.0
                temp_margin = device_state.get("temp_margin") or 0.0
                power_kw = device_state.get("power_kw") or 0.0
                max_power_kw = device_state.get("max_power_kw") or 0.0
                hourly_consumption_kwh = device_state.get("hourly_consumption_kwh") or 0.0
                daily_consumption_kwh = device_state.get("daily_consumption_kwh") or 0.0
                priority = device_state.get("priority", "-")

                device_info["labels"]["priority"].config(text=f"Priority: {priority}")
                if status == 'ON':
                    status_text, status_color = "Status: ON", "#00ff88"
                else:
                    status_text, status_color = "Status: OFF", "#ff3333"
                device_info["labels"]["status"].config(text=status_text, foreground=status_color)
                device_info["labels"]["temp"].config(text=f"Current Temp: {current_temp:.1f} °C")
                device_info["labels"]["target"].config(text=f"Target Temp: {target_temp:.1f} °C ±{temp_margin:.1f}°C")
                device_info["labels"]["power"].config(text=f"Power: {power_kw:.2f} kW / {max_power_kw:.2f} kW")
                device_info["labels"]["consumption"].config(text=f"Hourly: {hourly_consumption_kwh:.3f} kWh | Daily: {daily_consumption_kwh:.3f} kWh")
                comfort = "✅ Comfortable" if target_temp - temp_margin <= current_temp <= target_temp + temp_margin else "❌ Outside range"
                device_info["labels"]["comfort"].config(text=f"Comfort: {comfort}")
                is_on = status == 'ON'

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

                device_info["labels"]["priority"].config(text=f"Priority: {priority}")
                if status == 'RUNNING':
                    status_text, status_color = "Compressor: ON", "#00ff88"
                else:
                    status_text, status_color = "Compressor: OFF", "#ff3333"
                device_info["labels"]["status"].config(text=status_text, foreground=status_color)
                device_info["labels"]["temp"].config(text=f"Interior Temp: {current_temp:.1f} °C")
                device_info["labels"]["target"].config(text=f"Target Temp: {target_temp:.1f} °C ±{temp_margin:.1f}°C")
                device_info["labels"]["power"].config(text=f"Power: {power_kw:.2f} kW / {max_power_kw:.2f} kW")
                device_info["labels"]["consumption"].config(text=f"Hourly: {hourly_consumption_kwh:.3f} kWh | Daily: {daily_consumption_kwh:.3f} kWh")
                is_on = status == 'RUNNING'

            elif device_info["type"] == "washing_machine":
                motor_status = device_state.get("motor_status", "Unknown")
                pending_clothes = device_state.get("pending_clothes", 0)
                wash_cycles_remaining = device_state.get("cycle_steps_remaining", 0)
                power_kw = device_state.get("power_kw", 0.0)
                max_power_kw = device_state.get("max_power_kw", 0.0)
                hourly_consumption_kwh = device_state.get("hourly_consumption_kwh", 0.0)
                daily_consumption_kwh = device_state.get("daily_consumption_kwh", 0.0)
                priority = device_state.get("priority", "-")

                device_info["labels"]["priority"].config(text=f"Priority: {priority}")
                if motor_status == 'WASHING':
                    motor_text, motor_color = "Motor: ON", "#00ff88"
                else:
                    motor_text, motor_color = "Motor: OFF", "#ff3333"
                device_info["labels"]["motor_status"].config(text=motor_text, foreground=motor_color)
                device_info["labels"]["pending_clothes"].config(text=f"Pending Clothes: {pending_clothes}")
                device_info["labels"]["wash_cycles"].config(text=f"Wash Cycles Remaining: {wash_cycles_remaining}")
                device_info["labels"]["power"].config(text=f"Power: {power_kw:.2f} kW / {max_power_kw:.2f} kW")
                device_info["labels"]["consumption"].config(text=f"Hourly: {hourly_consumption_kwh:.3f} kWh | Daily: {daily_consumption_kwh:.3f} kWh")
                is_on = motor_status == 'WASHING'

            elif device_info["type"] == "dish_washer":
                motor_status = device_state.get("motor_status", "Unknown")
                pending_dishes = device_state.get("pending_dishes", 0)
                wash_cycles_remaining = device_state.get("cycle_steps_remaining", 0)
                power_kw = device_state.get("power_kw", 0.0)
                max_power_kw = device_state.get("max_power_kw", 0.0)
                hourly_consumption_kwh = device_state.get("hourly_consumption_kwh", 0.0)
                daily_consumption_kwh = device_state.get("daily_consumption_kwh", 0.0)
                priority = device_state.get("priority", "-")

                device_info["labels"]["priority"].config(text=f"Priority: {priority}")
                if motor_status == 'WASHING':
                    motor_text, motor_color = "Motor: ON", "#00ff88"
                else:
                    motor_text, motor_color = "Motor: OFF", "#ff3333"
                device_info["labels"]["motor_status"].config(text=motor_text, foreground=motor_color)
                device_info["labels"]["pending_dishes"].config(text=f"Pending Dishes: {pending_dishes}")
                device_info["labels"]["wash_cycles"].config(text=f"Wash Cycles Remaining: {wash_cycles_remaining}")
                device_info["labels"]["power"].config(text=f"Power: {power_kw:.2f} kW / {max_power_kw:.2f} kW")
                device_info["labels"]["consumption"].config(text=f"Hourly: {hourly_consumption_kwh:.3f} kWh | Daily: {daily_consumption_kwh:.3f} kWh")
                is_on = motor_status == 'WASHING'

            elif device_info["type"] == "battery":
                status = device_state.get("status", "Unknown")
                level = device_state.get("battery_level", 0.0)
                provided_power = device_state.get("provided_power_kw", 0.0)
                solar_charge = device_state.get("solar_charge_kw", 0.0)
                priority = device_state.get("priority", "-")

                device_info["labels"]["priority"].config(text=f"Priority: {priority}")

                status_color = "#ffff00" if "solar panels" in status.lower() else ("#00ff88" if "DISCHARGING" in status else "#b0b0b0")
                device_info["labels"]["status"].config(text=f"State: {status}", foreground=status_color)
                device_info["labels"]["level"].config(text=f"Charge Level: {level:.1f}%")
                device_info["labels"]["power_provided"].config(text=f"Provided to House: {provided_power:.2f} kW", foreground="#00ff88")
                device_info["labels"]["solar_charge"].config(text=f"Solar Charge: {solar_charge:.2f} kW", foreground="#ffff00")
                is_on = status != "IDLE"

            elif device_info["type"] == "air_fryer":
                status = device_state.get("status", "Unknown")
                timer = device_state.get("cycle_minutes_remaining", 0)
                power_kw = device_state.get("power_kw", 0.0)
                max_power_kw = device_state.get("max_power_kw", 0.0)
                hourly_consumption_kwh = device_state.get("hourly_consumption_kwh", 0.0)
                daily_consumption_kwh = device_state.get("daily_consumption_kwh", 0.0)
                priority = device_state.get("priority", "-")

                device_info["labels"]["priority"].config(text=f"Priority: {priority}")
                if status == 'ON':
                    status_text, status_color = "Status: ON", "#00ff88"
                else:
                    status_text, status_color = "Status: OFF", "#ff3333"
                device_info["labels"]["status"].config(text=status_text, foreground=status_color)
                device_info["labels"]["timer"].config(text=f"Remaining: {timer} min")
                device_info["labels"]["power"].config(text=f"Power: {power_kw:.2f} kW / {max_power_kw:.2f} kW")
                device_info["labels"]["consumption"].config(text=f"Hourly: {hourly_consumption_kwh:.3f} kWh | Daily: {daily_consumption_kwh:.3f} kWh")
                is_on = status == 'ON'



            else:
                continue

            # Unified animation toggle
            if is_on and not device_info['animating']:
                device_info['animating'] = True
                self.start_animation(device_info['animation_label'], device_name)
            elif not is_on and device_info['animating']:
                device_info['animation_label'].config(image='')
                device_info['animating'] = False