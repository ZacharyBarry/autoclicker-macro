import sys
import subprocess
import os
import time
import threading

# --- DPI AWARENESS FIX (Crisp Text) ---
# This forces Windows to render the app at native high-definition scaling instead of stretching it
if os.name == 'nt':
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

import tkinter as tk
from tkinter import filedialog, messagebox


# --- AUTO-INSTALL DEPENDENCIES ---
def ensure_dependencies():
    try:
        import pynput
        import mss
        from PIL import Image
        import customtkinter
    except ImportError:
        print("Missing required libraries. Installing them automatically...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pynput", "mss", "Pillow", "customtkinter"])
            print("Installation successful! Restarting application...")
            os.execl(sys.executable, sys.executable, *sys.argv)
        except Exception as e:
            print(f"Auto-install failed. Please manually run: pip install pynput mss Pillow customtkinter\nError: {e}")
            sys.exit(1)


ensure_dependencies()

from pynput import mouse, keyboard
import mss
from PIL import Image
import customtkinter as ctk

# --- UI THEME SETUP ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class ModernTextbox(ctk.CTkTextbox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.highlighting_enabled = True

        self.tag_config("MOVE", foreground="#5865f2")
        self.tag_config("WAIT", foreground="#949ba4")
        self.tag_config("DOWN", foreground="#57f287")
        self.tag_config("UP", foreground="#ed4245")
        self.tag_config("KEY_DOWN", foreground="#00d26a")
        self.tag_config("KEY_UP", foreground="#f8a532")
        self.tag_config("WAIT_PIXEL", foreground="#fee75c")
        self.tag_config("COMMENT", foreground="#80848e")

        self.bind("<<Modified>>", self._on_change)
        self.bind("<Configure>", self._on_change)

    def _on_change(self, event=None):
        self.highlight()
        self.edit_modified(False)

    def highlight(self):
        if not self.highlighting_enabled:
            return

        for tag in self.tag_names():
            self.tag_remove(tag, "1.0", "end")

        for i, line in enumerate(self.get("1.0", "end-1c").split("\n")):
            line_num = i + 1
            if "MOVE" in line:
                self.tag_add("MOVE", f"{line_num}.0", f"{line_num}.4")
            elif "WAIT," in line:
                self.tag_add("WAIT", f"{line_num}.0", f"{line_num}.4")
            elif "DOWN" in line:
                self.tag_add("DOWN", f"{line_num}.0", f"{line_num}.4")
            elif "UP" in line:
                self.tag_add("UP", f"{line_num}.0", f"{line_num}.2")
            elif "KEY_DOWN" in line:
                self.tag_add("KEY_DOWN", f"{line_num}.0", f"{line_num}.8")
            elif "KEY_UP" in line:
                self.tag_add("KEY_UP", f"{line_num}.0", f"{line_num}.6")
            elif "WAIT_PIXEL" in line:
                self.tag_add("WAIT_PIXEL", f"{line_num}.0", f"{line_num}.10")
            elif line.strip().startswith("#"):
                self.tag_add("COMMENT", f"{line_num}.0", f"{line_num}.end")


class AutoClickerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Auto-Clicker Pro")
        self.geometry("900x700")
        self.minsize(850, 650)

        self.is_clicking = False
        self.is_recording = False
        self.is_playing = False
        self.is_mouse_down = False
        self.last_event_time = None
        self.status_message_id = None
        self.hotkey_to_set = None
        self.script_dirty = False

        self.clicker_stop_event = threading.Event()
        self.macro_stop_event = threading.Event()

        self.click_thread = None
        self.macro_thread = None
        self.global_listener = None
        self.recording_listener = None
        self.location_listener = None

        # --- DEFAULT HOTKEYS ---
        self.clicker_hotkey = keyboard.KeyCode(char="+")
        self.record_hotkey = keyboard.Key.f10
        self.play_hotkey = keyboard.Key.f12
        self.stop_hotkey = keyboard.Key.esc  # Unified stop hotkey

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # --- SIDEBAR ---
        self.sidebar_frame = ctk.CTkFrame(self, width=180, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, rowspan=2, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(3, weight=1)

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="Clicker Pro", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 30))

        self.nav_clicker_btn = ctk.CTkButton(self.sidebar_frame, text="Auto-Clicker", fg_color="transparent",
                                             text_color=("gray10", "gray90"), hover_color=("gray70", "gray30"),
                                             anchor="w", command=lambda: self.select_frame("clicker"))
        self.nav_clicker_btn.grid(row=1, column=0, padx=10, pady=5, sticky="ew")

        self.nav_macro_btn = ctk.CTkButton(self.sidebar_frame, text="Macro Recorder", fg_color="transparent",
                                           text_color=("gray10", "gray90"), hover_color=("gray70", "gray30"),
                                           anchor="w", command=lambda: self.select_frame("macro"))
        self.nav_macro_btn.grid(row=2, column=0, padx=10, pady=5, sticky="ew")

        self.always_on_top_var = ctk.BooleanVar(value=True)
        self.topmost_switch = ctk.CTkSwitch(self.sidebar_frame, text="Always on Top", variable=self.always_on_top_var,
                                            command=self.toggle_always_on_top)
        self.topmost_switch.grid(row=4, column=0, padx=20, pady=20, sticky="w")

        # --- MAIN FRAMES ---
        self.clicker_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.macro_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")

        self.build_clicker_ui()
        self.build_macro_ui()

        self.select_frame("clicker")

        self.global_listener = keyboard.Listener(on_press=self.on_global_press, on_release=self.on_global_release)
        self.global_listener.start()
        self.attributes("-topmost", True)
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.update_ui_states()

    def select_frame(self, name):
        self.nav_clicker_btn.configure(fg_color=("gray75", "gray25") if name == "clicker" else "transparent")
        self.nav_macro_btn.configure(fg_color=("gray75", "gray25") if name == "macro" else "transparent")

        if name == "clicker":
            self.macro_frame.grid_forget()
            self.clicker_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        elif name == "macro":
            self.clicker_frame.grid_forget()
            self.macro_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)

    def validate_interval(self, P):
        if P == "" or P == ".": return True
        try:
            val = float(P)
            return val >= 0
        except ValueError:
            return False

    def build_clicker_ui(self):
        self.click_location_mode = ctk.IntVar(value=0)
        self.interval_var = ctk.StringVar(value="0.5")
        self.x_var = ctk.StringVar(value="100")
        self.y_var = ctk.StringVar(value="100")
        self.clicker_hotkey_var = ctk.StringVar(value="+")
        self.clicker_status_var = ctk.StringVar(value="Status: Idle")

        ctk.CTkLabel(self.clicker_frame, text="Auto-Clicker Settings", font=ctk.CTkFont(size=24, weight="bold")).pack(
            anchor="w", pady=(0, 20))

        card_interval = ctk.CTkFrame(self.clicker_frame)
        card_interval.pack(fill="x", pady=10)

        ctk.CTkLabel(card_interval, text="Interval (seconds):", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0,
                                                                                                      padx=20, pady=20,
                                                                                                      sticky="w")
        vcmd = (self.register(self.validate_interval), '%P')
        self.interval_entry = ctk.CTkEntry(card_interval, textvariable=self.interval_var, width=120)
        self.interval_entry.grid(row=0, column=1, padx=20, pady=20, sticky="w")

        card_location = ctk.CTkFrame(self.clicker_frame)
        card_location.pack(fill="x", pady=10)

        self.loc_mode_current = ctk.CTkRadioButton(card_location, text="Click at current mouse position",
                                                   variable=self.click_location_mode, value=0,
                                                   command=self.update_ui_states)
        self.loc_mode_current.grid(row=0, column=0, columnspan=4, padx=20, pady=(20, 10), sticky="w")

        self.loc_mode_specific = ctk.CTkRadioButton(card_location, text="Click at specific coordinates",
                                                    variable=self.click_location_mode, value=1,
                                                    command=self.update_ui_states)
        self.loc_mode_specific.grid(row=1, column=0, padx=20, pady=(10, 20), sticky="w")

        self.set_loc_button = ctk.CTkButton(card_location, text="Pick on Screen", command=self.prompt_for_location,
                                            width=120)
        self.set_loc_button.grid(row=1, column=1, padx=10, pady=(10, 20))

        ctk.CTkLabel(card_location, text="X:").grid(row=1, column=2, padx=(10, 2), pady=(10, 20))
        self.x_entry = ctk.CTkEntry(card_location, textvariable=self.x_var, width=60)
        self.x_entry.grid(row=1, column=3, padx=(0, 20), pady=(10, 20))

        ctk.CTkLabel(card_location, text="Y:").grid(row=1, column=4, padx=(10, 2), pady=(10, 20))
        self.y_entry = ctk.CTkEntry(card_location, textvariable=self.y_var, width=60)
        self.y_entry.grid(row=1, column=5, padx=(0, 20), pady=(10, 20))

        card_controls = ctk.CTkFrame(self.clicker_frame)
        card_controls.pack(fill="x", pady=10)

        ctk.CTkLabel(card_controls, text="Hotkey:").grid(row=0, column=0, padx=20, pady=20, sticky="w")
        self.clicker_hotkey_entry = ctk.CTkEntry(card_controls, textvariable=self.clicker_hotkey_var, width=120,
                                                 state="readonly", font=ctk.CTkFont(weight="bold"))
        self.clicker_hotkey_entry.grid(row=0, column=1, padx=10, pady=20)
        self.set_clicker_hotkey_button = ctk.CTkButton(card_controls, text="Set Key",
                                                       command=lambda: self.set_hotkey_mode('clicker'), width=80)
        self.set_clicker_hotkey_button.grid(row=0, column=2, padx=10, pady=20)

        button_frame = ctk.CTkFrame(self.clicker_frame, fg_color="transparent")
        button_frame.pack(fill="x", pady=20)

        self.start_button = ctk.CTkButton(button_frame, text="▶ Start Clicking",
                                          font=ctk.CTkFont(size=14, weight="bold"), height=40,
                                          command=self.start_clicker, fg_color="#28a745", hover_color="#218838")
        self.start_button.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.stop_button = ctk.CTkButton(button_frame, text="⏹ Stop", font=ctk.CTkFont(size=14, weight="bold"),
                                         height=40, command=self.stop_clicker, fg_color="#dc3545",
                                         hover_color="#c82333")
        self.stop_button.pack(side="left", fill="x", expand=True, padx=(10, 0))

        self.clicker_status_label = ctk.CTkLabel(self.clicker_frame, textvariable=self.clicker_status_var,
                                                 text_color="gray60", font=ctk.CTkFont(size=12))
        self.clicker_status_label.pack(anchor="w", side="bottom")

    def build_macro_ui(self):
        self.macro_frame.grid_rowconfigure(3, weight=1)
        self.macro_frame.grid_columnconfigure(0, weight=1)

        self.repeat_var = ctk.StringVar(value="1")
        self.macro_status_var = ctk.StringVar(value="Status: Idle")

        # Explicit variables for display
        self.record_hotkey_var = ctk.StringVar(value=self.get_key_name(self.record_hotkey))
        self.play_hotkey_var = ctk.StringVar(value=self.get_key_name(self.play_hotkey))
        self.stop_hotkey_var = ctk.StringVar(value=self.get_key_name(self.stop_hotkey))

        self.schedule_var = ctk.StringVar(value="0")

        self.playback_speed_var = tk.DoubleVar(value=1.0)
        self.formatted_speed_var = ctk.StringVar(value="1.00x")
        self.playback_speed_var.trace_add("write", lambda *args: self.formatted_speed_var.set(
            f"{self.playback_speed_var.get():.2f}x"))

        ctk.CTkLabel(self.macro_frame, text="Macro Engine", font=ctk.CTkFont(size=24, weight="bold")).grid(row=0,
                                                                                                           column=0,
                                                                                                           sticky="w",
                                                                                                           pady=(0, 15))

        # --- NEW: HOTKEYS BOARD ---
        hotkeys_card = ctk.CTkFrame(self.macro_frame)
        hotkeys_card.grid(row=1, column=0, sticky="ew", pady=(0, 10))

        # Record Mapping
        ctk.CTkLabel(hotkeys_card, text="Record:", text_color="#ed4245", font=ctk.CTkFont(weight="bold")).grid(row=0,
                                                                                                               column=0,
                                                                                                               padx=(20,
                                                                                                                     5),
                                                                                                               pady=10)
        self.record_hotkey_entry = ctk.CTkEntry(hotkeys_card, textvariable=self.record_hotkey_var, state="readonly",
                                                width=80, font=ctk.CTkFont(weight="bold"))
        self.record_hotkey_entry.grid(row=0, column=1, padx=5, pady=10)
        ctk.CTkButton(hotkeys_card, text="Set", width=50, command=lambda: self.set_hotkey_mode('record')).grid(row=0,
                                                                                                               column=2,
                                                                                                               padx=(0,
                                                                                                                     15),
                                                                                                               pady=10)

        # Play Mapping
        ctk.CTkLabel(hotkeys_card, text="Play:", text_color="#57f287", font=ctk.CTkFont(weight="bold")).grid(row=0,
                                                                                                             column=3,
                                                                                                             padx=(15,
                                                                                                                   5),
                                                                                                             pady=10)
        self.play_hotkey_entry = ctk.CTkEntry(hotkeys_card, textvariable=self.play_hotkey_var, state="readonly",
                                              width=80, font=ctk.CTkFont(weight="bold"))
        self.play_hotkey_entry.grid(row=0, column=4, padx=5, pady=10)
        ctk.CTkButton(hotkeys_card, text="Set", width=50, command=lambda: self.set_hotkey_mode('play')).grid(row=0,
                                                                                                             column=5,
                                                                                                             padx=(0,
                                                                                                                   15),
                                                                                                             pady=10)

        # Stop Mapping
        ctk.CTkLabel(hotkeys_card, text="Stop All:", text_color="#f8a532", font=ctk.CTkFont(weight="bold")).grid(row=0,
                                                                                                                 column=6,
                                                                                                                 padx=(
                                                                                                                     15,
                                                                                                                     5),
                                                                                                                 pady=10)
        self.stop_hotkey_entry = ctk.CTkEntry(hotkeys_card, textvariable=self.stop_hotkey_var, state="readonly",
                                              width=80, font=ctk.CTkFont(weight="bold"))
        self.stop_hotkey_entry.grid(row=0, column=7, padx=5, pady=10)
        ctk.CTkButton(hotkeys_card, text="Set", width=50, command=lambda: self.set_hotkey_mode('stop')).grid(row=0,
                                                                                                             column=8,
                                                                                                             padx=(0,
                                                                                                                   20),
                                                                                                             pady=10)

        # Playback Settings
        settings_bar = ctk.CTkFrame(self.macro_frame)
        settings_bar.grid(row=2, column=0, sticky="ew", pady=(0, 15))

        ctk.CTkLabel(settings_bar, text="Repeat:").grid(row=0, column=0, padx=(15, 5), pady=15)
        self.repeat_entry = ctk.CTkEntry(settings_bar, textvariable=self.repeat_var, width=50)
        self.repeat_entry.grid(row=0, column=1, padx=5, pady=15)

        ctk.CTkLabel(settings_bar, text="Speed:").grid(row=0, column=2, padx=(20, 5), pady=15)
        self.speed_scale = ctk.CTkSlider(settings_bar, from_=0.1, to=10.0, variable=self.playback_speed_var, width=120)
        self.speed_scale.grid(row=0, column=3, padx=5, pady=15)
        ctk.CTkLabel(settings_bar, textvariable=self.formatted_speed_var, width=40).grid(row=0, column=4, padx=5,
                                                                                         pady=15)

        ctk.CTkLabel(settings_bar, text="Delay (s):").grid(row=0, column=5, padx=(20, 5), pady=15)
        self.schedule_entry = ctk.CTkEntry(settings_bar, textvariable=self.schedule_var, width=50)
        self.schedule_entry.grid(row=0, column=6, padx=5, pady=15)
        self.schedule_button = ctk.CTkButton(settings_bar, text="Schedule", width=70, command=self.schedule_playback)
        self.schedule_button.grid(row=0, column=7, padx=10, pady=15)

        # Editor
        self.script_text = ModernTextbox(self.macro_frame, font=ctk.CTkFont(family="Consolas", size=14), wrap="word",
                                         corner_radius=8, border_width=2, border_color="#313338")
        self.script_text.grid(row=3, column=0, sticky="nsew", pady=(0, 15))

        # Bottom Tools
        tool_bar = ctk.CTkFrame(self.macro_frame, fg_color="transparent")
        tool_bar.grid(row=4, column=0, sticky="ew", pady=(0, 5))

        self.load_button = ctk.CTkButton(tool_bar, text="📂 Load", width=80, fg_color="transparent", border_width=1,
                                         command=self.load_script)
        self.load_button.pack(side="left", padx=(0, 10))
        self.save_button = ctk.CTkButton(tool_bar, text="💾 Save", width=80, fg_color="transparent", border_width=1,
                                         command=self.save_script)
        self.save_button.pack(side="left", padx=10)
        self.clear_button = ctk.CTkButton(tool_bar, text="🗑 Clear", width=80, fg_color="transparent", border_width=1,
                                          hover_color="#5c1a1c", command=lambda: self.script_text.delete("1.0", tk.END))
        self.clear_button.pack(side="left", padx=10)
        self.get_pixel_button = ctk.CTkButton(tool_bar, text="Get Pixel Color", width=120, command=self.get_pixel_color)
        self.get_pixel_button.pack(side="right", padx=(10, 0))

        # Progress & Status
        self.macro_progress = ctk.CTkProgressBar(self.macro_frame)
        self.macro_progress.grid(row=5, column=0, sticky="ew", pady=(10, 5))
        self.macro_progress.set(0)

        self.macro_status_label = ctk.CTkLabel(self.macro_frame, textvariable=self.macro_status_var,
                                               text_color="gray60", font=ctk.CTkFont(size=12))
        self.macro_status_label.grid(row=6, column=0, sticky="w")

    # ==========================================
    # CORE LOGIC
    # ==========================================
    def toggle_always_on_top(self):
        self.attributes("-topmost", self.always_on_top_var.get())

    def start_clicker(self):
        if self.is_clicking: return
        try:
            interval = float(self.interval_var.get())
            if interval <= 0:
                self.show_status_message("Error: Interval must be positive.")
                return
            coords = (0, 0)
            if self.click_location_mode.get() == 1:
                coords = (int(self.x_var.get()), int(self.y_var.get()))
        except ValueError:
            self.show_status_message("Error: Invalid interval or coordinates.")
            return
        self.is_clicking = True
        self.clicker_stop_event.clear()
        self.click_thread = threading.Thread(target=self.run_clicker,
                                             args=(interval, self.click_location_mode.get(), coords))
        self.click_thread.start()
        self.update_ui_states()

    def stop_clicker(self):
        if not self.is_clicking: return
        self.clicker_stop_event.set()

    def run_clicker(self, interval, click_mode, coords):
        mouse_controller = mouse.Controller()
        while not self.clicker_stop_event.is_set():
            if click_mode == 1:
                mouse_controller.position = coords
                time.sleep(0.05)
            mouse_controller.click(mouse.Button.left, 1)
            self.clicker_stop_event.wait(interval)
        self.is_clicking = False
        self.after(0, self.update_ui_states)

    def prompt_for_location(self):
        self.withdraw()
        self.location_listener = mouse.Listener(on_click=self.on_location_click)
        self.location_listener.start()

    def on_location_click(self, x, y, _button, pressed):
        if pressed:
            self.deiconify()
            self.lift()
            self.x_var.set(str(x))
            self.y_var.set(str(y))
            self.show_status_message(f"Location set to ({x}, {y})")
            if self.location_listener:
                self.location_listener.stop()
                self.location_listener = None
            return False

    def toggle_recording(self):
        if self.is_recording:
            self.stop_recording()
        else:
            self.start_recording()

    def start_recording(self):
        self.is_recording = True
        self.is_mouse_down = False
        self.script_text.highlighting_enabled = False
        self.script_text.delete("1.0", tk.END)
        self.last_event_time = time.time()
        self.last_recorded_pos = (0, 0)
        self.update_ui_states()
        self.recording_listener = mouse.Listener(on_move=self.on_record_move, on_click=self.on_record_click)
        self.recording_listener.start()

    def stop_recording(self):
        if self.recording_listener:
            self.recording_listener.stop()
            self.recording_listener = None
        self.is_recording = False
        self.script_text.highlighting_enabled = True
        self.script_text.highlight()
        self.update_ui_states()

    def add_script_line(self, line):
        self.after(0, lambda: (
            self.script_text.insert(tk.END, line + "\n"),
            self.script_text.see(tk.END)
        ))

    def on_record_move(self, x, y):
        if self.is_mouse_down:
            last_x, last_y = self.last_recorded_pos
            if abs(x - last_x) > 5 or abs(y - last_y) > 5:
                current_time = time.time()
                wait_time = current_time - self.last_event_time
                self.add_script_line(f"WAIT,{wait_time:.4f}")
                self.add_script_line(f"MOVE,{x},{y}")
                self.last_event_time = current_time
                self.last_recorded_pos = (x, y)

    def on_record_click(self, x, y, button, pressed):
        wait_time = time.time() - self.last_event_time
        self.add_script_line(f"WAIT,{wait_time:.4f}")
        event = "DOWN" if pressed else "UP"
        self.add_script_line(f"{event},{x},{y},{button.name}")
        self.is_mouse_down = pressed
        self.last_event_time = time.time()
        if not pressed:
            self.add_script_line("\n# --- New Action ---")

    def on_record_press(self, key):
        wait_time = time.time() - self.last_event_time
        self.add_script_line(f"WAIT,{wait_time:.4f}")
        self.add_script_line(f"KEY_DOWN,{self.get_key_name(key)}")
        self.last_event_time = time.time()

    def on_record_release(self, key):
        wait_time = time.time() - self.last_event_time
        self.add_script_line(f"WAIT,{wait_time:.4f}")
        self.add_script_line(f"KEY_UP,{self.get_key_name(key)}")
        self.last_event_time = time.time()

    def schedule_playback(self):
        try:
            delay = int(self.schedule_var.get())
            if delay <= 0: return
            self.macro_status_var.set(f"Playback scheduled in {delay} seconds...")
            self.after(delay * 1000, self.start_playback)
        except ValueError:
            self.macro_status_var.set("Invalid schedule time.")

    def toggle_playback(self):
        if self.is_playing:
            self.stop_macro_playback()
        else:
            self.start_playback()

    def start_playback(self):
        script = self.script_text.get("1.0", tk.END)
        if not script.strip(): return
        try:
            repeats = int(self.repeat_var.get())
        except ValueError:
            return
        self.is_playing = True
        self.macro_stop_event.clear()
        self.update_ui_states()
        self.macro_thread = threading.Thread(target=self.run_macro, args=(script, repeats))
        self.macro_thread.start()

    def stop_macro_playback(self):
        if not self.is_playing: return
        self.macro_stop_event.set()

    def stop_all_macro_activity(self):
        if self.is_recording: self.stop_recording()
        if self.is_playing: self.stop_macro_playback()

    def run_macro(self, script, repeats):
        mouse_controller = mouse.Controller()
        keyboard_controller = keyboard.Controller()
        speed_multiplier = self.playback_speed_var.get()
        commands = [line.strip() for line in script.split('\n') if line.strip() and not line.strip().startswith('#')]
        total_commands = len(commands)

        loop_count = 0
        while repeats == 0 or loop_count < repeats:
            if self.macro_stop_event.is_set(): break
            for i, command in enumerate(commands):
                if self.macro_stop_event.is_set(): break
                progress = ((i + 1) / total_commands)
                self.after(0, self.macro_progress.set, progress)

                parts = command.split(',')
                action = parts[0].upper()
                try:
                    if action == "WAIT":
                        time.sleep(float(parts[1]) / speed_multiplier)
                    elif action in ("DOWN", "UP"):
                        x, y, button_name = int(parts[1]), int(parts[2]), parts[3]
                        button = mouse.Button.left if button_name == 'left' else mouse.Button.right
                        mouse_controller.position = (x, y)
                        time.sleep(0.01)
                        if action == "DOWN":
                            mouse_controller.press(button)
                        else:
                            mouse_controller.release(button)
                    elif action == "MOVE":
                        x, y = int(parts[1]), int(parts[2])
                        mouse_controller.position = (x, y)
                        time.sleep(0.001)
                    elif action in ("KEY_DOWN", "KEY_UP"):
                        key_name = parts[1]
                        key = self.parse_key(key_name)
                        if action == "KEY_DOWN":
                            keyboard_controller.press(key)
                        else:
                            keyboard_controller.release(key)
                    elif action == "WAIT_PIXEL":
                        x, y, r, g, b = map(int, parts[1:])
                        self.wait_for_pixel(x, y, (r, g, b))
                except Exception as e:
                    self.after(0, self.macro_status_var.set, f"Status: Error - {e}")
                    self.macro_stop_event.set()
            else:
                loop_count += 1
                continue
            break

        self.is_playing = False
        self.after(0, self.update_ui_states)
        self.after(0, self.macro_progress.set, 0)

    def wait_for_pixel(self, x, y, expected_color):
        with mss.mss() as sct:
            monitor = {"top": y, "left": x, "width": 1, "height": 1}
            while not self.macro_stop_event.is_set():
                img = sct.grab(monitor)
                pixel = Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX").getpixel((0, 0))
                if pixel == expected_color: break
                time.sleep(0.1)

    def get_pixel_color(self):
        self.withdraw()
        self.location_listener = mouse.Listener(on_click=self.on_pixel_select)
        self.location_listener.start()

    def on_pixel_select(self, x, y, button, pressed):
        if pressed:
            with mss.mss() as sct:
                monitor = {"top": y, "left": x, "width": 1, "height": 1}
                img = sct.grab(monitor)
                pixel = Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX").getpixel((0, 0))
                r, g, b = pixel
            self.add_script_line(f"WAIT_PIXEL,{x},{y},{r},{g},{b}")
            self.deiconify()
            messagebox.showinfo("Pixel Captured",
                                f"Color grabbed and added to script!\n\nCoordinates: ({x}, {y})\nRGB: ({r}, {g}, {b})")
            return False

    def load_script(self):
        filepath = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")])
        if filepath:
            with open(filepath, 'r') as f:
                self.script_text.delete("1.0", tk.END)
                self.script_text.insert("1.0", f.read())

    def save_script(self):
        filepath = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text Files", "*.txt")])
        if filepath:
            with open(filepath, 'w') as f:
                f.write(self.script_text.get("1.0", tk.END))

    def get_key_name(self, key):
        try:
            return key.char
        except AttributeError:
            return key.name

    def parse_key(self, key_name):
        if len(key_name) == 1:
            return key_name
        else:
            return getattr(keyboard.Key, key_name)

    def set_hotkey_mode(self, key_type):
        self.hotkey_to_set = key_type
        status_text = f"Press any key to set the '{key_type}' hotkey..."
        if key_type == 'clicker':
            self.clicker_status_var.set(status_text)
        else:
            self.macro_status_var.set(status_text)
        self.update_ui_states()

    def on_global_press(self, key):
        # Emergency universal stop using the custom mapped stop key
        if key == self.stop_hotkey:
            self.stop_clicker()
            self.stop_all_macro_activity()
            self.show_status_message("STOPPED BY HOTKEY")
            return

        if self.hotkey_to_set:
            key_name = self.get_key_name(key)
            if self.hotkey_to_set == 'clicker':
                self.clicker_hotkey = key
                self.clicker_hotkey_var.set(key_name)
            elif self.hotkey_to_set == 'record':
                self.record_hotkey = key
                self.record_hotkey_var.set(key_name)
            elif self.hotkey_to_set == 'play':
                self.play_hotkey = key
                self.play_hotkey_var.set(key_name)
            elif self.hotkey_to_set == 'stop':
                self.stop_hotkey = key
                self.stop_hotkey_var.set(key_name)

            self.hotkey_to_set = None
            self.update_ui_states()
            return

        if self.is_recording:
            self.on_record_press(key)
            return

        if key == self.clicker_hotkey:
            if self.is_clicking:
                self.stop_clicker()
            else:
                self.start_clicker()
        elif key == self.record_hotkey:
            self.toggle_recording()
        elif key == self.play_hotkey:
            self.toggle_playback()

    def on_global_release(self, key):
        if self.is_recording:
            self.on_record_release(key)

    def show_status_message(self, message, duration=2000):
        if self.status_message_id: self.after_cancel(self.status_message_id)
        self.clicker_status_var.set(message)
        self.status_message_id = self.after(duration, self.update_ui_states)

    def update_ui_states(self):
        is_busy = self.is_clicking or self.is_recording or self.is_playing or self.hotkey_to_set

        # Clicker UI States
        clicker_state = "disabled" if is_busy else "normal"
        self.start_button.configure(state="disabled" if self.is_clicking else clicker_state)
        self.stop_button.configure(state="normal" if self.is_clicking else "disabled")

        loc_button_state = "disabled" if is_busy or self.click_location_mode.get() == 0 else "normal"
        self.set_loc_button.configure(state=loc_button_state)

        for w in [self.interval_entry, self.loc_mode_current, self.loc_mode_specific, self.x_entry, self.y_entry,
                  self.set_clicker_hotkey_button]:
            w.configure(state=clicker_state)

        if not self.hotkey_to_set:
            clicker_status = "Running..." if self.is_clicking else "Stopped"
            self.clicker_status_var.set(f"Status: {clicker_status} | Hotkey: {self.get_key_name(self.clicker_hotkey)}")

        # Macro UI States
        macro_busy_state = "disabled" if self.is_recording or self.is_playing or self.hotkey_to_set else "normal"
        self.script_text.configure(state="disabled" if self.is_playing else "normal")

        for w in [self.repeat_entry, self.load_button, self.save_button, self.schedule_button, self.schedule_entry,
                  self.speed_scale, self.clear_button, self.get_pixel_button]:
            w.configure(state=macro_busy_state)

        if not self.hotkey_to_set:
            if self.is_recording:
                self.macro_status_var.set("Status: Recording...")
            elif self.is_playing:
                self.macro_status_var.set("Status: Playing...")
            else:
                self.macro_status_var.set("Status: Idle")

    def on_closing(self):
        self.clicker_stop_event.set()
        self.macro_stop_event.set()
        if self.global_listener: self.global_listener.stop()
        if self.recording_listener: self.recording_listener.stop()
        self.destroy()


if __name__ == "__main__":
    app = AutoClickerApp()
    app.mainloop()
