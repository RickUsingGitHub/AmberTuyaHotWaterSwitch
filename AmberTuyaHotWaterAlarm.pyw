import tkinter as tk
from tkinter import font, messagebox
import threading
import time
import tinytuya
import requests
import json
import os
import sys
from datetime import datetime, timedelta

# Import for playing sounds on Windows
try:
    import winsound
except ImportError:
    winsound = None
    print("winsound module not available. Sound alerts will be disabled.")

# --- LOAD CONFIGURATION ---
CONFIG_FILE = "config.json"
config = {}

def load_main_config():
    global config
    # Ensure we look in the script's directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)

    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
        except Exception as e:
            messagebox.showerror("Config Error", f"Failed to parse {CONFIG_FILE}:\n{e}")
            sys.exit(1)
    else:
        messagebox.showerror("Config Error", f"{CONFIG_FILE} not found!\nPlease ensure the configuration file is in the script directory.")
        sys.exit(1)

# Load config immediately on startup
load_main_config()

class AmberAlarmApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Amber Alarm & Hot Water Monitor")
        self.root.geometry(config.get("WINDOW_SIZE", "1142x410"))
        self.root.configure(bg="#222222")
        self.root.resizable(True, True)

        # State storage
        self.low_threshold = config.get('low_thresh', 15.0)
        self.high_threshold = config.get('high_thresh', 30.0)
        self.current_price_color = "initial"
        self.mute_until = datetime.now()
        self.hw_on = None # Track HW state for toggling

        # Initial Custom Fonts
        self.font_med = font.Font(family="Segoe UI", size=18)
        self.font_small = font.Font(family="Segoe UI", size=10)
        self.font_x_large = font.Font(family="Segoe UI", size=70, weight="bold")
        self.font_button = font.Font(family="Segoe UI", size=12)

        # Bind resize event
        self.root.bind('<Configure>', self.on_resize)

        # --- MAIN FRAME ---
        self.frm_main = tk.Frame(root, bg="#222222")
        self.frm_main.pack(expand=True, fill='both', padx=20, pady=10)
        self.frm_main.grid_columnconfigure(0, weight=1)
        self.frm_main.grid_columnconfigure(1, weight=1)
        self.frm_main.grid_rowconfigure(0, weight=1)
        self.frm_main.grid_rowconfigure(1, weight=0)

        # --- LEFT COLUMN: AMBER PRICE & SETTINGS ---
        self.frm_left_amber = tk.Frame(self.frm_main, bg="#222222")
        self.frm_left_amber.grid(row=0, column=0, sticky="nsew", padx=10)
        self.frm_left_amber.grid_rowconfigure(1, weight=1)

        self.lbl_price_header = tk.Label(self.frm_left_amber, text="Current Electricity Price", font=self.font_med, bg="#222222", fg="#bbbbbb")
        self.lbl_price_header.grid(row=0, column=0, columnspan=2, pady=(4, 0), sticky="ew")

        self.lbl_price = tk.Label(self.frm_left_amber, text="-- c/kWh", font=self.font_x_large, bg="#222222", fg="#ffffff", anchor="center")
        self.lbl_price.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(0, 4))

        self.lbl_status = tk.Label(self.frm_left_amber, text="Fetching data...", font=self.font_small, bg="#222222", fg="#888888")
        self.lbl_status.grid(row=2, column=0, columnspan=2, pady=(0, 4))

        # Threshold Settings Frame
        self.frm_settings = tk.Frame(self.frm_left_amber, bg="#222222")
        self.frm_settings.grid(row=3, column=0, columnspan=2, pady=(0, 4))

        tk.Label(self.frm_settings, text="Green <", bg="#222222", fg="#00ff00").pack(side=tk.LEFT, padx=5)
        self.ent_low = tk.Entry(self.frm_settings, width=4, justify="center")
        self.ent_low.insert(0, str(self.low_threshold))
        self.ent_low.pack(side=tk.LEFT)
        self.ent_low.bind('<FocusOut>', lambda e: self.save_settings())
        self.ent_low.bind('<Return>', lambda e: self.save_settings())

        tk.Label(self.frm_settings, text="Yellow <", bg="#222222", fg="#ffff00").pack(side=tk.LEFT, padx=5)
        self.ent_high = tk.Entry(self.frm_settings, width=4, justify="center")
        self.ent_high.insert(0, str(self.high_threshold))
        self.ent_high.pack(side=tk.LEFT)
        self.ent_high.bind('<FocusOut>', lambda e: self.save_settings())
        self.ent_high.bind('<Return>', lambda e: self.save_settings())

        # --- RIGHT COLUMN: HOT WATER STATUS ---
        self.frm_right_hw = tk.Frame(self.frm_main, bg="#333333", relief=tk.RIDGE, bd=2)
        self.frm_right_hw.grid(row=0, column=1, sticky="nsew", padx=10)
        self.frm_right_hw.grid_rowconfigure(1, weight=1)

        self.lbl_hw_header = tk.Label(self.frm_right_hw, text="Hot Water Switch Status", font=self.font_med, bg="#333333", fg="#bbbbbb")
        self.lbl_hw_header.grid(row=0, column=0, pady=(20, 0), sticky="ew")

        # CHANGED: Label became a Button for interactivity
        self.btn_hw_toggle = tk.Button(self.frm_right_hw, text="UNKNOWN", font=self.font_x_large, bg="#333333", fg="#888888",
                                       command=self.toggle_hot_water, relief=tk.FLAT,
                                       activebackground="#444444", activeforeground="#ffffff", bd=0)
        self.btn_hw_toggle.grid(row=1, column=0, sticky="nsew", pady=(10, 20))

        # --- BOTTOM ROW: MUTE CONTROLS ---
        self.frm_mute_controls = tk.Frame(self.frm_main, bg="#222222")
        self.frm_mute_controls.grid(row=1, column=0, columnspan=2, pady=(5, 10))

        # Mute Status Label
        self.lbl_mute_status = tk.Label(self.frm_mute_controls, text="Sound Alerts Active", font=self.font_button, bg="#222222", fg="#888888")
        self.lbl_mute_status.pack(side=tk.TOP, pady=(0, 5))

        # Mute Buttons Frame
        self.frm_mute_btns = tk.Frame(self.frm_mute_controls, bg="#222222")
        self.frm_mute_btns.pack(side=tk.TOP)

        self.mute_buttons = []
        for hours in [1, 2, 4, 8]:
            btn = tk.Button(self.frm_mute_btns, text=f"{hours}h Mute", command=lambda h=hours: self.set_mute(h),
                            font=self.font_button, bg="#444444", fg="#ffffff",
                            activebackground="#666666", activeforeground="#ffffff", relief=tk.FLAT, bd=0, width=8)
            btn.pack(side=tk.LEFT, padx=5)
            self.mute_buttons.append(btn)

        self.btn_cancel_mute = tk.Button(self.frm_mute_btns, text="Cancel Mute", command=self.cancel_mute,
                                         font=self.font_button, bg="#444444", fg="#ffffff",
                                         activebackground="#666666", activeforeground="#ffffff", relief=tk.FLAT, bd=0, width=12)
        self.btn_cancel_mute.pack(side=tk.LEFT, padx=20)

        # Start the background updater
        self.running = True
        self.thread = threading.Thread(target=self.update_loop, daemon=True)
        self.thread.start()

        # Perform an initial font sizing and button update
        self.root.update_idletasks()
        self.on_resize(None)
        self.update_mute_status()

    # --- TOGGLE LOGIC ---
    def _get_tuya_device(self):
        dev_id = config.get("TUYA_DEVICE_ID")
        ip = config.get("TUYA_IP_ADDRESS")
        key = config.get("TUYA_LOCAL_KEY")
        ver = config.get("TUYA_VERSION", 3.4)

        if not all([dev_id, ip, key]):
            return None

        d = tinytuya.OutletDevice(dev_id, ip, key)
        d.set_version(ver)
        return d

    def toggle_hot_water(self):
        # Indicate loading
        self.btn_hw_toggle.config(text="...", state=tk.DISABLED)
        # Run in thread to prevent freezing
        threading.Thread(target=self._toggle_hw_thread, daemon=True).start()

    def _toggle_hw_thread(self):
        try:
            d = self._get_tuya_device()
            if not d:
                return

            # Determine action based on last known state (self.hw_on)
            # If unknown, fetch first
            if self.hw_on is None:
                status = d.status()
                if status and 'dps' in status:
                    self.hw_on = status['dps'].get('1', False)

            # Send command
            if self.hw_on:
                d.turn_off()
                new_state = False
            else:
                d.turn_on()
                new_state = True

            # Update internal state and GUI immediately
            self.hw_on = new_state

            # We don't have the price here, so pass None to just update HW status
            self.root.after(0, self.update_gui, None, None, self.hw_on)

        except Exception as e:
            print(f"Toggle Error: {e}")
            # Revert UI state on error
            self.root.after(0, self.update_gui, None, None, self.hw_on)

    # --- EXISTING LOGIC ---

    def is_night_time_mute(self):
        start = config.get("MUTE_START_HOUR", 23)
        end = config.get("MUTE_END_HOUR", 8)
        now_hour = datetime.now().hour

        if start <= end:
            return start <= now_hour < end
        else:
            return now_hour >= start or now_hour < end

    def cancel_mute(self):
        self.mute_until = datetime.now()
        self.update_mute_status()

    def set_mute(self, hours):
        now = datetime.now()
        if self.mute_until > now:
            self.mute_until += timedelta(hours=hours)
        else:
            self.mute_until = now + timedelta(hours=hours)
        self.update_mute_status()

    def update_mute_status(self):
        now = datetime.now()
        start = config.get("MUTE_START_HOUR", 23)
        end = config.get("MUTE_END_HOUR", 8)

        # Check Night Mute
        if self.is_night_time_mute():
            self.lbl_mute_status.config(text=f"Night Mute Active ({start}:00-{end}:00)", fg="#aaaaff")
            self.btn_cancel_mute.config(state=tk.DISABLED, bg="#333333")
            for btn in self.mute_buttons:
                btn.config(state=tk.DISABLED, bg="#333333")

            if self.root.after_idle:
                 self.root.after(60000, self.update_mute_status)
            return

        # Check Manual Mute
        if now < self.mute_until:
            remaining_time = self.mute_until - now
            total_seconds = int(remaining_time.total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)

            if hours > 0:
                 time_str = f"{hours:01d}:{minutes:02d}:{seconds:02d}"
            else:
                 time_str = f"{minutes:02d}:{seconds:02d}"

            self.lbl_mute_status.config(text=f"MUTED UNTIL {self.mute_until.strftime('%H:%M')} (Remaining: {time_str})", fg="#ff8888")
            self.btn_cancel_mute.config(state=tk.NORMAL, bg="#AA4444")

            for btn in self.mute_buttons:
                btn.config(state=tk.NORMAL, bg="#444444")

            if self.root.after_idle:
                 self.root.after(1000, self.update_mute_status)
        else:
            self.mute_until = now
            self.lbl_mute_status.config(text="Sound Alerts Active", fg="#888888")
            self.btn_cancel_mute.config(state=tk.DISABLED, bg="#333333")
            for btn in self.mute_buttons:
                btn.config(state=tk.NORMAL, bg="#444444")

    def on_resize(self, event):
        if event and event.widget != self.root:
            return

        width = self.root.winfo_width()
        scale_factor = width / 1142.0

        new_size_x_large = max(40, int(70 * scale_factor))
        new_size_med = max(12, int(18 * scale_factor))
        new_size_button = max(10, int(12 * scale_factor))

        self.font_x_large.config(size=new_size_x_large)
        self.font_med.config(size=new_size_med)
        self.font_button.config(size=new_size_button)

        self.lbl_price.config(font=self.font_x_large)
        self.btn_hw_toggle.config(font=self.font_x_large) # Update Button Font
        self.lbl_price_header.config(font=self.font_med)
        self.lbl_hw_header.config(font=self.font_med)

        self.lbl_mute_status.config(font=self.font_button)
        self.btn_cancel_mute.config(font=self.font_button)
        for btn in self.mute_buttons:
            btn.config(font=self.font_button)

    def play_alert_sound(self, threshold_type):
        if self.is_night_time_mute():
            return

        if winsound is None or datetime.now() < self.mute_until:
            return

        sound_file = ""
        if threshold_type == "green":
            sound_file = config.get("CHEER_SOUND_FILE", "Cheer.wav")
        elif threshold_type == "red":
            sound_file = config.get("ALARM_SOUND_FILE", "Alarm.wav")

        if sound_file:
            if os.path.exists(sound_file):
                winsound.PlaySound(sound_file, winsound.SND_FILENAME | winsound.SND_ASYNC)
            else:
                print(f"Sound file not found: {sound_file}")

    def save_settings(self):
        try:
            self.low_threshold = float(self.ent_low.get())
            self.high_threshold = float(self.ent_high.get())

            config['low_thresh'] = self.low_threshold
            config['high_thresh'] = self.high_threshold

            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=4)
        except ValueError:
            print("Error: Thresholds must be numeric.")
        except Exception as e:
            print(f"Error saving settings: {e}")

    def fetch_site_id(self):
        api_token = config.get("AMBER_API_TOKEN")
        if not api_token:
            return None

        url = "https://api.amber.com.au/v1/sites"
        headers = {"Authorization": f"Bearer {api_token}"}
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, list) and len(data) > 0:
                return data[0]['id']
        except Exception as e:
            print(f"Site ID Fetch Error: {e}")
        return None

    def get_amber_price(self):
        api_token = config.get("AMBER_API_TOKEN")
        site_id = config.get("AMBER_SITE_ID")

        if not api_token:
            return None, "Missing API Token"

        if not site_id:
            site_id = self.fetch_site_id()
            if not site_id:
                return None, "No Site ID Found"
            config["AMBER_SITE_ID"] = site_id

        url = f"https://api.amber.com.au/v1/sites/{site_id}/prices/current"
        headers = {"Authorization": f"Bearer {api_token}"}

        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            current_interval = data[0]
            for interval in data:
                if interval.get('channelType') == 'general':
                    current_interval = interval
                    break

            price = current_interval.get('perKwh')
            return price, "Live"
        except requests.exceptions.RequestException as e:
            print(f"Amber Error (Request): {e}")
            return None, "Error"
        except Exception as e:
            print(f"Amber Error (General): {e}")
            return None, "Error"

    def get_tuya_status(self):
        try:
            d = self._get_tuya_device()
            if not d: return None

            status = d.status()

            if status and 'dps' in status:
                is_on = status['dps'].get('1', False)
                return is_on
            return None
        except Exception as e:
            print(f"Tuya Error: {e}")
            return None

    def update_gui(self, price, price_status, hw_on):
        # Allow partial updates (e.g. from toggle thread)
        if hw_on is not None:
            self.hw_on = hw_on # Sync internal state
            self.btn_hw_toggle.config(state=tk.NORMAL) # Re-enable if disabled
            if hw_on is True:
                self.btn_hw_toggle.config(text="ON", fg="#ff4444")
            elif hw_on is False:
                self.btn_hw_toggle.config(text="OFF", fg="#00ff00")
            else:
                self.btn_hw_toggle.config(text="OFFLINE", fg="#888888")

        # If price is None, we are doing a partial update (HW only), skip price logic
        if price is None and price_status is None:
            return

        # Full Update Logic
        thresh_low = self.low_threshold
        thresh_high = self.high_threshold
        new_price_color = self.current_price_color

        if price is not None:
            self.lbl_price.config(text=f"{price:.2f}c")

            if price < thresh_low:
                self.lbl_price.config(fg="#00ff00")
                new_price_color = "green"
            elif price < thresh_high:
                self.lbl_price.config(fg="#ffff00")
                new_price_color = "yellow"
            else:
                self.lbl_price.config(fg="#ff4444")
                new_price_color = "red"

            is_manually_muted = datetime.now() < self.mute_until
            is_night_muted = self.is_night_time_mute()

            if new_price_color != self.current_price_color:
                if not is_manually_muted and not is_night_muted:
                    if new_price_color == "green":
                        self.play_alert_sound("green")
                    elif new_price_color == "red":
                        self.play_alert_sound("red")

            self.current_price_color = new_price_color
        else:
            self.lbl_price.config(text="--", fg="#888888")
            self.current_price_color = "initial"

        self.lbl_status.config(text=f"Amber Status: {price_status}")


    def update_loop(self):
        while self.running:
            price, price_stat = self.get_amber_price()
            hw_status = self.get_tuya_status()
            self.root.after(0, self.update_gui, price, price_stat, hw_status)
            time.sleep(config.get("REFRESH_RATE", 60))

if __name__ == "__main__":
    root = tk.Tk()
    app = AmberAlarmApp(root)
    root.mainloop()