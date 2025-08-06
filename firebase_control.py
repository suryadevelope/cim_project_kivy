import json
import threading
import time
from datetime import datetime
from kivy.clock import Clock
from kivy.properties import BooleanProperty, StringProperty

# Import configuration
try:
    from firebase_config import FIREBASE_CONFIG, FIREBASE_PATHS, ROVER_CONTROL_PARAMS
    print("Firebase config imported successfully")
except ImportError as e:
    print(f"Error importing firebase_config: {e}")
    # Fallback configuration if config file doesn't exist
    FIREBASE_CONFIG = {
        "apiKey": "your-api-key-here",
        "authDomain": "your-project-id.firebaseapp.com",
        "databaseURL": "https://your-project-id-default-rtdb.firebaseio.com",
        "projectId": "your-project-id",
        "storageBucket": "your-project-id.appspot.com",
        "messagingSenderId": "your-sender-id",
        "appId": "your-app-id"
    }
    FIREBASE_PATHS = {
        "joystick": "control/joystick",
        "autonomous": "control/autonomous", 
        "system_status": "system/status",
        "sensors": "sensors/current",
        "mission_commands": "control/autonomous",
        "navigation_status": "sensors/current/autonomous"
    }
    ROVER_CONTROL_PARAMS = {
        "joystick_deadzone": 0.1,
        "max_speed": 100.0,
        "update_frequency": 50,
        "udp_timeout": 1.0
    }

# Try to import pyrebase
try:
    from pyrebase import initialize_app
    print("Pyrebase imported successfully")
except ImportError as e:
    print(f"Error importing pyrebase: {e}")
    initialize_app = None

class FirebaseControl:
    def __init__(self, config):
        """
        Initialize Firebase control with configuration
        
        config: Firebase configuration dictionary
        """
        try:
            if initialize_app is None:
                raise ImportError("Pyrebase not available - initialize_app is None")
            
            print(f"Initializing Firebase with config: {config.get('projectId', 'unknown')}")
            
            # Initialize Firebase app
            self.firebase = initialize_app(config)
            print("Firebase app initialized")
            
            # Initialize database and auth
            self.db = self.firebase.database()
            self.auth = self.firebase.auth()
            print("Firebase database and auth initialized")
            
            # Control state
            self.control_mode = "hardware"  # "hardware" or "internet"
            self.is_connected = False
            self.last_heartbeat = None
            self.connection_lock = threading.Lock()
            
            # Rover control data
            self.joystick_data = {
                "x_axis": 0.0,
                "y_axis": 0.0,
                "lift_speed": 0.0,
                "clicked": False,
                "release": False,
                "centerliftknob": 0,
                "timestamp": time.time()
            }
            
            # Autonomous control data
            self.autonomous_data = {
                "run_status": False,
                "vh_autonomous": False,
                "wp_loaded_count": 0,
                "wp_number": None,
                "wp_distance": None,
                "compass_err": None
            }
            
            # Mission commands data (new structure)
            self.mission_commands = {
                "mission": [],
                "mission_count": 0,
                "status": "stop",  # "start", "stop", "pause"
                "timestamp": time.time()
            }
            
            # Navigation status data (new structure)
            self.navigation_status = {
                "active": False,
                "current_waypoint": 0,
                "distance_to_target": 0.0,
                "heading": 0.0,
                "speed": 0.0,
                "total_waypoints": 0,
                "timestamp": time.time()
            }
            
            # System status data
            self.system_status = {
                "control_mode": "hardware",
                "firebase_connected": False,
                "online": False,
                "last_heartbeat": None,
                "timestamp": time.time()
            }
            
            # Sensors data
            self.sensors_data = {
                "gps": {},
                "compass": "0",
                "autonomous": {},
                "utils": "",
                "packet_count": 0,
                "timestamp": time.time()
            }
            
            # Callback functions
            self.on_joystick_update = None
            self.on_autonomous_update = None
            self.on_mission_commands_update = None
            self.on_navigation_status_update = None
            self.on_system_update = None
            self.on_sensors_update = None
            
            # Stream listeners
            self.joystick_stream = None
            self.autonomous_stream = None
            self.mission_commands_stream = None
            self.navigation_status_stream = None
            self.system_stream = None
            self.sensors_stream = None
            
            # Test connection
            if self.test_connection():
                self.start_listeners()
            else:
                print("Firebase connection test failed")
                
        except Exception as e:
            print(f"Error initializing Firebase control: {e}")
            import traceback
            traceback.print_exc()
            self.is_connected = False

    def test_connection(self):
        """Test Firebase connection"""
        try:
            with self.connection_lock:
                # Try to read from database
                test_data = self.db.child("test").child("connection").get()
                if test_data.val() is not None:
                    # Update connection status
                    self.db.child("test").child("connection").update({
                        "status": "connected",
                        "timestamp": time.time()
                    })
                    self.is_connected = True
                    self.last_heartbeat = time.time()
                    print("Firebase connection test successful")
                    return True
                else:
                    # Create test entry
                    self.db.child("test").child("connection").set({
                        "status": "connected",
                        "timestamp": time.time()
                    })
                    self.is_connected = True
                    self.last_heartbeat = time.time()
                    print("Firebase connection test successful (created test entry)")
                    return True
        except Exception as e:
            print(f"Firebase connection test failed: {e}")
            self.is_connected = False
            return False

    def validate_autonomous_data(self, autonomous_data):
        """Validate autonomous data structure and content"""
        try:
            if not isinstance(autonomous_data, dict):
                print("Invalid autonomous data: not a dictionary")
                return False
            
            # Check if this is mission data (has mission field)
            if "mission" in autonomous_data:
                # This is mission data
                if not isinstance(autonomous_data["mission"], list):
                    print("Invalid mission data: mission must be a list")
                    return False
                
                # Validate mission points
                for i, point in enumerate(autonomous_data["mission"]):
                    if not isinstance(point, (list, tuple)) or len(point) < 2:
                        print(f"Invalid mission point {i}: must be list/tuple with at least 2 coordinates")
                        return False
                    try:
                        lat = float(point[0])
                        lon = float(point[1])
                        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                            print(f"Invalid mission point {i}: coordinates out of range")
                            return False
                    except (ValueError, TypeError):
                        print(f"Invalid mission point {i}: coordinates must be numeric")
                        return False
                
                # Validate status field
                if "status" in autonomous_data:
                    status = autonomous_data["status"]
                    if not isinstance(status, str) or status not in ["start", "stop", "pause"]:
                        print("Invalid mission data: status must be 'start', 'stop', or 'pause'")
                        return False
                
                return True
            
            # Check required fields for autonomous command data
            required_fields = ["run_status", "vh_autonomous", "wp_loaded_count"]
            for field in required_fields:
                if field not in autonomous_data:
                    print(f"Invalid autonomous data: missing required field '{field}'")
                    return False
            
            # Validate data types
            if not isinstance(autonomous_data["run_status"], bool):
                print("Invalid autonomous data: run_status must be boolean")
                return False
            
            if not isinstance(autonomous_data["vh_autonomous"], bool):
                print("Invalid autonomous data: vh_autonomous must be boolean")
                return False
            
            if not isinstance(autonomous_data["wp_loaded_count"], (int, float)):
                print("Invalid autonomous data: wp_loaded_count must be numeric")
                return False
            
            # Validate optional fields if present
            if "wp_number" in autonomous_data and not isinstance(autonomous_data["wp_number"], (int, float, type(None))):
                print("Invalid autonomous data: wp_number must be numeric or None")
                return False
            
            if "wp_distance" in autonomous_data and not isinstance(autonomous_data["wp_distance"], (int, float, type(None))):
                print("Invalid autonomous data: wp_distance must be numeric or None")
                return False
            
            if "compass_err" in autonomous_data and not isinstance(autonomous_data["compass_err"], (int, float, type(None))):
                print("Invalid autonomous data: compass_err must be numeric or None")
                return False
            
            return True
            
        except Exception as e:
            print(f"Error validating autonomous data: {e}")
            return False

    def validate_mission_data(self, mission_data):
        """Validate mission data structure"""
        try:
            if not isinstance(mission_data, dict):
                return False
            
            required_fields = ["mission", "mission_count", "status"]
            for field in required_fields:
                if field not in mission_data:
                    return False
            
            if not isinstance(mission_data["mission"], list):
                return False
            
            if not isinstance(mission_data["mission_count"], (int, float)):
                return False
            
            if mission_data["status"] not in ["start", "stop", "pause"]:
                return False
            
            return True
        except Exception as e:
            print(f"Error validating mission data: {e}")
            return False

    def validate_navigation_data(self, nav_data):
        """Validate navigation status data"""
        try:
            if not isinstance(nav_data, dict):
                return False
            
            required_fields = ["active", "current_waypoint", "distance_to_target", "heading", "speed", "total_waypoints"]
            for field in required_fields:
                if field not in nav_data:
                    return False
            
            if not isinstance(nav_data["active"], bool):
                return False
            
            if not isinstance(nav_data["current_waypoint"], (int, float)):
                return False
            
            if not isinstance(nav_data["distance_to_target"], (int, float)):
                return False
            
            if not isinstance(nav_data["heading"], (int, float)):
                return False
            
            if not isinstance(nav_data["speed"], (int, float)):
                return False
            
            if not isinstance(nav_data["total_waypoints"], (int, float)):
                return False
            
            return True
        except Exception as e:
            print(f"Error validating navigation data: {e}")
            return False

    def start_listeners(self):
        """Start Firebase listeners for real-time updates"""
        try:
            print("Starting Firebase listeners...")
            
            # Test connection first
            if not self.test_connection():
                raise Exception("Firebase connection test failed")
            
            # Listen for joystick data
            joystick_path = FIREBASE_PATHS["joystick"].split("/")
            print(f"Setting up joystick listener for path: {joystick_path}")
            self.joystick_stream = self.db.child(*joystick_path).stream(
                self.on_joystick_data_update
            )
            
            # Listen for autonomous data
            autonomous_path = FIREBASE_PATHS["autonomous"].split("/")
            print(f"Setting up autonomous listener for path: {autonomous_path}")
            self.autonomous_stream = self.db.child(*autonomous_path).stream(
                self.on_autonomous_data_update
            )
            
            # Listen for mission commands (new)
            mission_commands_path = FIREBASE_PATHS["mission_commands"].split("/")
            print(f"Setting up mission commands listener for path: {mission_commands_path}")
            self.mission_commands_stream = self.db.child(*mission_commands_path).stream(
                self.on_mission_commands_update
            )
            
            # Listen for navigation status (new)
            navigation_status_path = FIREBASE_PATHS["navigation_status"].split("/")
            print(f"Setting up navigation status listener for path: {navigation_status_path}")
            self.navigation_status_stream = self.db.child(*navigation_status_path).stream(
                self.on_navigation_status_update
            )
            
            # Listen for system status
            system_path = FIREBASE_PATHS["system_status"].split("/")
            print(f"Setting up system status listener for path: {system_path}")
            self.system_stream = self.db.child(*system_path).stream(
                self.on_system_status_update
            )
            
            # Listen for sensors data (new structure)
            sensors_path = FIREBASE_PATHS["sensors"].split("/")
            print(f"Setting up sensors listener for path: {sensors_path}")
            self.sensors_stream = self.db.child(*sensors_path).stream(
                self.on_sensors_data_update
            )
            
            self.is_connected = True
            self.update_system_status()
            print("Firebase listeners started successfully")
            
        except Exception as e:
            print(f"Error starting Firebase listeners: {e}")
            import traceback
            traceback.print_exc()
            self.is_connected = False
            # Try to reconnect after a delay
            print("Scheduling reconnection attempt in 5 seconds...")
            threading.Timer(5.0, self.start_listeners).start()

    def on_joystick_data_update(self, message):
        """Handle joystick data updates from Firebase"""
        try:
            if message['event'] == 'put':
                data = message['data']
                if data:
                    # Handle new structure where joystick might be nested
                    if isinstance(data, dict) and "joystick" in data:
                        joystick_data = data["joystick"]
                    else:
                        joystick_data = data
                    
                    # Update local data
                    with self.connection_lock:
                        self.joystick_data.update(joystick_data)
                        self.joystick_data["timestamp"] = time.time()
                    
                    # Trigger callback on main thread
                    if self.on_joystick_update:
                        Clock.schedule_once(lambda dt: self.on_joystick_update(joystick_data))
                    print(f"Joystick data updated: {joystick_data}")
        except Exception as e:
            print(f"Error handling joystick update: {e}")

    def on_autonomous_data_update(self, message):
        """Handle autonomous data updates from Firebase with enhanced validation"""
        try:
            if message['event'] == 'put':
                data = message['data']
                if data:
                    # Handle new structure where autonomous might be nested
                    if isinstance(data, dict) and "autonomous" in data:
                        autonomous_data = data["autonomous"]
                    else:
                        autonomous_data = data
                    
                    # Validate the autonomous data before processing
                    if self.validate_autonomous_data(autonomous_data):
                        # Update local data
                        with self.connection_lock:
                            self.autonomous_data.update(autonomous_data)
                            self.autonomous_data["timestamp"] = time.time()
                        
                        # Trigger callback on main thread
                        if self.on_autonomous_update:
                            Clock.schedule_once(lambda dt: self.on_autonomous_update(autonomous_data))
                        print(f"Autonomous data updated: {autonomous_data}")
                    else:
                        print(f"Invalid autonomous data received, ignoring: {autonomous_data}")
                else:
                    print("Empty autonomous data received")
        except Exception as e:
            print(f"Error handling autonomous update: {e}")
            import traceback
            traceback.print_exc()

    def on_system_status_update(self, message):
        """Handle system status updates from Firebase"""
        try:
            if message['event'] == 'put':
                data = message['data']
                if data:
                    # Handle new structure where system status might be nested
                    if isinstance(data, dict) and "status" in data:
                        system_data = data["status"]
                    else:
                        system_data = data
                    
                    # Update local data
                    with self.connection_lock:
                        self.system_status.update(system_data)
                        self.system_status["timestamp"] = time.time()
                    
                    # Trigger callback on main thread
                    if self.on_system_update:
                        Clock.schedule_once(lambda dt: self.on_system_update(system_data))
                    print(f"System status updated: {system_data}")
        except Exception as e:
            print(f"Error handling system status update: {e}")

    def on_sensors_data_update(self, message):
        """Handle sensors data updates from Firebase"""
        try:
            if message['event'] == 'put':
                data = message['data']
                if data:
                    # Handle new structure where sensors might be nested
                    if isinstance(data, dict) and "current" in data:
                        sensors_data = data["current"]
                    else:
                        sensors_data = data
                    
                    # Update local data
                    with self.connection_lock:
                        self.sensors_data.update(sensors_data)
                        self.sensors_data["timestamp"] = time.time()
                    
                    # Trigger callback on main thread
                    if self.on_sensors_update:
                        Clock.schedule_once(lambda dt: self.on_sensors_update(sensors_data))
                    print(f"Sensors data updated: {sensors_data}")
        except Exception as e:
            print(f"Error handling sensors update: {e}")

    def on_mission_commands_update(self, message):
        """Handle mission commands updates from Firebase"""
        try:
            if message['event'] == 'put':
                data = message['data']
                if data:
                    # Validate mission data
                    if self.validate_mission_data(data):
                        # Update local data
                        with self.connection_lock:
                            self.mission_commands.update(data)
                            self.mission_commands["timestamp"] = time.time()
                        
                        # Trigger callback on main thread
                        if self.on_mission_commands_update:
                            Clock.schedule_once(lambda dt: self.on_mission_commands_update(data))
                        print(f"Mission commands updated: {data}")
                    else:
                        print(f"Invalid mission data received, ignoring: {data}")
        except Exception as e:
            print(f"Error handling mission commands update: {e}")

    def on_navigation_status_update(self, message):
        """Handle navigation status updates from Firebase"""
        try:
            if message['event'] == 'put':
                data = message['data']
                if data:
                    # Validate navigation data
                    if self.validate_navigation_data(data):
                        # Update local data
                        with self.connection_lock:
                            self.navigation_status.update(data)
                            self.navigation_status["timestamp"] = time.time()
                        
                        # Trigger callback on main thread
                        if self.on_navigation_status_update:
                            Clock.schedule_once(lambda dt: self.on_navigation_status_update(data))
                        print(f"Navigation status updated: {data}")
                    else:
                        print(f"Invalid navigation data received, ignoring: {data}")
        except Exception as e:
            print(f"Error handling navigation status update: {e}")

    def send_joystick_data(self, joystick_data):
        """Send joystick data to Firebase"""
        try:
            with self.connection_lock:
                if not self.is_connected:
                    print("Firebase not connected, cannot send joystick data")
                    return False
                
                # Update timestamp
                joystick_data["timestamp"] = time.time()
                
                # Send to Firebase
                joystick_path = FIREBASE_PATHS["joystick"].split("/")
                self.db.child(*joystick_path).set(joystick_data)
                
                # Update local data
                self.joystick_data.update(joystick_data)
                
                print(f"Joystick data sent to Firebase: {joystick_data}")
                return True
                
        except Exception as e:
            print(f"Error sending joystick data: {e}")
            return False

    def send_autonomous_command(self, command_data):
        """Send autonomous command to Firebase"""
        try:
            with self.connection_lock:
                if not self.is_connected:
                    print("Firebase not connected, cannot send autonomous command")
                    return False
                
                # Validate command data
                if not self.validate_autonomous_data(command_data):
                    print("Invalid autonomous command data")
                    return False
                
                # Update timestamp
                command_data["timestamp"] = time.time()
                
                # Send to Firebase
                autonomous_path = FIREBASE_PATHS["autonomous"].split("/")
                self.db.child(*autonomous_path).set(command_data)
                
                # Update local data
                self.autonomous_data.update(command_data)
                
                print(f"Autonomous command sent to Firebase: {command_data}")
                return True
                
        except Exception as e:
            print(f"Error sending autonomous command: {e}")
            return False

    def ensure_connection(self):
        """Ensure Firebase connection is active"""
        try:
            with self.connection_lock:
                if not self.is_connected or (self.last_heartbeat and time.time() - self.last_heartbeat > 30):
                    print("Firebase connection lost, attempting to reconnect...")
                    return self.test_connection()
                return True
        except Exception as e:
            print(f"Error ensuring connection: {e}")
            return False

    def send_autonomous_mission(self, mission_data):
        """Send autonomous mission to Firebase"""
        try:
            with self.connection_lock:
                if not self.is_connected:
                    print("Firebase not connected, cannot send mission")
                    return False
                
                # Validate mission data
                if not self.validate_mission_data(mission_data):
                    print("Invalid mission data")
                    return False
                
                # Update timestamp
                mission_data["timestamp"] = time.time()
                
                # Send to Firebase
                mission_path = FIREBASE_PATHS["mission_commands"].split("/")
                self.db.child(*mission_path).set(mission_data)
                
                # Update local data
                self.mission_commands.update(mission_data)
                
                print(f"Mission sent to Firebase: {mission_data}")
                return True
                
        except Exception as e:
            print(f"Error sending mission: {e}")
            return False

    def update_system_status(self):
        """Update system status in Firebase"""
        try:
            with self.connection_lock:
                if not self.is_connected:
                    return False
                
                # Update system status
                self.system_status.update({
                    "control_mode": self.control_mode,
                    "firebase_connected": self.is_connected,
                    "online": True,
                    "last_heartbeat": time.time(),
                    "timestamp": time.time()
                })
                
                # Send to Firebase
                system_path = FIREBASE_PATHS["system_status"].split("/")
                self.db.child(*system_path).set(self.system_status)
                
                return True
                
        except Exception as e:
            print(f"Error updating system status: {e}")
            return False

    def set_control_mode(self, mode):
        """Set control mode"""
        with self.connection_lock:
            self.control_mode = mode
            self.update_system_status()
            print(f"Control mode set to: {mode}")

    def get_control_mode(self):
        """Get current control mode"""
        with self.connection_lock:
            return self.control_mode

    def is_firebase_connected(self):
        """Check if Firebase is connected"""
        with self.connection_lock:
            return self.is_connected

    def stop_listeners(self):
        """Stop all Firebase listeners"""
        try:
            print("Stopping Firebase listeners...")
            
            # Stop all streams
            streams = [
                self.joystick_stream,
                self.autonomous_stream,
                self.mission_commands_stream,
                self.navigation_status_stream,
                self.system_stream,
                self.sensors_stream
            ]
            
            for stream in streams:
                if stream:
                    try:
                        stream.close()
                    except:
                        pass
            
            # Reset stream references
            self.joystick_stream = None
            self.autonomous_stream = None
            self.mission_commands_stream = None
            self.navigation_status_stream = None
            self.system_stream = None
            self.sensors_stream = None
            
            self.is_connected = False
            print("Firebase listeners stopped")
            
        except Exception as e:
            print(f"Error stopping listeners: {e}")

    def send_mission_commands(self, mission_data):
        """Send mission commands to Firebase"""
        try:
            with self.connection_lock:
                if not self.is_connected:
                    print("Firebase not connected, cannot send mission commands")
                    return False
                
                # Validate mission data
                if not self.validate_mission_data(mission_data):
                    print("Invalid mission commands data")
                    return False
                
                # Update timestamp
                mission_data["timestamp"] = time.time()
                
                # Send to Firebase
                mission_path = FIREBASE_PATHS["mission_commands"].split("/")
                self.db.child(*mission_path).set(mission_data)
                
                # Update local data
                self.mission_commands.update(mission_data)
                
                print(f"Mission commands sent to Firebase: {mission_data}")
                return True
                
        except Exception as e:
            print(f"Error sending mission commands: {e}")
            return False

    def send_navigation_status(self, nav_data):
        """Send navigation status to Firebase"""
        try:
            with self.connection_lock:
                if not self.is_connected:
                    print("Firebase not connected, cannot send navigation status")
                    return False
                
                # Validate navigation data
                if not self.validate_navigation_data(nav_data):
                    print("Invalid navigation status data")
                    return False
                
                # Update timestamp
                nav_data["timestamp"] = time.time()
                
                # Send to Firebase
                nav_path = FIREBASE_PATHS["navigation_status"].split("/")
                self.db.child(*nav_path).set(nav_data)
                
                # Update local data
                self.navigation_status.update(nav_data)
                
                print(f"Navigation status sent to Firebase: {nav_data}")
                return True
                
        except Exception as e:
            print(f"Error sending navigation status: {e}")
            return False 