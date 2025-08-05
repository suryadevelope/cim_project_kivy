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
        "sensors": "sensors/current"
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
            
            # Rover control data
            self.joystick_data = {
                "x_axis": 0.0,
                "y_axis": 0.0,
                "lift_speed": 0.0,
                "clicked": False,
                "release": False,
                "centerliftknob": 0
            }
            
            # Autonomous control data
            self.autonomous_data = {
                "run_status": False,
                "vh_autonomous": False,
                "wp_loaded_count": 0
            }
            
            # System status
            self.system_status = {
                "control_mode": "hardware",
                "firebase_connected": False,
                "last_heartbeat": None,
                "online": False,
                "timestamp": None
            }
            
            # Callbacks
            self.on_joystick_update = None
            self.on_autonomous_update = None
            self.on_system_update = None
            
            # Start listening threads
            self.start_listeners()
            print("FirebaseControl initialized successfully")
            
        except Exception as e:
            print(f"Error initializing FirebaseControl: {e}")
            import traceback
            traceback.print_exc()
            self.is_connected = False
            raise
    
    def test_connection(self):
        """Test Firebase connection by writing and reading a test value"""
        try:
            print("=== TESTING FIREBASE CONNECTION ===")
            test_data = {
                "test": "connection",
                "timestamp": datetime.now().isoformat(),
                "status": "testing"
            }
            test_path = FIREBASE_PATHS["system_status"].split("/")
            
            print(f"Writing test data to path: {test_path}")
            # Write test data
            self.db.child(*test_path).set(test_data)
            print("✅ Test data written successfully")
            
            # Read test data back
            print("Reading test data back...")
            result = self.db.child(*test_path).get()
            if result.val():
                print("✅ Test data read successfully")
                self.is_connected = True
                print(f"✅ Firebase connection status: {self.is_connected}")
                return True
            else:
                print("❌ Failed to read test data")
                self.is_connected = False
                print(f"❌ Firebase connection status: {self.is_connected}")
                return False
                
        except Exception as e:
            print(f"❌ Firebase connection test failed: {e}")
            import traceback
            traceback.print_exc()
            self.is_connected = False
            print(f"❌ Firebase connection status: {self.is_connected}")
            return False

    def validate_autonomous_data(self, autonomous_data):
        """Validate autonomous data structure and content"""
        try:
            if not isinstance(autonomous_data, dict):
                print("Invalid autonomous data: not a dictionary")
                return False
            
            # Check required fields
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
            
            # Listen for system status
            system_path = FIREBASE_PATHS["system_status"].split("/")
            print(f"Setting up system status listener for path: {system_path}")
            self.system_stream = self.db.child(*system_path).stream(
                self.on_system_status_update
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
                    self.joystick_data.update(data)
                    if self.on_joystick_update:
                        Clock.schedule_once(lambda dt: self.on_joystick_update(data))
                    print(f"Joystick data updated: {data}")
        except Exception as e:
            print(f"Error handling joystick update: {e}")
    
    def on_autonomous_data_update(self, message):
        """Handle autonomous data updates from Firebase with enhanced validation"""
        try:
            if message['event'] == 'put':
                data = message['data']
                if data:
                    # Validate the autonomous data before processing
                    if self.validate_autonomous_data(data):
                        self.autonomous_data.update(data)
                        if self.on_autonomous_update:
                            Clock.schedule_once(lambda dt: self.on_autonomous_update(data))
                        print(f"Autonomous data updated: {data}")
                    else:
                        print(f"Invalid autonomous data received, ignoring: {data}")
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
                    self.system_status.update(data)
                    if self.on_system_update:
                        Clock.schedule_once(lambda dt: self.on_system_update(data))
                    print(f"System status updated: {data}")
        except Exception as e:
            print(f"Error handling system status update: {e}")
    
    def send_joystick_data(self, joystick_data):
        """Send joystick data to Firebase"""
        try:
            if self.control_mode == "internet":
                joystick_path = FIREBASE_PATHS["joystick"].split("/")
                self.db.child(*joystick_path).set(joystick_data)
                print(f"Sent joystick data to Firebase: {joystick_data}")
                return True
            else:
                print(f"Not in internet mode (current mode: {self.control_mode})")
                return False
        except Exception as e:
            print(f"Error sending joystick data: {e}")
            self.is_connected = False
            # Try to reconnect
            try:
                self.start_listeners()
            except Exception as reconnect_error:
                print(f"Failed to reconnect to Firebase: {reconnect_error}")
            return False
    
    def send_autonomous_command(self, command_data):
        """Send autonomous command to Firebase with enhanced validation"""
        try:
            if self.control_mode == "internet" and self.is_connected:
                # Validate the command data before sending
                if self.validate_autonomous_data(command_data):
                    autonomous_path = FIREBASE_PATHS["autonomous"].split("/")
                    self.db.child(*autonomous_path).set(command_data)
                    print(f"Sent autonomous command to Firebase: {command_data}")
                    return True
                else:
                    print(f"Invalid autonomous command data, not sending: {command_data}")
                    return False
            else:
                if self.control_mode != "internet":
                    print(f"Not in internet mode (current mode: {self.control_mode})")
                elif not self.is_connected:
                    print("Firebase not connected")
                return False
        except Exception as e:
            print(f"Error sending autonomous command: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def ensure_connection(self):
        """Ensure Firebase connection is established"""
        try:
            if not self.is_connected:
                print("Firebase not connected, attempting to establish connection...")
                if self.test_connection():
                    print("✅ Firebase connection established")
                    return True
                else:
                    print("❌ Failed to establish Firebase connection")
                    return False
            else:
                print("✅ Firebase already connected")
                return True
        except Exception as e:
            print(f"❌ Error ensuring Firebase connection: {e}")
            return False

    def send_autonomous_mission(self, mission_data):
        """Send autonomous mission data to Firebase with enhanced validation"""
        try:
            print(f"=== FIREBASE SEND AUTONOMOUS MISSION DEBUG ===")
            print(f"send_autonomous_mission called with data: {mission_data}")
            print(f"Current control mode: {self.control_mode}")
            print(f"Firebase connected: {self.is_connected}")
            
            # Ensure connection is established
            if not self.ensure_connection():
                print("❌ Cannot send mission: Firebase connection not available")
                return False
            
            if self.control_mode == "internet" and self.is_connected:
                print("✅ Conditions met for Firebase upload - proceeding with validation")
                # Validate the mission data structure
                if isinstance(mission_data, dict) and "mission" in mission_data and "status" in mission_data:
                    print("✅ Mission data structure is valid")
                    # Validate mission points
                    mission_points = mission_data.get("mission", [])
                    if isinstance(mission_points, list):
                        print(f"✅ Mission points is a list with {len(mission_points)} points")
                        # Validate each mission point
                        valid_points = []
                        for i, point in enumerate(mission_points):
                            if isinstance(point, (list, tuple)) and len(point) >= 2:
                                # Ensure coordinates are numeric
                                try:
                                    lat = float(point[0])
                                    lon = float(point[1])
                                    valid_points.append([lat, lon])
                                    print(f"✅ Validated point {i}: [{lat}, {lon}]")
                                except (ValueError, TypeError):
                                    print(f"❌ Invalid mission point coordinates: {point}")
                                    continue
                        
                        if valid_points:
                            # Create validated mission data
                            validated_mission_data = {
                                "mission": valid_points,
                                "status": mission_data.get("status", "stop"),
                                "timestamp": time.time(),
                                "mission_count": len(valid_points)
                            }
                            
                            print(f"✅ Validated mission data: {validated_mission_data}")
                            
                            # Send to Firebase
                            autonomous_path = FIREBASE_PATHS["autonomous"].split("/")
                            print(f"📤 Sending to Firebase path: {autonomous_path}")
                            
                            try:
                                self.db.child(*autonomous_path).set(validated_mission_data)
                                print(f"✅ Successfully sent autonomous mission to Firebase: {validated_mission_data}")
                                return True
                            except Exception as firebase_error:
                                print(f"❌ Firebase write error: {firebase_error}")
                                import traceback
                                traceback.print_exc()
                                return False
                        else:
                            print("❌ No valid mission points found")
                            return False
                    else:
                        print(f"❌ Invalid mission points format: {mission_points}")
                        return False
                else:
                    print(f"❌ Invalid mission data structure: {mission_data}")
                    return False
            else:
                if self.control_mode != "internet":
                    print(f"❌ Not in internet mode (current mode: {self.control_mode})")
                elif not self.is_connected:
                    print("❌ Firebase not connected")
                return False
        except Exception as e:
            print(f"❌ Error sending autonomous mission: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def update_system_status(self):
        """Update system status in Firebase"""
        try:
            if self.is_connected:
                status = {
                    "control_mode": self.control_mode,
                    "firebase_connected": self.is_connected,
                    "last_heartbeat": time.time(),
                    "online": True,
                    "timestamp": datetime.now().isoformat()
                }
                system_path = FIREBASE_PATHS["system_status"].split("/")
                self.db.child(*system_path).set(status)
                self.system_status.update(status)
        except Exception as e:
            print(f"Error updating system status: {e}")
    
    def set_control_mode(self, mode):
        """Set control mode (hardware/internet)"""
        if mode in ["hardware", "internet"]:
            print(f"Setting Firebase control mode from {self.control_mode} to {mode}")
            self.control_mode = mode
            self.update_system_status()
            print(f"Control mode set to: {mode}")
            return True
        else:
            print(f"Invalid control mode: {mode}")
            return False
    
    def get_control_mode(self):
        """Get current control mode"""
        return self.control_mode
    
    def is_firebase_connected(self):
        """Check if Firebase is connected"""
        return self.is_connected
    
    def stop_listeners(self):
        """Stop Firebase listeners"""
        try:
            if hasattr(self, 'joystick_stream'):
                self.joystick_stream.close()
            if hasattr(self, 'autonomous_stream'):
                self.autonomous_stream.close()
            if hasattr(self, 'system_stream'):
                self.system_stream.close()
            self.is_connected = False
            print("Firebase listeners stopped")
        except Exception as e:
            print(f"Error stopping Firebase listeners: {e}") 