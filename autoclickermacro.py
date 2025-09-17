import time
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pynput import mouse, keyboard
import mss
from PIL import Image


# A custom Text widget with line numbers and syntax highlighting
class TextLineNumbers(tk.Canvas):
    def __init__(self, *args, **kwargs):
        tk.Canvas.__init__(self, *args, **kwargs)
        self.textwidget = None

    def attach(self, text_widget):
        self.textwidget = text_widget

    def redraw(self, *args):
        '''Redraw line numbers'''
        self.delete("all")

        i = self.textwidget.index("@0,0")
        while True:
            dline = self.textwidget.dlineinfo(i)
            if dline is None: break
            y = dline[1]
            linenum = str(i).split(".")[0]
            self.create_text(2, y, anchor="nw", text=linenum, fill="#6c757d")
            i = self.textwidget.index("%s+1line" % i)


class CustomText(tk.Text):
    def __init__(self, *args, **kwargs):
        tk.Text.__init__(self, *args, **kwargs)

        self.tag_config("MOVE", foreground="#007bff")
        self.tag_config("WAIT", foreground="#6c757d")
        self.tag_config("DOWN", foreground="#28a745")
        self.tag_config("UP", foreground="#dc3545")
        self.tag_config("KEY_DOWN", foreground="#17a2b8")
        self.tag_config("KEY_UP", foreground="#fd7e14")
        self.tag_config("WAIT_PIXEL", foreground="#ffc107")
        self.tag_config("COMMENT", foreground="#6a737d")

        self.bind("<<Modified>>", self._on_change)
        self.bind("<Configure>", self._on_change)

    def _on_change(self, event):
        self.highlight()
        self.event_generate("<<Change>>")

    def highlight(self):
        # Basic highlighter, could be optimized for very large files
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


class AutoClickerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Auto-Clicker Pro")
        self.root.geometry("750x750")  # Increased height to prevent cutoff
        self.root.minsize(600, 500)

        # --- Initialize all instance attributes ---
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

        self.clicker_hotkey = keyboard.KeyCode(char="+")
        self.record_hotkey = keyboard.Key.f10
        self.play_hotkey = keyboard.Key.f12

        # --- Main UI Setup ---
        # Create widgets first
        notebook = ttk.Notebook(root)
        notebook.pack(pady=10, padx=10, fill="both", expand=True)

        self.clicker_frame = ttk.Frame(notebook)
        self.macro_frame = ttk.Frame(notebook)

        notebook.add(self.clicker_frame, text='Auto-Clicker')
        notebook.add(self.macro_frame, text='Macro Recorder')

        self.create_clicker_tab(self.clicker_frame)
        self.create_macro_tab(self.macro_frame)

        # Now that widgets exist, set up styles
        self.setup_styles()

        # Final setup
        self.global_listener = keyboard.Listener(on_press=self.on_global_press, on_release=self.on_global_release)
        self.global_listener.start()

        self.root.attributes("-topmost", True)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.update_ui_states()

    def setup_styles(self):
        self.style = ttk.Style(self.root)
        self.style.theme_use('clam')
        self.set_theme('light')

    def set_theme(self, mode):
        bg_color = "#f0f0f0" if mode == 'light' else "#2e2e2e"
        fg_color = "black" if mode == 'light' else "white"
        entry_bg = "white" if mode == 'light' else "#3c3c3c"

        self.root.configure(background=bg_color)
        self.style.configure("TFrame", background=bg_color)
        self.style.configure("TLabel", background=bg_color, foreground=fg_color)
        self.style.configure("TLabelframe", background=bg_color, bordercolor=fg_color)
        self.style.configure("TLabelframe.Label", background=bg_color, foreground=fg_color)
        self.style.configure("TCheckbutton", background=bg_color, foreground=fg_color)
        self.style.configure("TRadiobutton", background=bg_color, foreground=fg_color)
        self.style.map("TCheckbutton", indicatorcolor=[('selected', fg_color)], foreground=[('active', '#007bff')])
        self.style.configure("TEntry", fieldbackground=entry_bg, foreground=fg_color, insertcolor=fg_color)
        self.style.configure("TButton", background="#e0e0e0" if mode == 'light' else "#555", foreground=fg_color)
        self.style.map("TButton", background=[('active', '#007bff')])
        self.script_text.config(background=entry_bg, foreground=fg_color, insertbackground=fg_color)

    # --- TAB 1: AUTO-CLICKER ---
    def create_clicker_tab(self, parent):
        parent.pack(fill="both", expand=True, padx=10, pady=10)
        self.click_location_mode = tk.IntVar(value=0)
        self.always_on_top_var = tk.BooleanVar(value=True)
        self.interval_var = tk.StringVar(value="0.5")
        self.x_var = tk.StringVar(value="100")
        self.y_var = tk.StringVar(value="100")
        self.clicker_hotkey_var = tk.StringVar(value="+")
        self.clicker_status_var = tk.StringVar()

        clicking_frame = ttk.LabelFrame(parent, text="Clicking Options", padding=10)
        clicking_frame.pack(fill="x", pady=5)
        clicking_frame.columnconfigure(1, weight=1)
        ttk.Label(clicking_frame, text="Interval (s):").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.interval_entry = ttk.Entry(clicking_frame, textvariable=self.interval_var, width=10)
        self.interval_entry.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        self.loc_mode_current = ttk.Radiobutton(clicking_frame, text="Click at current mouse position",
                                                variable=self.click_location_mode, value=0,
                                                command=self.update_ui_states)
        self.loc_mode_current.grid(row=1, column=0, columnspan=2, sticky="w", padx=5, pady=(5, 0))
        specific_loc_frame = ttk.Frame(clicking_frame)
        specific_loc_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=5, pady=(0, 5))
        self.loc_mode_specific = ttk.Radiobutton(specific_loc_frame, text="Click at specific location:",
                                                 variable=self.click_location_mode, value=1,
                                                 command=self.update_ui_states)
        self.loc_mode_specific.pack(side="left")
        self.set_loc_button = ttk.Button(specific_loc_frame, text="Set Location", command=self.prompt_for_location)
        self.set_loc_button.pack(side="right", padx=(5, 0))
        self.y_entry = ttk.Entry(specific_loc_frame, textvariable=self.y_var, width=5)
        self.y_entry.pack(side="right")
        ttk.Label(specific_loc_frame, text="Y:").pack(side="right", padx=(5, 2))
        self.x_entry = ttk.Entry(specific_loc_frame, textvariable=self.x_var, width=5)
        self.x_entry.pack(side="right")
        ttk.Label(specific_loc_frame, text="X:").pack(side="right", padx=(5, 2))
        settings_frame = ttk.LabelFrame(parent, text="Settings", padding=10)
        settings_frame.pack(fill="x", pady=5)
        ttk.Label(settings_frame, text="Hotkey:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.clicker_hotkey_entry = ttk.Entry(settings_frame, textvariable=self.clicker_hotkey_var, width=10,
                                              state="readonly")
        self.clicker_hotkey_entry.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        self.set_clicker_hotkey_button = ttk.Button(settings_frame, text="Set",
                                                    command=lambda: self.set_hotkey_mode('clicker'))
        self.set_clicker_hotkey_button.grid(row=0, column=2, padx=5, pady=5)
        self.dark_mode_var = tk.BooleanVar(value=False)
        self.dark_mode_check = ttk.Checkbutton(settings_frame, text="Dark Mode", variable=self.dark_mode_var,
                                               command=lambda: self.set_theme(
                                                   'dark' if self.dark_mode_var.get() else 'light'))
        self.dark_mode_check.grid(row=0, column=3, sticky="w", padx=10)
        self.always_on_top_check = ttk.Checkbutton(settings_frame, text="Window always on top",
                                                   variable=self.always_on_top_var, command=self.toggle_always_on_top)
        self.always_on_top_check.grid(row=1, column=0, columnspan=3, sticky="w", padx=5, pady=5)
        control_frame = ttk.Frame(parent)
        control_frame.pack(fill="x", pady=(15, 5))
        control_frame.columnconfigure((0, 1), weight=1)
        self.start_button = ttk.Button(control_frame, text="▶ Start", command=self.start_clicker)
        self.start_button.grid(row=0, column=0, sticky="ew", padx=5)
        self.stop_button = ttk.Button(control_frame, text="⏹ Stop", command=self.stop_clicker, state=tk.DISABLED)
        self.stop_button.grid(row=0, column=1, sticky="ew", padx=5)
        ttk.Label(parent, textvariable=self.clicker_status_var, relief="sunken", padding=5).pack(fill="x",
                                                                                                 side="bottom")

    # --- TAB 2: MACRO RECORDER ---
    def create_macro_tab(self, parent):
        parent.pack(fill="both", expand=True)
        parent.rowconfigure(2, weight=1)
        parent.columnconfigure(0, weight=1)

        self.repeat_var = tk.StringVar(value="1")
        self.macro_status_var = tk.StringVar()
        self.record_hotkey_var = tk.StringVar(value=self.get_key_name(self.record_hotkey))
        self.play_hotkey_var = tk.StringVar(value=self.get_key_name(self.play_hotkey))
        self.playback_speed_var = tk.DoubleVar(value=1.0)
        self.schedule_var = tk.StringVar(value="0")

        controls_frame = ttk.LabelFrame(parent, text="Controls", padding=10)
        controls_frame.grid(row=0, column=0, sticky="ew", pady=5, padx=10)

        self.record_button = ttk.Button(controls_frame, text="⏺ Record", command=self.toggle_recording)
        self.record_button.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        self.play_button = ttk.Button(controls_frame, text="▶ Play", command=self.toggle_playback)
        self.play_button.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.stop_macro_button = ttk.Button(controls_frame, text="⏹ Stop", command=self.stop_all_macro_activity,
                                            state=tk.DISABLED)
        self.stop_macro_button.grid(row=0, column=2, padx=5, pady=5, sticky="ew")

        ttk.Label(controls_frame, text="Record Hotkey:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.record_hotkey_entry = ttk.Entry(controls_frame, textvariable=self.record_hotkey_var, state="readonly",
                                             width=10)
        self.record_hotkey_entry.grid(row=1, column=1, sticky="w", padx=5, pady=2)
        ttk.Button(controls_frame, text="Set", command=lambda: self.set_hotkey_mode('record')).grid(row=1, column=2,
                                                                                                    sticky="w", padx=5,
                                                                                                    pady=2)

        ttk.Label(controls_frame, text="Play Hotkey:").grid(row=2, column=0, sticky="w", padx=5, pady=2)
        self.play_hotkey_entry = ttk.Entry(controls_frame, textvariable=self.play_hotkey_var, state="readonly",
                                           width=10)
        self.play_hotkey_entry.grid(row=2, column=1, sticky="w", padx=5, pady=2)
        ttk.Button(controls_frame, text="Set", command=lambda: self.set_hotkey_mode('play')).grid(row=2, column=2,
                                                                                                  sticky="w", padx=5,
                                                                                                  pady=2)

        options_frame = ttk.LabelFrame(parent, text="Playback Options", padding=10)
        options_frame.grid(row=1, column=0, sticky="ew", pady=5, padx=10)
        ttk.Label(options_frame, text="Repeat:").pack(side="left", padx=5)
        self.repeat_entry = ttk.Entry(options_frame, textvariable=self.repeat_var, width=5)
        self.repeat_entry.pack(side="left")
        ttk.Label(options_frame, text="Speed:").pack(side="left", padx=(10, 0))
        self.speed_scale = ttk.Scale(options_frame, from_=0.1, to=3.0, variable=self.playback_speed_var,
                                     orient="horizontal")
        self.speed_scale.pack(side="left", padx=5)
        ttk.Label(options_frame, textvariable=self.playback_speed_var).pack(side="left")
        ttk.Label(options_frame, text="Schedule (sec):").pack(side="left", padx=(10, 0))
        self.schedule_entry = ttk.Entry(options_frame, textvariable=self.schedule_var, width=5)
        self.schedule_entry.pack(side="left", padx=5)
        self.schedule_button = ttk.Button(options_frame, text="Schedule Play", command=self.schedule_playback)
        self.schedule_button.pack(side="left")

        editor_frame = ttk.LabelFrame(parent, text="Macro Script", padding=10)
        editor_frame.grid(row=2, column=0, sticky="nsew", pady=5, padx=10)
        editor_frame.rowconfigure(0, weight=1)
        editor_frame.columnconfigure(0, weight=1)

        self.linenumbers = TextLineNumbers(editor_frame, width=30)
        self.linenumbers.pack(side="left", fill="y")
        self.script_text = CustomText(editor_frame, height=10, width=50, wrap="word", undo=True)
        self.script_text.pack(side="left", fill="both", expand=True)
        self.linenumbers.attach(self.script_text)

        scrollbar = ttk.Scrollbar(editor_frame, orient="vertical", command=self.script_text.yview)
        scrollbar.pack(side="right", fill="y")
        self.script_text.config(yscrollcommand=scrollbar.set)
        self.script_text.bind("<<Change>>", lambda e: self.linenumbers.redraw())
        self.script_text.bind("<<Modified>>", self.on_script_modify)

        file_frame = ttk.Frame(parent)
        file_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=5)
        self.load_button = ttk.Button(file_frame, text="📂 Load", command=self.load_script)
        self.load_button.pack(side="left")
        self.save_button = ttk.Button(file_frame, text="💾 Save", command=self.save_script)
        self.save_button.pack(side="left", padx=5)
        self.clear_button = ttk.Button(file_frame, text="🗑 Clear",
                                       command=lambda: self.script_text.delete("1.0", tk.END))
        self.clear_button.pack(side="left")
        self.get_pixel_button = ttk.Button(file_frame, text="Get Pixel Color", command=self.get_pixel_color)
        self.get_pixel_button.pack(side="left", padx=5)

        self.macro_progress = ttk.Progressbar(parent, orient='horizontal', mode='determinate')
        self.macro_progress.grid(row=4, column=0, sticky="ew", padx=10, pady=5)
        self.macro_status_var_label = ttk.Label(parent, textvariable=self.macro_status_var, relief="sunken")
        self.macro_status_var_label.grid(row=5, column=0, sticky="ew", padx=10, pady=(0, 10))

    # --- CLICKER LOGIC ---
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
        self.root.after(0, self.update_ui_states)

    def prompt_for_location(self):
        self.root.withdraw()
        self.location_listener = mouse.Listener(on_click=self.on_location_click)
        self.location_listener.start()

    def on_location_click(self, x, y, _button, pressed):
        if pressed:
            self.root.deiconify();
            self.root.lift()
            self.x_var.set(str(x));
            self.y_var.set(str(y))
            self.show_status_message(f"Location set to ({x}, {y})")
            if self.location_listener:
                self.location_listener.stop()
                self.location_listener = None
            return False

    # --- MACRO LOGIC ---
    def toggle_recording(self):
        if self.is_recording:
            self.stop_recording()
        else:
            self.start_recording()

    def start_recording(self):
        self.is_recording = True
        self.is_mouse_down = False
        self.script_text.delete("1.0", tk.END)
        self.last_event_time = time.time()
        self.update_ui_states()
        self.recording_listener = mouse.Listener(
            on_move=self.on_record_move,
            on_click=self.on_record_click
        )
        self.recording_listener.start()

    def stop_recording(self):
        if self.recording_listener:
            self.recording_listener.stop()
            self.recording_listener = None
        self.is_recording = False
        self.update_ui_states()

    def on_script_modify(self, event):
        self.script_dirty = True
        self.script_text.edit_modified(False)

    def add_script_line(self, line):
        self.root.after(0, lambda: (
            self.script_text.insert(tk.END, line + "\n"),
            self.script_text.see(tk.END)
        ))

    def on_record_move(self, x, y):
        if self.is_mouse_down:
            current_time = time.time()
            wait_time = current_time - self.last_event_time
            self.add_script_line(f"WAIT,{wait_time:.4f}")
            self.add_script_line(f"MOVE,{x},{y}")
            self.last_event_time = current_time

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
            self.root.after(delay * 1000, self.start_playback)
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

                progress = ((i + 1) / total_commands) * 100
                self.root.after(0, self.macro_progress.config, {'value': progress})

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
                    self.root.after(0, self.macro_status_var.set, f"Status: Error - {e}")
                    self.macro_stop_event.set()
            else:
                loop_count += 1
                continue
            break

        self.is_playing = False
        self.root.after(0, self.update_ui_states)
        self.root.after(0, self.macro_progress.config, {'value': 0})

    def wait_for_pixel(self, x, y, expected_color):
        with mss.mss() as sct:
            monitor = {"top": y, "left": x, "width": 1, "height": 1}
            while not self.macro_stop_event.is_set():
                img = sct.grab(monitor)
                pixel = Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX").getpixel((0, 0))
                if pixel == expected_color:
                    break
                time.sleep(0.1)

    def get_pixel_color(self):
        self.root.withdraw()
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
            self.root.deiconify()
            return False

    def load_script(self):
        if self.script_dirty:
            if not messagebox.askyesno("Unsaved Changes",
                                       "You have unsaved changes. Do you want to continue and discard them?"):
                return
        filepath = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")])
        if filepath:
            with open(filepath, 'r') as f:
                self.script_text.delete("1.0", tk.END)
                self.script_text.insert("1.0", f.read())
            self.script_dirty = False

    def save_script(self):
        filepath = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text Files", "*.txt")])
        if filepath:
            with open(filepath, 'w') as f:
                f.write(self.script_text.get("1.0", tk.END))
            self.script_dirty = False

    # --- GLOBAL & UI LOGIC ---
    def get_key_name(self, key):
        try:
            return key.char
        except AttributeError:
            return key.name

    def parse_key(self, key_name):
        # This is a simple parser. A more robust one would handle all special keys.
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

    def toggle_always_on_top(self):
        self.root.attributes("-topmost", self.always_on_top_var.get())

    def show_status_message(self, message, duration=2000):
        if self.status_message_id: self.root.after_cancel(self.status_message_id)
        self.clicker_status_var.set(message)
        self.status_message_id = self.root.after(duration, self.update_ui_states)

    def update_ui_states(self):
        is_busy = self.is_clicking or self.is_recording or self.is_playing or self.hotkey_to_set

        # --- Clicker Tab UI ---
        clicker_state = tk.DISABLED if is_busy else tk.NORMAL
        self.start_button.config(state=tk.DISABLED if self.is_clicking else clicker_state)
        self.stop_button.config(state=tk.NORMAL if self.is_clicking else tk.DISABLED)
        loc_button_state = tk.DISABLED if is_busy or self.click_location_mode.get() == 0 else tk.NORMAL
        self.set_loc_button.config(state=loc_button_state)
        for w in [self.interval_entry, self.loc_mode_current, self.loc_mode_specific, self.x_entry, self.y_entry,
                  self.clicker_hotkey_entry, self.set_clicker_hotkey_button, self.always_on_top_check,
                  self.dark_mode_check]:
            w.config(state=clicker_state if w is not self.clicker_hotkey_entry else "readonly")
        if not self.hotkey_to_set:
            clicker_status = "Running..." if self.is_clicking else "Stopped"
            self.clicker_status_var.set(f"Status: {clicker_status} | Hotkey: {self.get_key_name(self.clicker_hotkey)}")

        # --- Macro Tab UI ---
        self.record_button.config(state=tk.DISABLED if self.is_playing or self.hotkey_to_set else tk.NORMAL)
        self.play_button.config(state=tk.DISABLED if self.is_recording or self.hotkey_to_set else tk.NORMAL)
        self.stop_macro_button.config(state=tk.NORMAL if self.is_recording or self.is_playing else tk.DISABLED)
        script_box_state = tk.DISABLED if self.is_playing else tk.NORMAL
        self.script_text.config(state=script_box_state)
        macro_busy_state = tk.DISABLED if self.is_recording or self.is_playing or self.hotkey_to_set else tk.NORMAL
        for w in [self.repeat_entry, self.load_button, self.save_button, self.play_hotkey_entry,
                  self.record_hotkey_entry, self.schedule_button, self.schedule_entry, self.speed_scale,
                  self.clear_button, self.get_pixel_button]:
            w.config(
                state=macro_busy_state if w not in [self.play_hotkey_entry, self.record_hotkey_entry] else "readonly")

        if not self.hotkey_to_set:
            if self.is_recording:
                macro_status = "Status: Recording..."
            elif self.is_playing:
                macro_status = "Status: Playing..."
            else:
                macro_status = "Status: Idle"
            self.macro_status_var.set(macro_status)

    def on_closing(self):
        if self.script_dirty:
            if not messagebox.askyesno("Unsaved Changes",
                                       "You have unsaved changes. Do you want to quit without saving?"):
                return
        self.clicker_stop_event.set()
        self.macro_stop_event.set()
        if self.global_listener: self.global_listener.stop()
        if self.recording_listener: self.recording_listener.stop()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = AutoClickerApp(root)
    root.mainloop()
