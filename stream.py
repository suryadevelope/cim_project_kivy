import signal
import subprocess
import sys
from threading import Thread, Lock
import time
import pygame
import socket
import tkinter as tk
import json
import ast
from kivy.clock import Clock
from kivy.event import EventDispatcher
from kivymd.toast import toast
from collections import deque
from kivy.properties import NumericProperty, ObjectProperty, StringProperty

# Firebase imports
try:
    from firebase_control import FirebaseControl
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False
    print("Firebase not available in stream.py")

# Network Configuration
Stream_2_IP = "192.168.144.16"
Stream_2_PORT = 5005
LISTEN_IP = "0.0.0.0"  # Listen on all interfaces
LISTEN_PORT = 5006

print("main.py started")

def is_port_in_use(port):
    """Check if a port is in use"""
    try:
        output = subprocess.check_output(["netstat", "-tuln"])
        lines = output.decode("utf-8").split("\n")
        for line in lines:
            parts = line.split()
            if len(parts) >= 4:
                if parts[3] == f"0.0.0.0:{port}":
                    return True  # Port is in use
        return False  # Port is not in use
    except subprocess.CalledProcessError as e:
        print(f"Error checking port {port}: {e}")
        return None  # Error occurred

def close_port_if_running(port):
    """Close port if it's in use"""
    try:
        subprocess.run(["fuser", "-k", f"{port}/tcp"])
        print(f"Closed port {port}.")
    except Exception as e:
        print(f"Error closing port {port}: {e}")

# Port management
port_status = is_port_in_use(LISTEN_PORT)
if port_status is None:
    print(f"An error occurred while checking port {LISTEN_PORT}.")
elif port_status:
    print(f"Port {LISTEN_PORT} is in use.")
    close_port_if_running(LISTEN_PORT)
else:
    print(f"Port {LISTEN_PORT} is not in use.")

# Initialize the two UDP sockets
Stream2_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
Listen_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
Listen_socket.settimeout(1.0)  # Add timeout for better error handling

try:
    Listen_socket.bind((LISTEN_IP, LISTEN_PORT))
    print(f"UDP listener bound to {LISTEN_IP}:{LISTEN_PORT}")
except Exception as e:
    print(f"Error binding UDP socket: {e}")

# Define a signal handler function
def signal_handler(sig, frame):
    print('Closing socket...')
    try:
        Listen_socket.close()
        Stream2_socket.close()
    except:
        pass
    sys.exit(0)

# Register the signal handler for termination signals
signal.signal(signal.SIGINT, signal_handler)  # Handles Ctrl+C
signal.signal(signal.SIGTERM, signal_handler) # Handles termination signal

class Stream(EventDispatcher):
    update_event = NumericProperty(0)
    update_utils = StringProperty("{}")

    dataconfirm = {
        "compass": False,
        "jetsonvoltage": 0
    }

    videosections = None
    compasswidget = None
    control_mode = "hardware"  # Default control mode
    firebase_control = None
    data_lock = Lock()  # Thread safety for data updates
    
    # UI update optimization
    _ui_update_pending = False
    _last_ui_update = 0
    _ui_update_interval = 1.0 / 30.0  # 30 FPS max
    _data_buffer = deque(maxlen=10)  # Buffer for data updates
    _joystick_buffer = deque(maxlen=5)  # Buffer for joystick updates
    
    def __init__(self, **kwargs):
        super(Stream, self).__init__(**kwargs)
        
        # Initialize Firebase control if available
        if FIREBASE_AVAILABLE:
            try:
                from firebase_config import FIREBASE_CONFIG
                self.firebase_control = FirebaseControl(FIREBASE_CONFIG)
                print("Firebase control initialized in Stream")
            except Exception as e:
                print(f"Error initializing Firebase control: {e}")
                self.firebase_control = None
        
        # Start UDP listener thread
        self.listener_thread = Thread(target=self.listen_udp, daemon=True)
        self.listener_thread.start()
        
        # Start joystick thread if in hardware mode
        if self.control_mode == "hardware":
            self.joystick_thread = Thread(target=self.runjoystick, daemon=True)
            self.joystick_thread.start()
        
        # Schedule UI updates at a consistent rate
        Clock.schedule_interval(self._process_ui_updates, self._ui_update_interval)

    def _process_ui_updates(self, dt):
        """Process pending UI updates at a consistent frame rate"""
        current_time = time.time()
        
        # Process data updates
        if self._data_buffer and current_time - self._last_ui_update >= self._ui_update_interval:
            try:
                # Get the most recent data
                latest_data = self._data_buffer[-1]
                with self.data_lock:
                    self.update_utils = json.dumps(latest_data)
                    self.update_event += 1
                self._last_ui_update = current_time
                self._data_buffer.clear()  # Clear processed data
            except Exception as e:
                print(f"Error processing UI updates: {e}")

    def _queue_data_update(self, data):
        """Queue data for UI update instead of immediate update"""
        try:
            with self.data_lock:
                data['_timestamp'] = time.time()
                self._data_buffer.append(data)
        except Exception as e:
            print(f"Error queuing data update: {e}")

    def set_control_mode(self, mode):
        """Set control mode (hardware or internet)"""
        with self.data_lock:
            self.control_mode = mode
            print(f"Stream control mode set to: {mode}")
            
            # Update Firebase control mode if available
            if self.firebase_control:
                self.firebase_control.set_control_mode(mode)

    def get_control_mode(self):
        """Get current control mode"""
        with self.data_lock:
            return self.control_mode

    def send_joystick_to_firebase(self, udp_command_string):
        """Send joystick data to Firebase ONLY if in internet mode"""
        if self.firebase_control and self.control_mode == "internet":  # type: ignore
            try:
                # Send the UDP command string directly to Firebase (same as socket)
                joystick_data = {
                    "udp_command": udp_command_string,
                    "timestamp": time.time()
                }
                self.firebase_control.send_joystick_data(joystick_data)  # type: ignore
                print(f"✅ Sent joystick data to Firebase (internet mode): {joystick_data}")
            except Exception as e:
                print(f"❌ Error sending joystick data to Firebase: {e}")
        else:
            if self.control_mode == "hardware":
                print(f"ℹ️ Skipping Firebase send: Currently in hardware mode, using socket communication")
            elif not self.firebase_control:
                print(f"ℹ️ Skipping Firebase send: Firebase control not available")

    def send_joystick_via_socket(self, udp_command_string):
        """Send joystick data via socket ONLY if in hardware mode"""
        if self.control_mode == "hardware":
            try:
                # Send via UDP socket
                self.send_udp_packet(Stream2_socket, udp_command_string, Stream_2_IP, Stream_2_PORT)
                print(f"✅ Sent joystick data via socket (hardware mode): {udp_command_string}")
                return True
            except Exception as e:
                print(f"❌ Error sending joystick data via socket: {e}")
                return False
        else:
            print(f"ℹ️ Skipping socket send: Currently in internet mode, using Firebase communication")
            return False

    def send_joystick_data(self, udp_command_string):
        """
        Send joystick data based on current control mode
        
        Args:
            udp_command_string (str): UDP command string to send
            
        Returns:
            bool: True if data was sent successfully, False otherwise
        """
        try:
            if self.control_mode == "hardware":
                # Hardware mode: send via socket only
                return self.send_joystick_via_socket(udp_command_string)
            elif self.control_mode == "internet":
                # Internet mode: send via Firebase only
                return self.send_joystick_to_firebase(udp_command_string) is not None
            else:
                print(f"❌ Unknown control mode: {self.control_mode}")
                return False
        except Exception as e:
            print(f"❌ Error in send_joystick_data: {e}")
            return False

    def parse_udp_command(self, udp_command):
        """Parse UDP command string to joystick data"""
        try:
            # Format: "@speed,direction,holdobject,centerliftknob,lift_speed"
            if udp_command.startswith("@"):
                parts = udp_command[1:].split(",")
                if len(parts) >= 5:
                    speed = int(parts[0])
                    direction = int(parts[1])
                    holdobject = int(parts[2])
                    centerliftknob = int(parts[3])
                    lift_speed = float(parts[4])
                    
                    # Convert to joystick format
                    return {
                        "speed": speed,
                        "direction": direction,
                        "holdobject": holdobject,
                        "centerliftknob": centerliftknob,
                        "lift_speed": lift_speed,
                        "timestamp": time.time()
                    }
        except Exception as e:
            print(f"Error parsing UDP command: {e}")
        
        return {}

    def updatevideoview(self, view):
        """Update video view"""
        if self.videosections and view < len(self.videosections):
            self.videosections[view].texture = None

    def map_input_to_movement(self, value, dead_zone=0.1):
        """Apply dead zone correction and map input to movement"""
        if abs(value) < dead_zone:
            return 0
        movement = int(value * 255)
        return max(-255, min(255, movement))

    def send_udp_packet(self, socket, data, ip, port):
        """Send UDP packet with error handling"""
        try:
            socket.sendto(data.encode(), (ip, port))
            return True
        except Exception as e:
            print(f"Error sending UDP packet: {e}")
            return False

    def map_value(self, value, in_min, in_max, out_min, out_max):
        """Map the value from the input range to the output range"""
        return (value - in_min) * (out_max - out_min) / (in_max - in_min) + out_min

    def runjoystick(self): 
        """Initialize the pygame library and joysticks with optimized update rate"""
        try:
            pygame.init()
            pygame.joystick.init()
            
            joystick_count = pygame.joystick.get_count()
            if joystick_count == 0:
                print("No joystick connected.")
                return
            
            joystick = pygame.joystick.Joystick(0)
            joystick.init()
            
            print(f"Joystick initialized: {joystick.get_name()}")
            
            last_update = 0
            update_interval = 0.05  # 20Hz update rate for joystick (reduced from 50Hz)
            
            while True:
                pygame.event.pump()
                
                current_time = time.time()
                if current_time - last_update < update_interval:
                    time.sleep(0.001)  # Small sleep to reduce CPU usage
                    continue
                
                # Read joystick values
                x_axis = joystick.get_axis(0)  # Left/Right
                y_axis = joystick.get_axis(1)  # Forward/Backward
                lift_speed = joystick.get_axis(2) if joystick.get_numaxes() > 2 else 0
                
                # Read buttons
                clicked = joystick.get_button(0)  # Button 0
                release = joystick.get_button(1)  # Button 1
                
                # Read hat (D-pad)
                hat = joystick.get_hat(0) if joystick.get_numhats() > 0 else (0, 0)
                centerliftknob = hat[1]  # Up/Down from hat
                
                # Map joystick values to movement
                x_movement = self.map_input_to_movement(x_axis, dead_zone=0.2)
                y_movement = self.map_input_to_movement(y_axis, dead_zone=0.2)
                
                # Determine direction and speed
                speed = 0
                direction = "115"  # Stop
                holdobject = -1
                
                # Handle button states
                if clicked and not release:
                    holdobject = 1
                elif clicked and release:
                    holdobject = 0
                
                # Determine direction based on movement
                if y_movement < 0 and x_movement < 0:
                    direction = "7"  # Forward-left
                    speed = abs(y_movement)
                elif y_movement < 0 and x_movement > 0:
                    direction = "9"  # Forward-right
                    speed = abs(y_movement)
                elif y_movement > 0 and x_movement < 0:
                    direction = "1"  # Backward-left
                    speed = abs(y_movement)
                elif y_movement > 0 and x_movement > 0:
                    direction = "3"  # Backward-right
                    speed = abs(y_movement)
                elif y_movement > 0:
                    direction = "5"  # Backward
                    speed = abs(y_movement)
                elif y_movement < 0:
                    direction = "8"  # Forward
                    speed = abs(y_movement)
                elif x_movement > 0:
                    direction = "6"  # Right
                    speed = abs(x_movement)
                elif x_movement < 0:
                    direction = "4"  # Left
                    speed = abs(x_movement)
                else:
                    speed = 0
                    direction = "115"
                
                # Format the command string
                data = "@{},{},{},{},{}".format(speed, direction, holdobject, centerliftknob, lift_speed)
                
                # Send data based on current control mode
                self.send_joystick_data(data)
                
                last_update = current_time
                
        except Exception as e:
            print(f"Error in joystick thread: {e}")
        finally:
            pygame.quit()

    def listen_udp(self):
        """Listen for UDP data from rover with improved error handling"""
        print("Starting UDP listener thread...")
        
        while True:
            try:
                data, addr = Listen_socket.recvfrom(1024)
                if not data:
                    continue
                
                compassdata = data.decode('utf-8', errors='ignore')
                
                if compassdata and compassdata != 'None':
                    self.process_udp_data(compassdata, addr)
                    
            except socket.timeout:
                # Timeout is expected, continue listening
                continue
            except Exception as e:
                print(f"Error in UDP listener: {e}")
                time.sleep(1)  # Wait before retrying

    def process_udp_data(self, data, addr):
        """Process UDP data with proper validation and error handling"""
        try:
            # Try to parse as JSON first (new format)
            try:
                json_data = json.loads(data)
                self.process_json_data(json_data)
            except json.JSONDecodeError:
                # Fallback to old format
                self.process_legacy_data(data)
                
        except Exception as e:
            print(f"Error processing UDP data: {e}")

    def process_json_data(self, json_data):
        """Process JSON format data with optimized UI updates"""
        try:
            # Handle new Firebase data structure
            if "sensors" in json_data and "current" in json_data["sensors"]:
                sensors_data = json_data["sensors"]["current"]
                
                # Parse utils data
                utils_str = sensors_data.get("utils", "")
                utils_data = self.parse_utils_string(utils_str)
                
                # Create complete data structure
                complete_data = {
                    "sensors": {
                        "current": {
                            "gps": sensors_data.get("gps", {}),
                            "compass": sensors_data.get("compass", "0"),
                            "autonomous": sensors_data.get("autonomous", {}),
                            "utils": utils_str,
                            "packet_count": sensors_data.get("packet_count", 0),
                            "timestamp": sensors_data.get("timestamp", time.time())
                        }
                    },
                    "system": {
                        "status": json_data.get("system", {}).get("status", {})
                    },
                    "control": json_data.get("control", {}),
                    "remote_control": json_data.get("remote_control", {}),
                    "test": json_data.get("test", {})
                }
                
                # Queue data for UI update instead of immediate update
                self._queue_data_update(complete_data)
                
                # Update compass widget immediately (this is lightweight)
                self.update_compass_widget(sensors_data.get("compass", "0"))
                
            else:
                # Legacy JSON structure
                complete_data = {
                    "gps": json_data.get("gps", {}),
                    "compass": json_data.get("compass", "0"),
                    "autonomous": json_data.get("autonomous", {}),
                    **self.parse_utils_string(json_data.get("utils", ""))
                }
                
                # Queue data for UI update
                self._queue_data_update(complete_data)
                
                self.update_compass_widget(json_data.get("compass", "0"))
                
        except Exception as e:
            print(f"Error processing JSON data: {e}")

    def process_legacy_data(self, data):
        """Process legacy format data with optimized UI updates"""
        try:
            if data.startswith("#"):
                parts = data[1:].split("=")
                if len(parts) == 5:
                    legacy_data = {
                        "armstate": parts[0],
                        "batvoltage": parts[1],
                        "jetsonvoltage": parts[2],
                        "gps": parts[4],
                        "compass": parts[3]
                    }
                    
                    # Queue data for UI update
                    self._queue_data_update(legacy_data)
                    
                    self.update_compass_widget(parts[3])
                else:
                    print("Legacy data format incorrect")
        except Exception as e:
            print(f"Error processing legacy data: {e}")

    def parse_utils_string(self, utils_str):
        """Parse utils string with error handling"""
        try:
            if utils_str and utils_str.strip() and utils_str.startswith("#"):
                parts = utils_str[1:].split("=")
                if len(parts) >= 3:
                    return {
                        "armstate": parts[0],
                        "batvoltage": parts[1],
                        "jetsonvoltage": parts[2]
                    }
        except Exception as e:
            print(f"Error parsing utils string: {e}")
        
        return {
            "armstate": "0",
            "batvoltage": "0.0",
            "jetsonvoltage": "0.0"
        }

    def update_compass_widget(self, compass_value):
        """Update compass widget with error handling"""
        try:
            if compass_value and compass_value != "None" and self.compasswidget is not None:
                compass_angle = float(compass_value)
                self.compasswidget.update_compass(compass_angle)
                self.dataconfirm["compass"] = True
        except (ValueError, TypeError) as e:
            print(f"Error updating compass widget: {e}")

    def setcompasswidget(self, compasswidget=None):
        """Set compass widget reference"""
        self.compasswidget = compasswidget

    def set_ui_update_rate(self, fps):
        """Set the UI update rate in FPS"""
        if fps > 0:
            self._ui_update_interval = 1.0 / fps
            # Reschedule the UI update timer
            Clock.unschedule(self._process_ui_updates)
            Clock.schedule_interval(self._process_ui_updates, self._ui_update_interval)
            print(f"UI update rate set to {fps} FPS")

    def get_ui_update_rate(self):
        """Get current UI update rate in FPS"""
        return int(1.0 / self._ui_update_interval) if self._ui_update_interval > 0 else 0

    def sync_control_mode_from_firebase(self):
        """
        Synchronize local control mode with Firebase system status
        This ensures mode changes in Firebase are immediately reflected locally
        """
        try:
            if not self.firebase_control:
                print("ℹ️ Cannot sync mode: Firebase control not available")
                return False
            
            # Use the Firebase control's sync method
            if hasattr(self.firebase_control, 'sync_mode_from_firebase'):
                success = self.firebase_control.sync_mode_from_firebase()
                if success:
                    # Update local mode to match Firebase
                    new_mode = self.firebase_control.get_control_mode()
                    if new_mode != self.control_mode:
                        print(f"🔄 Mode synchronized from Firebase: {self.control_mode} -> {new_mode}")
                        self.control_mode = new_mode
                        return True
                return success
            else:
                print("ℹ️ Firebase control doesn't have sync_mode_from_firebase method")
                return False
                
        except Exception as e:
            print(f"❌ Error syncing control mode from Firebase: {e}")
            return False

    def get_control_mode_status(self):
        """
        Get detailed control mode status for debugging
        """
        try:
            status = {
                "local_mode": self.control_mode,
                "firebase_available": self.firebase_control is not None,
                "firebase_mode": None,
                "firebase_connected": False
            }
            
            if self.firebase_control:
                status["firebase_mode"] = self.firebase_control.get_control_mode()
                status["firebase_connected"] = self.firebase_control.is_firebase_connected()
            
            return status
        except Exception as e:
            print(f"❌ Error getting control mode status: {e}")
            return {"error": str(e)}