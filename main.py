import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import requests
import socket
import xml.etree.ElementTree as ET
import json
import os
import speech_recognition as sr

class RokuController:
    def __init__(self, ip_address=None):
        self.ip_address = ip_address
        if not self.ip_address:
            self.ip_address = self.discover_roku()
        self.base_url = f"http://{self.ip_address}:8060"
        self.app_list = []
        self.device_info = {}
        self.get_app_list()
        self.get_device_info()
        
    def discover_roku(self):
        print("Searching for Roku devices on your network...")
        SSDP_DISCOVER = (
            'M-SEARCH * HTTP/1.1\r\n' +
            'HOST: 239.255.255.250:1900\r\n' +
            'MAN: "ssdp:discover"\r\n' +
            'ST: roku:ecp\r\n' +
            'MX: 3\r\n\r\n'
        )
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(5)
        
        try:
            sock.sendto(SSDP_DISCOVER.encode(), ('239.255.255.250', 1900))
            
            start_time = time.time()
            while time.time() - start_time < 5:
                try:
                    data, addr = sock.recvfrom(1024)
                    response = data.decode('utf-8')
                    
                    for line in response.split('\r\n'):
                        if line.lower().startswith('location:'):
                            url = line.split(' ')[1].strip()
                            ip = url.split('//')[1].split(':')[0]
                            print(f"Found Roku device at {ip}")
                            sock.close()
                            return ip
                except socket.timeout:
                    continue
                
            print("No Roku devices found automatically.")
            return None
        except Exception as e:
            print(f"Error during device discovery: {e}")
            return None
        finally:
            sock.close()
    
    def send_keypress(self, key):
        url = f"{self.base_url}/keypress/{key}"
        try:
            response = requests.post(url)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            print(f"Error sending '{key}' command to Roku")
            return False
    
    def launch_app(self, app_id):
        url = f"{self.base_url}/launch/{app_id}"
        try:
            response = requests.post(url)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            print(f"Error launching app {app_id}")
            return False

    def get_app_list(self):
        url = f"{self.base_url}/query/apps"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                root = ET.fromstring(response.text)
                self.app_list = []
                for app in root.findall('.//app'):
                    app_id = app.get('id')
                    app_name = app.text
                    self.app_list.append((app_id, app_name))
                return True
            return False
        except requests.exceptions.RequestException:
            print("Error getting app list")
            return False
        except ET.ParseError:
            print("Error parsing app list XML")
            return False

    def get_device_info(self):
        url = f"{self.base_url}/query/device-info"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                root = ET.fromstring(response.text)
                for child in root:
                    self.device_info[child.tag] = child.text
                return True
            return False
        except requests.exceptions.RequestException:
            print("Error getting device info")
            return False
        except ET.ParseError:
            print("Error parsing device info XML")
            return False

class CommandHistory:
    def __init__(self, history_file="command_history.json"):
        self.history_file = history_file
        self.items = []
        self.load_history()
    
    def load_history(self):
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r') as f:
                    self.items = json.load(f)
            except json.JSONDecodeError:
                self.items = []
        else:
            self.items = []
    
    def save_history(self):
        with open(self.history_file, 'w') as f:
            json.dump(self.items, f)
    
    def add_item(self, action, status, details=""):
        item = {
            "action": action,
            "status": status,
            "details": details,
            "timestamp": time.strftime("%m-%d-%Y %I:%M:%S %p")
        
        }
        self.items.append(item)
        self.save_history()
        return len(self.items) - 1
    
    def clear_history(self):
        self.items = []
        self.save_history()

class VoiceRecognizer:
    def __init__(self, callback):
        self.recognizer = sr.Recognizer()
        self.callback = callback
        self.listening = False
        self.thread = None
    
    def start_listening(self):
        if self.listening:
            return
        
        self.listening = True
        self.thread = threading.Thread(target=self.listen_loop, daemon=True)
        self.thread.start()
        return True
    
    def stop_listening(self):
        self.listening = False
        if self.thread:
            self.thread.join(timeout=1)
            self.thread = None
    
    def listen_loop(self):
        while self.listening:
            try:
                with sr.Microphone() as source:
                    self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                    audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=5)
                
                try:
                    text = self.recognizer.recognize_google(audio)
                    if text:
                        self.callback(text.lower())
                except sr.UnknownValueError:
                    pass
                except sr.RequestError as e:
                    print(f"Could not request results; {e}")
            except Exception as e:
                print(f"Error in voice recognition: {e}")
                time.sleep(1)

class ThemeManager:
    def __init__(self, root):
        self.root = root
        self.dark_mode = False
        
        self.light_theme = {
            'bg': '#f0f0f0',
            'fg': '#000000',
            'button_bg': '#e0e0e0',
            'frame_bg': '#f5f5f5',
            'treeview_bg': '#ffffff',
            'treeview_fg': '#000000',
            'entry_bg': '#ffffff',
            'select_bg': '#0078d7',
            'select_fg': '#ffffff'
        }
        
        self.dark_theme = {
            'bg': '#2e2e2e',
            'fg': '#ffffff',
            'button_bg': '#3c3c3c',
            'frame_bg': '#363636',
            'treeview_bg': '#2a2a2a',
            'treeview_fg': '#ffffff',
            'entry_bg': '#3c3c3c',
            'select_bg': '#0078d7',
            'select_fg': '#ffffff'
        }
        
        self.apply_theme(self.light_theme)
        
    def toggle_theme(self):
        self.dark_mode = not self.dark_mode
        if self.dark_mode:
            self.apply_theme(self.dark_theme)
        else:
            self.apply_theme(self.light_theme)
        return self.dark_mode
        
    def apply_theme(self, theme):
        style = ttk.Style()
        style.theme_use('default')
        
        style.configure('TFrame', background=theme['bg'])
        style.configure('TLabel', background=theme['bg'], foreground=theme['fg'])
        style.configure('TButton', background=theme['button_bg'])
        style.configure('TEntry', fieldbackground=theme['entry_bg'])
        style.configure('TLabelframe', background=theme['bg'])
        style.configure('TLabelframe.Label', background=theme['bg'], foreground=theme['fg'])
        
        style.configure('Treeview', 
                        background=theme['treeview_bg'], 
                        foreground=theme['treeview_fg'],
                        fieldbackground=theme['treeview_bg'])
        
        style.map('Treeview', 
                 background=[('selected', theme['select_bg'])],
                 foreground=[('selected', theme['select_fg'])])
        
        style.configure('TCombobox', background=theme['entry_bg'], fieldbackground=theme['entry_bg'])
        
        self.root.configure(background=theme['bg'])

class RokuGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("ROKU CONTROL !!!!")
        self.root.geometry("800x600")
        self.root.minsize(1200, 700)
        
        self.roku = None
        self.history = CommandHistory()
        self.voice = None
        self.voice_button_var = tk.StringVar(value="Start Voice Control")
        
        self.theme_manager = ThemeManager(self.root)
        self.dark_mode_var = tk.StringVar(value="🌙 Dark Mode")
        
        self.setup_ui()
        
    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill=tk.X, pady=5)
        
        theme_button = ttk.Button(top_frame, textvariable=self.dark_mode_var, command=self.toggle_dark_mode)
        theme_button.pack(side=tk.RIGHT, padx=5)
        
        control_panel = ttk.Frame(main_frame)
        control_panel.pack(fill=tk.X, pady=5)
        
        conn_frame = ttk.LabelFrame(control_panel, text="Roku Connection", padding="10")
        conn_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Label(conn_frame, text="Roku IP:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.ip_var = tk.StringVar()
        ttk.Entry(conn_frame, textvariable=self.ip_var, width=15).grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)
        ttk.Button(conn_frame, text="Connect", command=self.connect_roku).grid(row=0, column=2, padx=5, pady=5)
        ttk.Button(conn_frame, text="Auto-Discover", command=self.auto_discover).grid(row=0, column=3, padx=5, pady=5)
        
        voice_frame = ttk.LabelFrame(control_panel, text="Voice Control", padding="10")
        voice_frame.pack(side=tk.RIGHT, fill=tk.X, padx=(10, 0))
        
        self.voice_status_var = tk.StringVar(value="Voice control inactive")
        ttk.Label(voice_frame, textvariable=self.voice_status_var).pack(fill=tk.X, pady=2)
        
        self.voice_button = ttk.Button(voice_frame, textvariable=self.voice_button_var, command=self.toggle_voice_control)
        self.voice_button.pack(fill=tk.X, pady=2)
        
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        content_left_frame = ttk.Frame(content_frame)
        content_left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        log_frame = ttk.LabelFrame(content_left_frame, text="Command History", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        
        self.setup_log_ui(log_frame)
        
        tv_info_frame = ttk.LabelFrame(content_left_frame, text="TV Information", padding="10")
        tv_info_frame.pack(fill=tk.X, expand=False)
        
        self.setup_tv_info_ui(tv_info_frame)
        
        controls_frame = ttk.LabelFrame(content_frame, text="Roku Controls", padding="10")
        controls_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        self.setup_controls_ui(controls_frame)
        
        self.status_var = tk.StringVar(value="Not connected")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM, pady=5)
    
    def setup_tv_info_ui(self, parent):
        self.tv_info_vars = {
            'model_name': tk.StringVar(value="Model: Not connected"),
            'serial_number': tk.StringVar(value="Serial: Not connected"),
            'software_version': tk.StringVar(value="Software: Not connected"),
            'network_type': tk.StringVar(value="Network: Not connected"),
            'screen_size': tk.StringVar(value="Screen Size: Not connected"),
            'uptime': tk.StringVar(value="Uptime: Not connected")
        }
        
        info_frame = ttk.Frame(parent)
        info_frame.pack(fill=tk.X, expand=True)
        
        for i, (key, var) in enumerate(self.tv_info_vars.items()):
            col = i % 3
            row = i // 3
            ttk.Label(info_frame, textvariable=var).grid(row=row, column=col, padx=10, pady=5, sticky=tk.W)
        
        ttk.Button(parent, text="Refresh TV Info", command=self.refresh_tv_info).pack(pady=5)
    
    def refresh_tv_info(self):
        if not self.roku:
            return
        
        self.status_var.set("Refreshing TV information...")
        self.history.add_item("Refresh TV Info", "Started", "Retrieving device information")
        self.refresh_history()
        
        def info_thread():
            try:
                if self.roku.get_device_info():
                    info = self.roku.device_info
                    
                    self.root.after(0, lambda: self.tv_info_vars['model_name'].set(f"Model: {info.get('model-name', 'Unknown')}"))
                    self.root.after(0, lambda: self.tv_info_vars['serial_number'].set(f"Serial: {info.get('serial-number', 'Unknown')}"))
                    self.root.after(0, lambda: self.tv_info_vars['software_version'].set(f"Software: {info.get('software-version', 'Unknown')}"))
                    self.root.after(0, lambda: self.tv_info_vars['network_type'].set(f"Network: {info.get('network-type', 'Unknown')}"))
                    self.root.after(0, lambda: self.tv_info_vars['screen_size'].set(f"Screen Size: {info.get('screen-size', 'Unknown')}"))
                    
                    uptime_seconds = int(info.get('uptime', 0))
                    hours, remainder = divmod(uptime_seconds, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    uptime_str = f"{hours}h {minutes}m {seconds}s"
                    self.root.after(0, lambda: self.tv_info_vars['uptime'].set(f"Uptime: {uptime_str}"))
                    
                    self.root.after(0, lambda: self.status_var.set("TV information updated"))
                    self.root.after(0, lambda: self.history.add_item("Refresh TV Info", "Success", "Device information updated"))
                else:
                    self.root.after(0, lambda: self.status_var.set("Failed to get TV information"))
                    self.root.after(0, lambda: self.history.add_item("Refresh TV Info", "Failed", "Could not retrieve device information"))
            except Exception as e:
                self.root.after(0, lambda: self.status_var.set(f"Error getting TV info: {str(e)}"))
                self.root.after(0, lambda: self.history.add_item("Refresh TV Info", "Error", str(e)))
            finally:
                self.root.after(0, self.refresh_history)
        
        threading.Thread(target=info_thread, daemon=True).start()
    
    def toggle_dark_mode(self):
        is_dark = self.theme_manager.toggle_theme()
        if is_dark:
            self.dark_mode_var.set("☀️ Light Mode")
        else:
            self.dark_mode_var.set("🌙 Dark Mode")
    
    def setup_log_ui(self, parent):
        buttons_frame = ttk.Frame(parent)
        buttons_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(buttons_frame, text="Clear History", command=self.clear_history).pack(side=tk.RIGHT, padx=2)
        
        list_frame = ttk.Frame(parent)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        columns = ('timestamp', 'action', 'status', 'details')
        self.history_tree = ttk.Treeview(list_frame, columns=columns, show='headings')
        self.history_tree.heading('timestamp', text='Time')
        self.history_tree.heading('action', text='Action')
        self.history_tree.heading('status', text='Status')
        self.history_tree.heading('details', text='Details')
        
        self.history_tree.column('timestamp', width=150)
        self.history_tree.column('action', width=100)
        self.history_tree.column('status', width=80)
        self.history_tree.column('details', width=200)
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.history_tree.yview)
        self.history_tree.configure(yscroll=scrollbar.set)
        
        self.history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.refresh_history()
        
    def setup_controls_ui(self, parent):
        remote_frame = ttk.Frame(parent)
        remote_frame.pack(fill=tk.BOTH, expand=True)
        
        power_home_frame = ttk.Frame(remote_frame)
        power_home_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(power_home_frame, text="Power", command=lambda: self.send_key("Power")).pack(side=tk.LEFT, padx=5)
        ttk.Button(power_home_frame, text="Home", command=lambda: self.send_key("Home")).pack(side=tk.LEFT, padx=5)
        ttk.Button(power_home_frame, text="Back", command=lambda: self.send_key("Back")).pack(side=tk.LEFT, padx=5)
        
        nav_frame = ttk.Frame(remote_frame)
        nav_frame.pack(pady=10)
        
        ttk.Button(nav_frame, text="▲", width=3, command=lambda: self.send_key("Up")).grid(row=0, column=1, pady=2)
        ttk.Button(nav_frame, text="◄", width=3, command=lambda: self.send_key("Left")).grid(row=1, column=0, padx=2)
        ttk.Button(nav_frame, text="OK", width=3, command=lambda: self.send_key("Select")).grid(row=1, column=1, padx=2)
        ttk.Button(nav_frame, text="►", width=3, command=lambda: self.send_key("Right")).grid(row=1, column=2, padx=2)
        ttk.Button(nav_frame, text="▼", width=3, command=lambda: self.send_key("Down")).grid(row=2, column=1, pady=2)
        
        playback_frame = ttk.Frame(remote_frame)
        playback_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(playback_frame, text="⏮", width=3, command=lambda: self.send_key("Rev")).pack(side=tk.LEFT, padx=2)
        ttk.Button(playback_frame, text="⏯", width=3, command=lambda: self.send_key("Play")).pack(side=tk.LEFT, padx=2)
        ttk.Button(playback_frame, text="⏭", width=3, command=lambda: self.send_key("Fwd")).pack(side=tk.LEFT, padx=2)
        
        vol_frame = ttk.Frame(remote_frame)
        vol_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(vol_frame, text="Vol+", command=lambda: self.send_key("VolumeUp")).pack(side=tk.LEFT, padx=5)
        ttk.Button(vol_frame, text="Vol-", command=lambda: self.send_key("VolumeDown")).pack(side=tk.LEFT, padx=5)
        ttk.Button(vol_frame, text="Mute", command=lambda: self.send_key("VolumeMute")).pack(side=tk.LEFT, padx=5)
        
        apps_frame = ttk.LabelFrame(remote_frame, text="Apps")
        apps_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        self.app_var = tk.StringVar()
        self.app_dropdown = ttk.Combobox(apps_frame, textvariable=self.app_var, state="readonly")
        self.app_dropdown.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(apps_frame, text="Launch App", command=self.launch_selected_app).pack(pady=5)
        
        quick_frame = ttk.Frame(apps_frame)
        quick_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(quick_frame, text="Netflix", command=lambda: self.launch_app("12")).pack(side=tk.LEFT, padx=2)
        ttk.Button(quick_frame, text="YouTube", command=lambda: self.launch_app("837")).pack(side=tk.LEFT, padx=2)
        ttk.Button(quick_frame, text="Hulu", command=lambda: self.launch_app("2285")).pack(side=tk.LEFT, padx=2)
    
    def clear_history(self):
        self.history.clear_history()
        self.refresh_history()
    
    def refresh_history(self):
        self.history_tree.delete(*self.history_tree.get_children())
        
        for i, item in enumerate(self.history.items):
            self.history_tree.insert('', 'end', iid=str(i), values=(
                item['timestamp'],
                item['action'],
                item['status'],
                item['details']
            ))
    
    def auto_discover(self):
        self.status_var.set("Searching for Roku devices...")
        self.history.add_item("Auto-Discover", "Started", "Searching for Roku devices")
        self.refresh_history()
        
        def discover_thread():
            try:
                temp_roku = RokuController(None)
                if temp_roku.ip_address:
                    self.ip_var.set(temp_roku.ip_address)
                    self.root.after(0, lambda: self.status_var.set(f"Found Roku at {temp_roku.ip_address}"))
                    self.root.after(0, lambda: self.history.add_item("Auto-Discover", "Success", f"Found Roku at {temp_roku.ip_address}"))
                    self.connect_roku()
                else:
                    self.root.after(0, lambda: self.status_var.set("No Roku devices found"))
                    self.root.after(0, lambda: self.history.add_item("Auto-Discover", "Failed", "No Roku devices found"))
                    self.root.after(0, lambda: messagebox.showinfo("Auto-Discover", "No Roku devices found. Please enter the IP address manually."))
            except Exception as e:
                self.root.after(0, lambda: self.status_var.set(f"Error: {str(e)}"))
                self.root.after(0, lambda: self.history.add_item("Auto-Discover", "Error", str(e)))
            finally:
                self.root.after(0, self.refresh_history)
        
        threading.Thread(target=discover_thread, daemon=True).start()
        
    def connect_roku(self):
        ip = self.ip_var.get().strip()
        
        if not ip:
            messagebox.showerror("Error", "Please enter an IP address or use Auto-Discover")
            self.history.add_item("Connect", "Failed", "No IP address provided")
            self.refresh_history()
            return
            
        self.status_var.set(f"Connecting to {ip}...")
        self.history.add_item("Connect", "Started", f"Connecting to {ip}")
        self.refresh_history()
        
        def connect_thread():
            try:
                self.roku = RokuController(ip)
                if not self.roku.get_app_list():
                    self.root.after(0, lambda: self.status_var.set("Failed to connect to Roku device"))
                    self.root.after(0, lambda: self.history.add_item("Connect", "Failed", f"Could not get app list from {ip}"))
                    return
                    
                self.root.after(0, self.update_app_dropdown)
                self.root.after(0, self.refresh_tv_info)
                self.root.after(0, lambda: self.status_var.set(f"Connected to Roku at {self.roku.ip_address}"))
                self.root.after(0, lambda: self.history.add_item("Connect", "Success", f"Connected to Roku at {self.roku.ip_address}"))
            except Exception as e:
                self.root.after(0, lambda: self.status_var.set(f"Connection error: {str(e)}"))
                self.root.after(0, lambda: self.history.add_item("Connect", "Error", str(e)))
            finally:
                self.root.after(0, self.refresh_history)
        
        threading.Thread(target=connect_thread, daemon=True).start()
        
    def update_app_dropdown(self):
        if not self.roku:
            return
            
        app_options = [f"{app_name} ({app_id})" for app_id, app_name in self.roku.app_list]
        self.app_dropdown['values'] = app_options
        if app_options:
            self.app_dropdown.current(0)
            
    def launch_selected_app(self):
        if not self.roku:
            self.status_var.set("Not connected to any Roku device")
            self.history.add_item("Launch App", "Failed", "Not connected to any Roku device")
            self.refresh_history()
            return
            
        selected = self.app_var.get()
        if not selected:
            return
            
        app_id = selected.split('(')[-1].rstrip(')')
        app_name = selected.split(' (')[0]
        self.launch_app(app_id, app_name)
        
    def launch_app(self, app_id, app_name=None):
        if not self.roku:
            self.status_var.set("Not connected to any Roku device")
            self.history.add_item("Launch App", "Failed", "Not connected to any Roku device")
            self.refresh_history()
            return
        
        if app_name is None:
            for id, name in self.roku.app_list:
                if id == app_id:
                    app_name = name
                    break
            if app_name is None:
                app_name = f"App ID {app_id}"
            
        self.status_var.set(f"Launching {app_name}...")
        self.history.add_item("Launch App", "Started", f"Launching {app_name} (ID: {app_id})")
        self.refresh_history()
        
        def launch_thread():
            try:
                result = self.roku.launch_app(app_id)
                if result:
                    self.root.after(0, lambda: self.status_var.set(f"Launched {app_name}"))
                    self.root.after(0, lambda: self.history.add_item("Launch App", "Success", f"Launched {app_name} (ID: {app_id})"))
                else:
                    self.root.after(0, lambda: self.status_var.set(f"Failed to launch {app_name}"))
                    self.root.after(0, lambda: self.history.add_item("Launch App", "Failed", f"Failed to launch {app_name} (ID: {app_id})"))
            except Exception as e:
                self.root.after(0, lambda: self.status_var.set(f"Error: {str(e)}"))
                self.root.after(0, lambda: self.history.add_item("Launch App", "Error", str(e)))
            finally:
                self.root.after(0, self.refresh_history)
            
        threading.Thread(target=launch_thread, daemon=True).start()
        
    def send_key(self, key):
        if not self.roku:
            self.status_var.set("Not connected to any Roku device")
            self.history.add_item("Send Key", "Failed", f"{key}: Not connected to any Roku device")
            self.refresh_history()
            return
            
        self.history.add_item("Send Key", "Started", f"Sending {key} command")
        self.refresh_history()
        self.refresh_history()
            
        def key_thread():
            try:
                if self.roku.send_keypress(key):
                    self.root.after(0, lambda: self.status_var.set(f"Sent {key} command"))
                    self.root.after(0, lambda: self.history.add_item("Send Key", "Success", f"Sent {key} command"))
                else:
                    self.root.after(0, lambda: self.status_var.set(f"Failed to send {key} command"))
                    self.root.after(0, lambda: self.history.add_item("Send Key", "Failed", f"Failed to send {key} command"))
            except Exception as e:
                self.root.after(0, lambda: self.status_var.set(f"Error: {str(e)}"))
                self.root.after(0, lambda: self.history.add_item("Send Key", "Error", str(e)))
            finally:
                self.root.after(0, self.refresh_history)
                
        threading.Thread(target=key_thread, daemon=True).start()
    
    def toggle_voice_control(self):
        if not self.voice:
            try:
                self.voice = VoiceRecognizer(self.process_voice_command)
                self.start_voice_control()
            except Exception as e:
                messagebox.showerror("Voice Control Error", f"Could not initialize voice control: {str(e)}")
                self.history.add_item("Voice Control", "Error", f"Initialization failed: {str(e)}")
                self.voice = None
                self.refresh_history()
        else:
            if self.voice_button_var.get() == "Start Voice Control":
                self.start_voice_control()
            else:
                self.stop_voice_control()
    
    def start_voice_control(self):
        if not self.voice:
            return
            
        self.history.add_item("Voice Control", "Started", "Voice recognition started")
        self.refresh_history()
        
        try:
            if self.voice.start_listening():
                self.voice_button_var.set("Stop Voice Control")
                self.voice_status_var.set("Voice control active - speak commands")
                self.status_var.set("Voice control active")
            else:
                self.voice_status_var.set("Voice control failed to start")
                self.status_var.set("Voice control failed to start")
        except Exception as e:
            self.history.add_item("Voice Control", "Error", f"Start failed: {str(e)}")
            self.voice_status_var.set("Voice control failed to start")
            self.status_var.set(f"Voice control error: {str(e)}")
            self.refresh_history()
    
    def stop_voice_control(self):
        if not self.voice:
            return
            
        self.voice.stop_listening()
        self.voice_button_var.set("Start Voice Control")
        self.voice_status_var.set("Voice control inactive")
        self.status_var.set("Voice control stopped")
        
        self.history.add_item("Voice Control", "Stopped", "Voice recognition stopped")
        self.refresh_history()
    
    def process_voice_command(self, command):
        if not self.roku:
            self.root.after(0, lambda: self.status_var.set("Voice command received but not connected to Roku"))
            self.root.after(0, lambda: self.history.add_item("Voice Command", "Failed", f"'{command}': Not connected to Roku"))
            self.root.after(0, self.refresh_history)
            return
        
        self.root.after(0, lambda: self.history.add_item("Voice Command", "Received", f"'{command}'"))
        self.root.after(0, self.refresh_history)

        if "open" in command or "launch" in command or "start" in command:
            app_name = None
            

            for app_id, name in self.roku.app_list:
                if name.lower() in command:
                    app_name = name
                    self.root.after(0, lambda id=app_id, name=name: self.launch_app(id, name))
                    break
            
            if not app_name:
                if "youtube" in command:
                    self.root.after(0, lambda: self.launch_app("837", "YouTube"))
                elif "netflix" in command:
                    self.root.after(0, lambda: self.launch_app("12", "Netflix"))
                elif "hulu" in command:
                    self.root.after(0, lambda: self.launch_app("2285", "Hulu"))
                elif "prime" in command or "amazon" in command:
                    self.root.after(0, lambda: self.launch_app("13", "Amazon Prime Video"))
                elif "disney" in command:
                    self.root.after(0, lambda: self.launch_app("291097", "Disney+"))
                elif "hbo" in command:
                    self.root.after(0, lambda: self.launch_app("61322", "HBO Max"))
                else:
                    self.root.after(0, lambda: self.status_var.set(f"App not recognized in voice command: '{command}'"))
                    self.root.after(0, lambda: self.history.add_item("Voice Command", "Failed", f"App not recognized: '{command}'"))
            
            return
        
        if "up" in command:
            self.root.after(0, lambda: self.send_key("Up"))
        elif "down" in command:
            self.root.after(0, lambda: self.send_key("Down"))
        elif "left" in command:
            self.root.after(0, lambda: self.send_key("Left"))
        elif "right" in command:
            self.root.after(0, lambda: self.send_key("Right"))
        elif "select" in command or "enter" in command or "ok" in command:
            self.root.after(0, lambda: self.send_key("Select"))
        elif "back" in command or "return" in command:
            self.root.after(0, lambda: self.send_key("Back"))
        elif "home" in command or "menu" in command:
            self.root.after(0, lambda: self.send_key("Home"))
        

        elif "play" in command or "resume" in command:
            self.root.after(0, lambda: self.send_key("Play"))
        elif "pause" in command:
            self.root.after(0, lambda: self.send_key("Play"))
        elif "forward" in command or "skip" in command:
            self.root.after(0, lambda: self.send_key("Fwd"))
        elif "rewind" in command or "back" in command:
            self.root.after(0, lambda: self.send_key("Rev"))
        
        elif "volume up" in command or "louder" in command:
            self.root.after(0, lambda: self.send_key("VolumeUp"))
        elif "volume down" in command or "quieter" in command:
            self.root.after(0, lambda: self.send_key("VolumeDown"))
        elif "mute" in command:
            self.root.after(0, lambda: self.send_key("VolumeMute"))
        
        elif "power" in command or "turn off" in command or "shutdown" in command:
            self.root.after(0, lambda: self.send_key("Power"))
        
        else:
            self.root.after(0, lambda: self.status_var.set(f"Unrecognized voice command: '{command}'"))
            self.root.after(0, lambda: self.history.add_item("Voice Command", "Unrecognized", f"'{command}'"))
            self.root.after(0, self.refresh_history)

def main():
    root = tk.Tk()
    app = RokuGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
