import tkinter as tk
from tkinter import ttk
import matplotlib
matplotlib.use('TkAgg')
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np

class GraphsPanel:
    def __init__(self, parent):
        self.frame = ttk.LabelFrame(parent, text="Graph Statistics", padding=10)
        self.frame.pack(fill=tk.BOTH, expand=True)

        # Style settings
        self.bg_color = "#2d2d2d"
        self.text_color = "#e0e0e0"

        self.battery_color = "#00ffea"
        self.solar_color = "#ffed50"
        self.grid_color = "#ff285e"

        # Initialize history tracking
        self.history = {
            "times": [],
            "grid_cons": [],
            "battery_cons": [],
            "solar_cons": [],
            "costs": [],
            "prices": [],
            "grid_power": []
        }

        self.current_day = None
        self.hourly_turn_on_counts = {}
        self.prev_device_on_states = {}
        self.turn_on_device_order = []

        self.last_recorded_time = None

        self.setup_graphs()

    def setup_graphs(self):
        # Create Matplotlib Figure
        self.fig = Figure(figsize=(7, 10), dpi=100, facecolor=self.bg_color)
        
        # Adjust subplot parameters for a tighter fit
        self.fig.subplots_adjust(left=0.08, right=0.97, top=0.96, bottom=0.05, hspace=0.7, wspace=0.3)

        # 1. Pie Graph (Usage)
        self.ax_pie = self.fig.add_subplot(3, 2, 1)
        self.configure_axis(self.ax_pie, "Total Consumption Mix")

        # 2. Gauge (System Power) - We'll simulate it using a half-polar or bar
        self.ax_gauge = self.fig.add_subplot(3, 2, 2, polar=True)
        self.configure_axis(self.ax_gauge, "System Power Gauge")

        # 3. Line Graph (Energy Sources)
        self.ax_sources = self.fig.add_subplot(3, 2, 3)
        self.configure_axis(self.ax_sources, "Sources Over Time (kWh)")

        # 4. Line Graph (Cost)
        self.ax_cost = self.fig.add_subplot(3, 2, 4)
        self.configure_axis(self.ax_cost, "Grid Cost Over Time (€)")

        # 5. Line Graph (Energy Price)
        self.ax_price = self.fig.add_subplot(3, 2, 5)
        self.configure_axis(self.ax_price, "Energy Price (€/kWh) - Last 24 ticks")

        # 6. Stacked Bar (Turn-on counts by hour)
        self.ax_turnons = self.fig.add_subplot(3, 2, 6)
        self.configure_axis(self.ax_turnons, "Device Turn-Ons by Hour")

        # Create Canvas
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def _is_device_on(self, device_name, state):
        device_type = state.get("device_type", "")
        if device_type == "battery":
            return False

        if "ac_status" in state:
            return state.get("ac_status") == "ON"
        if "heater_status" in state:
            return state.get("heater_status") == "ON"
        if "compressor_status" in state:
            return state.get("compressor_status") in {"RUNNING", "ON"}
        if "motor_status" in state:
            return state.get("motor_status") in {"WASHING", "ON", "RUNNING"}
        if "status" in state:
            return state.get("status") in {"ON", "RUNNING", "COOKING", "HEATING", "WASHING"}

        return state.get("power_kw", 0.0) > 0.0

    def _ensure_device_counter(self, device_name):
        if device_name not in self.hourly_turn_on_counts:
            self.hourly_turn_on_counts[device_name] = [0] * 24
            self.turn_on_device_order.append(device_name)

    def _reset_turn_on_counters(self):
        self.hourly_turn_on_counts = {}
        self.prev_device_on_states = {}
        self.turn_on_device_order = []

    def _update_turn_on_tracking(self, hour, device_states):
        for device_name, state in device_states.items():
            is_on = self._is_device_on(device_name, state)
            prev_state = self.prev_device_on_states.get(device_name)

            # First observation only initializes state, no synthetic event.
            if prev_state is None:
                self.prev_device_on_states[device_name] = is_on
                continue

            if not prev_state and is_on:
                self._ensure_device_counter(device_name)
                hour_idx = max(0, min(23, int(hour)))
                self.hourly_turn_on_counts[device_name][hour_idx] += 1

            self.prev_device_on_states[device_name] = is_on

    def configure_axis(self, ax, title):
        ax.set_title(title, color=self.text_color, pad=10, fontsize=9)
        # Handle polar projection diffs
        if getattr(ax, 'name', '') != 'polar':
            ax.set_facecolor(self.bg_color)
            ax.tick_params(colors=self.text_color, labelsize=8)
            for spine in ax.spines.values():
                spine.set_color('#555555')
        else:
            ax.set_facecolor(self.bg_color)
            ax.tick_params(colors=self.text_color, labelsize=8)

    def draw_gauge(self, total_power, max_grid_power=10.0, solar_gen=0.0, battery_capacity=0.0):
        self.ax_gauge.clear()
        self.configure_axis(self.ax_gauge, "System Power (kW)")
        
        self.ax_gauge.set_theta_offset(np.pi)
        self.ax_gauge.set_theta_direction(-1)
        self.ax_gauge.set_thetamin(0)
        self.ax_gauge.set_thetamax(180)
        self.ax_gauge.set_ylim(0, 1)
        self.ax_gauge.set_yticks([])
        
        tot_max = max_grid_power + solar_gen + battery_capacity
        if tot_max <= 0: tot_max = 1.0
        
        self.ax_gauge.set_xticks(np.linspace(0, np.pi, 5))
        self.ax_gauge.set_xticklabels(['0', f'{tot_max/4:.1f}', f'{tot_max/2:.1f}', f'{tot_max*0.75:.1f}', f'{tot_max:.1f}'])
        
        # Color sections
        # Solar: 0 to solar_gen (yellow)
        # Battery: solar_gen to solar_gen + battery_capacity (yellow)
        # Grid: green -> yellow -> red
        def color_range(start_val, end_val, color):
            if end_val <= start_val: return
            s_angle = (start_val / tot_max) * np.pi
            e_angle = (end_val / tot_max) * np.pi
            self.ax_gauge.fill_between(np.linspace(s_angle, e_angle, 50), 0, 1, color=color, alpha=0.5)

        current_pos = 0.0
        
        # Solar
        if solar_gen > 0:
            color_range(current_pos, current_pos + solar_gen, self.solar_color)
            current_pos += solar_gen
            
        # Battery
        if battery_capacity > 0:
            color_range(current_pos, current_pos + battery_capacity, self.battery_color)
            current_pos += battery_capacity
            
        # Grid
        if max_grid_power > 0:
            color_range(current_pos, current_pos + 0.7 * max_grid_power, '#00ff88')
            color_range(current_pos + 0.7 * max_grid_power, current_pos + 0.85 * max_grid_power, '#ffcc00')
            color_range(current_pos + 0.85 * max_grid_power, current_pos + max_grid_power, '#ff3333')

        # Calculate angle for the needle
        clamped_val = max(0, min(total_power, tot_max))
        angle = (clamped_val / tot_max) * np.pi
        
        self.ax_gauge.plot([angle, angle], [0, 1], color="#2C2C2C", linewidth=3) # Changed needle to white for visibility

    def update_data(self, world, total_power, max_grid_power, solar_gen=0.0, battery_capacity=0.0, device_states=None):
        hour = world.get("hour", 0)
        minute = world.get("minute", 0)
        day = world.get("day", 1)
        time_str = f"{hour:02d}:{minute:02d}"

        grid_cons = world.get("hourly_grid_consumption_kwh", 0.0)
        batt_cons = world.get("hourly_battery_consumption_kwh", 0.0)
        sol_cons = world.get("hourly_solar_consumption_kwh", 0.0)
        cost = world.get("hourly_cost_euro", 0.0)
        price = world.get("energy_price", 0.0)

        if self.current_day is None:
            self.current_day = day
        elif day != self.current_day:
            self.current_day = day
            self._reset_turn_on_counters()

        # Update History only once per simulated minute (to avoid spamming points when time stalls)
        time_changed = False
        if self.last_recorded_time != time_str:
            self.history["times"].append(time_str)
            self.history["grid_cons"].append(grid_cons)
            self.history["battery_cons"].append(batt_cons)
            self.history["solar_cons"].append(sol_cons)
            self.history["costs"].append(cost)
            self.history["prices"].append(price)

            if device_states:
                self._update_turn_on_tracking(hour, device_states)
            
            # Keep history manageable (e.g., last 60 points)
            if len(self.history["times"]) > 60:
                for key in self.history:
                    self.history[key] = self.history[key][-60:]
            self.last_recorded_time = time_str
            time_changed = True

        current_val = (total_power, max_grid_power, solar_gen, battery_capacity)
        gauge_changed = False
        if not hasattr(self, 'last_gauge_val') or self.last_gauge_val != current_val:
            self.last_gauge_val = current_val
            gauge_changed = True

        if not (time_changed or gauge_changed):
            return

        if time_changed:
            # Redraw Pie
            self.ax_pie.clear()
            self.configure_axis(self.ax_pie, "Consumption Mix (Daily)")
            labels = ['Grid', 'Battery', 'Solar']
            sizes = [0,0,0]

            for i, cons in enumerate([grid_cons, batt_cons, sol_cons]):
                # Only last 24h data for pie (sum of last 24 points or less if not available)
                recent_sum = sum(self.history[f"{labels[i].lower()}_cons"][-24:])
                sizes[i] = recent_sum

            colors = [self.grid_color, self.battery_color, self.solar_color]
            
            if sum(sizes) > 0.01:
                wedges, texts = self.ax_pie.pie(sizes, colors=colors, startangle=90)
                self.ax_pie.legend(wedges, labels, loc="upper right", bbox_to_anchor=(1.2, 1.0),
                                   fontsize=7, facecolor=self.bg_color, edgecolor='none', labelcolor=self.text_color)
            else:
                self.ax_pie.text(0, 0, "No Data", ha='center', va='center', color=self.text_color)

            # Redraw Sources Line Graph
            self.ax_sources.clear()
            self.configure_axis(self.ax_sources, "Sources (Last 24 ticks)")
            if len(self.history["times"]) > 0:
                recent_ticks = 24
                recent_grid = self.history["grid_cons"][-recent_ticks:]
                recent_battery = self.history["battery_cons"][-recent_ticks:]
                recent_solar = self.history["solar_cons"][-recent_ticks:]
                x_vals = range(len(recent_grid))
                self.ax_sources.plot(x_vals, recent_grid, label='Grid', color=self.grid_color)
                self.ax_sources.plot(x_vals, recent_battery, label='Battery', color=self.battery_color)
                self.ax_sources.plot(x_vals, recent_solar, label='Solar', color=self.solar_color)
                self.ax_sources.legend(loc='upper left', fontsize=7, facecolor=self.bg_color, edgecolor='none', labelcolor=self.text_color)

            # Redraw Cost Line Graph
            self.ax_cost.clear()
            self.configure_axis(self.ax_cost, "Cost (€) (Last 24 ticks)")
            if len(self.history["times"]) > 0:
                recent_ticks = 24
                recent_costs = self.history["costs"][-recent_ticks:]
                x_vals = range(len(recent_costs))
                self.ax_cost.plot(x_vals, recent_costs, label='Cost', color="#ffcc00")

            # Redraw Energy Price Line Graph
            self.ax_price.clear()
            self.configure_axis(self.ax_price, "Energy Price (€/kWh) - Last 24 ticks")
            if len(self.history["times"]) > 0:
                recent_ticks = 24
                recent_prices = self.history["prices"][-recent_ticks:]
                x_vals = range(len(recent_prices))
                self.ax_price.plot(x_vals, recent_prices, label='Price', color="#66ccff")
                self.ax_price.legend(loc='upper left', fontsize=7, facecolor=self.bg_color, edgecolor='none', labelcolor=self.text_color)

            # Redraw Device Turn-On Stacked Bar Chart
            self.ax_turnons.clear()
            self.configure_axis(self.ax_turnons, "Device Turn-Ons by Hour")
            hours = np.arange(24)
            bottom = np.zeros(24)
            if self.turn_on_device_order:
                color_map = matplotlib.colormaps.get_cmap("tab20")
                for idx, device_name in enumerate(self.turn_on_device_order):
                    counts = np.array(self.hourly_turn_on_counts.get(device_name, [0] * 24))
                    if counts.sum() <= 0:
                        continue
                    color = color_map(idx % 20)
                    self.ax_turnons.bar(hours, counts, bottom=bottom, width=0.8, label=device_name, color=color, alpha=0.85)
                    bottom += counts

                self.ax_turnons.legend(loc='upper right', fontsize=6, ncol=2, facecolor=self.bg_color, edgecolor='none', labelcolor=self.text_color)
            else:
                self.ax_turnons.text(11.5, 0.5, "No turn-on events yet", ha='center', va='center', color=self.text_color)

            self.ax_turnons.set_xticks(range(0, 24, 2))
            self.ax_turnons.set_xlim(-0.5, 23.5)
            self.ax_turnons.set_xlabel("Hour of day", color=self.text_color, fontsize=8)
            self.ax_turnons.set_ylabel("Turn-on count", color=self.text_color, fontsize=8)

        if gauge_changed or time_changed:
            # Redraw Gauge
            self.draw_gauge(total_power, max_grid_power if max_grid_power > 0 else 10.0, solar_gen, battery_capacity)

        # Refresh Canvas
        self.canvas.draw_idle()
