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

        # Initialize history tracking
        self.history = {
            "times": [],
            "grid_cons": [],
            "battery_cons": [],
            "solar_cons": [],
            "costs": [],
            "grid_power": []
        }

        self.last_recorded_time = None

        self.setup_graphs()

    def setup_graphs(self):
        # Create Matplotlib Figure
        self.fig = Figure(figsize=(6, 8), dpi=100, facecolor=self.bg_color)
        
        # Adjust subplot parameters for a tighter fit
        self.fig.subplots_adjust(left=0.1, right=0.95, top=0.95, bottom=0.05, hspace=0.6, wspace=0.3)

        # 1. Pie Graph (Usage)
        self.ax_pie = self.fig.add_subplot(2, 2, 1)
        self.configure_axis(self.ax_pie, "Total Consumption Mix")

        # 2. Gauge (Grid Power) - We'll simulate it using a half-polar or bar
        self.ax_gauge = self.fig.add_subplot(2, 2, 2, polar=True)
        self.configure_axis(self.ax_gauge, "Grid Power Gauge")

        # 3. Line Graph (Energy Sources)
        self.ax_sources = self.fig.add_subplot(2, 2, 3)
        self.configure_axis(self.ax_sources, "Sources Over Time (kWh)")

        # 4. Line Graph (Cost)
        self.ax_cost = self.fig.add_subplot(2, 2, 4)
        self.configure_axis(self.ax_cost, "Grid Cost Over Time (€)")

        # Create Canvas
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

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

    def draw_gauge(self, val, max_val_est=10.0, battery_extra=0.0):
        self.ax_gauge.clear()
        self.configure_axis(self.ax_gauge, "Grid Power (kW)")
        
        self.ax_gauge.set_theta_offset(np.pi)
        self.ax_gauge.set_theta_direction(-1)
        self.ax_gauge.set_thetamin(0)
        self.ax_gauge.set_thetamax(180)
        self.ax_gauge.set_ylim(0, 1)
        self.ax_gauge.set_yticks([])
        
        tot_max = max_val_est + battery_extra
        if tot_max <= 0: tot_max = 1.0
        
        self.ax_gauge.set_xticks(np.linspace(0, np.pi, 5))
        self.ax_gauge.set_xticklabels(['0', f'{tot_max/4:.1f}', f'{tot_max/2:.1f}', f'{tot_max*0.75:.1f}', f'{tot_max:.1f}'])
        
        # Color sections
        # Green: 0 to 70% of max_val_est
        # Yellow: 70% to 85% of max_val_est
        # Orange: 85% to 100% of max_val_est
        # Blue: max_val_est to tot_max (Battery Extra)
        def color_range(start_val, end_val, color):
            s_angle = (start_val / tot_max) * np.pi
            e_angle = (end_val / tot_max) * np.pi
            self.ax_gauge.fill_between(np.linspace(s_angle, e_angle, 50), 0, 1, color=color, alpha=0.5)

        color_range(0, 0.7 * max_val_est, '#00ff88')
        color_range(0.7 * max_val_est, 0.85 * max_val_est, '#ffcc00')
        color_range(0.85 * max_val_est, max_val_est, '#ff9900')
        if battery_extra > 0:
            color_range(max_val_est, tot_max, '#66b3ff')

        # Calculate angle for the needle
        clamped_val = max(0, min(val, tot_max))
        angle = (clamped_val / tot_max) * np.pi
        
        self.ax_gauge.plot([angle, angle], [0, 1], color='#ff3333', linewidth=3)

    def update_data(self, world, total_grid_power, max_grid_power, battery_extra=0.0):
        hour = world.get("hour", 0)
        minute = world.get("minute", 0)
        time_str = f"{hour:02d}:{minute:02d}"

        grid_cons = world.get("hourly_grid_consumption_kwh", 0.0)
        batt_cons = world.get("hourly_battery_consumption_kwh", 0.0)
        sol_cons = world.get("hourly_solar_consumption_kwh", 0.0)
        cost = world.get("hourly_cost_euro", 0.0)

        # Update History only once per simulated minute (to avoid spamming points when time stalls)
        time_changed = False
        if self.last_recorded_time != time_str:
            self.history["times"].append(time_str)
            self.history["grid_cons"].append(grid_cons)
            self.history["battery_cons"].append(batt_cons)
            self.history["solar_cons"].append(sol_cons)
            self.history["costs"].append(cost)
            
            # Keep history manageable (e.g., last 60 points)
            if len(self.history["times"]) > 60:
                for key in self.history:
                    self.history[key] = self.history[key][-60:]
            self.last_recorded_time = time_str
            time_changed = True

        current_val = (total_grid_power, max_grid_power, battery_extra)
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
            sizes = [grid_cons, batt_cons, sol_cons]
            colors = ['#ff9999','#66b3ff','#99ff99']
            
            if sum(sizes) > 0.01:
                wedges, texts = self.ax_pie.pie(sizes, colors=colors, startangle=90)
                self.ax_pie.legend(wedges, labels, loc="upper right", bbox_to_anchor=(1.2, 1.0),
                                   fontsize=7, facecolor=self.bg_color, edgecolor='none', labelcolor=self.text_color)
            else:
                self.ax_pie.text(0, 0, "No Data", ha='center', va='center', color=self.text_color)

            # Redraw Sources Line Graph
            self.ax_sources.clear()
            self.configure_axis(self.ax_sources, "Sources (Last 60 ticks)")
            if len(self.history["times"]) > 0:
                x_vals = range(len(self.history["times"]))
                self.ax_sources.plot(x_vals, self.history["grid_cons"], label='Grid', color='#ff9999')
                self.ax_sources.plot(x_vals, self.history["battery_cons"], label='Battery', color='#66b3ff')
                self.ax_sources.plot(x_vals, self.history["solar_cons"], label='Solar', color='#99ff99')
                self.ax_sources.legend(loc='upper left', fontsize=7, facecolor=self.bg_color, edgecolor='none', labelcolor=self.text_color)
                self.ax_sources.set_xticks([0, len(x_vals)-1])
                self.ax_sources.set_xticklabels([self.history["times"][0], self.history["times"][-1]])

            # Redraw Cost Line Graph
            self.ax_cost.clear()
            self.configure_axis(self.ax_cost, "Cost (€) (Last 60 ticks)")
            if len(self.history["times"]) > 0:
                x_vals = range(len(self.history["times"]))
                self.ax_cost.plot(x_vals, self.history["costs"], label='Cost', color='#ffcc00')
                self.ax_cost.set_xticks([0, len(x_vals)-1])
                self.ax_cost.set_xticklabels([self.history["times"][0], self.history["times"][-1]])

        if gauge_changed or time_changed:
            # Redraw Gauge
            self.draw_gauge(total_grid_power, max_grid_power if max_grid_power > 0 else 10.0, battery_extra)

        # Refresh Canvas
        self.canvas.draw_idle()
