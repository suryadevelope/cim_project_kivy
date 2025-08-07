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
            "mission_commands": "control/mission_commands",
            "navigation_status": "control/navigation_status"
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
            
            # Rover control data - Updated to match socket schema
            self.joystick_data = {
                "udp_command": "@0,115,-1,0,0.0",  # Default stop command
                "timestamp": time.time()
            }
            
            # Remote control data (for backward compatibility)
            self.remote_control_data = {
                "speed": 0,
                "direction": 115,
                "holdobject": -1,
                "centerliftknob": 0,
                "lift_speed": 0.0,
                "source": "local",
                "timestamp": time.time()
            }
            
            # Autonomous control data
            self.autonomous_data = {
                "run_status": False,
                "vh_autonomous": False,
                "wp_loaded_count": 0
            }
            
            # Mission commands data (new structure)
            self.mission_commands = {
                "mission": [],
                "mission_count": 0,
                "status": "stop",  # "start", "stop", "pause"
                "timestamp": None
            }
            
            # Navigation status data (new structure)
            self.navigation_status = {
                "active": False,
                "current_waypoint": 0,
                "distance_to_target": 0,
                "heading": 0,
                "speed": 0,
                "timestamp": None,
                "total_waypoints": 0
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
            self.on_joystick_update = None  # type: ignore
            self.on_autonomous_update = None  # type: ignore
            self.on_mission_commands_update = None  # type: ignore
            self.on_navigation_status_update = None  # type: ignore
            self.on_system_update = None  # type: ignore
            
            # Start listening threads
            self.start_listeners()
            print("FirebaseControl initialized successfully")
            
        except Exception as e:
            print(f"Error initializing FirebaseControl: {e}")
            import traceback
            traceback.print_exc()
            self.is_connected = False
    
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

    def validate_joystick_data(self, joystick_data):
        """Validate joystick data structure"""
        try:
            if not isinstance(joystick_data, dict):
                print(f"Invalid joystick data type: {type(joystick_data)}")
                return False
            
            # Check for UDP command format (new schema)
            if "udp_command" in joystick_data:
                udp_command = joystick_data["udp_command"]
                if not isinstance(udp_command, str) or not udp_command.startswith("@"):
                    print(f"Invalid UDP command format: {udp_command}")
                    return False
                
                # Parse and validate UDP command parts
                try:
                    parts = udp_command[1:].split(",")
                    if len(parts) < 5:
                        print(f"UDP command has insufficient parts: {len(parts)}")
                        return False
                    
                    speed = int(parts[0])
                    direction = int(parts[1])
                    holdobject = int(parts[2])
                    centerliftknob = int(parts[3])
                    lift_speed = float(parts[4])
                    
                    # Validate ranges
                    if not (0 <= speed <= 255):
                        print(f"Invalid speed value: {speed}")
                        return False
                    
                    valid_directions = [1, 3, 4, 5, 6, 7, 8, 9, 115]
                    if direction not in valid_directions:
                        print(f"Invalid direction value: {direction}")
                        return False
                    
                    if holdobject not in [-1, 0, 1]:
                        print(f"Invalid holdobject value: {holdobject}")
                        return False
                    
                    if centerliftknob not in [-1, 0, 1]:
                        print(f"Invalid centerliftknob value: {centerliftknob}")
                        return False
                    
                    if not (-1.0 <= lift_speed <= 1.0):
                        print(f"Invalid lift_speed value: {lift_speed}")
                        return False
                    
                except (ValueError, IndexError) as e:
                    print(f"Error parsing UDP command: {e}")
                    return False
                
                return True
            
            # Check for old format (backward compatibility)
            elif "speed" in joystick_data and "direction" in joystick_data:
                speed = joystick_data.get("speed", 0)
                direction = joystick_data.get("direction", 115)
                holdobject = joystick_data.get("holdobject", -1)
                centerliftknob = joystick_data.get("centerliftknob", 0)
                lift_speed = joystick_data.get("lift_speed", 0.0)
                
                # Validate ranges
                if not (0 <= speed <= 255):
                    print(f"Invalid speed value: {speed}")
                    return False
                
                valid_directions = [1, 3, 4, 5, 6, 7, 8, 9, 115]
                if direction not in valid_directions:
                    print(f"Invalid direction value: {direction}")
                    return False
                
                if holdobject not in [-1, 0, 1]:
                    print(f"Invalid holdobject value: {holdobject}")
                    return False
                
                if centerliftknob not in [-1, 0, 1]:
                    print(f"Invalid centerliftknob value: {centerliftknob}")
                    return False
                
                if not (-1.0 <= lift_speed <= 1.0):
                    print(f"Invalid lift_speed value: {lift_speed}")
                    return False
                
                return True
            
            else:
                print(f"Invalid joystick data structure: {joystick_data}")
                return False
                
        except Exception as e:
            print(f"Error validating joystick data: {e}")
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
        """Validate mission commands data structure and content"""
        try:
            if not isinstance(mission_data, dict):
                print("Invalid mission data: not a dictionary")
                return False
            
            # Check required fields
            required_fields = ["mission", "mission_count", "status"]
            for field in required_fields:
                if field not in mission_data:
                    print(f"Invalid mission data: missing required field '{field}'")
                    return False
            
            # Validate mission field
            if not isinstance(mission_data["mission"], list):
                print("Invalid mission data: mission must be a list")
                return False
            
            # Validate mission points
            for i, point in enumerate(mission_data["mission"]):
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
            
            # Validate mission_count
            if not isinstance(mission_data["mission_count"], (int, float)):
                print("Invalid mission data: mission_count must be numeric")
                return False
            
            # Validate status
            status = mission_data["status"]
            if not isinstance(status, str) or status not in ["start", "stop", "pause"]:
                print("Invalid mission data: status must be 'start', 'stop', or 'pause'")
                return False
            
            # Validate optional timestamp
            if "timestamp" in mission_data and not isinstance(mission_data["timestamp"], (int, float, type(None))):
                print("Invalid mission data: timestamp must be numeric or None")
                return False
            
            return True
            
        except Exception as e:
            print(f"Error validating mission data: {e}")
            return False

    def validate_navigation_data(self, nav_data):
        """Validate navigation status data structure and content"""
        try:
            if not isinstance(nav_data, dict):
                print("Invalid navigation data: not a dictionary")
                return False
            
            # Check required fields
            required_fields = ["active", "current_waypoint", "distance_to_target", "heading", "speed", "total_waypoints"]
            for field in required_fields:
                if field not in nav_data:
                    print(f"Invalid navigation data: missing required field '{field}'")
                    return False
            
            # Validate data types
            if not isinstance(nav_data["active"], bool):
                print("Invalid navigation data: active must be boolean")
                return False
            
            if not isinstance(nav_data["current_waypoint"], (int, float)):
                print("Invalid navigation data: current_waypoint must be numeric")
                return False
            
            if not isinstance(nav_data["distance_to_target"], (int, float)):
                print("Invalid navigation data: distance_to_target must be numeric")
                return False
            
            if not isinstance(nav_data["heading"], (int, float)):
                print("Invalid navigation data: heading must be numeric")
                return False
            
            if not isinstance(nav_data["speed"], (int, float)):
                print("Invalid navigation data: speed must be numeric")
                return False
            
            if not isinstance(nav_data["total_waypoints"], (int, float)):
                print("Invalid navigation data: total_waypoints must be numeric")
                return False
            
            # Validate optional timestamp
            if "timestamp" in nav_data and not isinstance(nav_data["timestamp"], (int, float, type(None))):
                print("Invalid navigation data: timestamp must be numeric or None")
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
        """Handle joystick data updates from Firebase with enhanced validation"""
        try:
            if message['event'] == 'put':
                data = message['data']
                if data:
                    # Handle new structure where joystick might be nested
                    if isinstance(data, dict) and "joystick" in data:
                        joystick_data = data["joystick"]
                    else:
                        joystick_data = data
                    
                    # Validate the joystick data before processing
                    if self.validate_joystick_data(joystick_data):
                        self.joystick_data.update(joystick_data)
                        if self.on_joystick_update:
                            Clock.schedule_once(lambda dt: self.on_joystick_update(joystick_data))
                        print(f"Joystick data updated: {joystick_data}")
                    else:
                        print(f"Invalid joystick data received, ignoring: {joystick_data}")
                else:
                    print("Empty joystick data received")
        except Exception as e:
            print(f"Error handling joystick update: {e}")
            import traceback
            traceback.print_exc()

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
                        self.autonomous_data.update(autonomous_data)
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
                    
                    self.system_status.update(system_data)
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
                    
                    # Update sensors data
                    if hasattr(self, 'sensors_data'):
                        self.sensors_data.update(sensors_data)
                    else:
                        self.sensors_data = sensors_data
                    
                    print(f"Sensors data updated: {sensors_data}")
        except Exception as e:
            print(f"Error handling sensors update: {e}")
            import traceback
            traceback.print_exc()

    def on_mission_commands_update(self, message):
        """Handle mission commands updates from Firebase"""
        try:
            if message['event'] == 'put':
                data = message['data']
                if data:
                    # Handle new structure where mission_commands might be nested
                    if isinstance(data, dict) and "mission_commands" in data:
                        mission_data = data["mission_commands"]
                    else:
                        mission_data = data
                    
                    # Validate mission data
                    if self.validate_mission_data(mission_data):
                        self.mission_commands.update(mission_data)
                        if self.on_mission_commands_update:
                            Clock.schedule_once(lambda dt: self.on_mission_commands_update(mission_data))
                        print(f"Mission commands updated: {mission_data}")
                    else:
                        print(f"Invalid mission commands data received, ignoring: {mission_data}")
                else:
                    print("Empty mission commands data received")
        except Exception as e:
            print(f"Error handling mission commands update: {e}")
            import traceback
            traceback.print_exc()

    def on_navigation_status_update(self, message):
        """Handle navigation status updates from Firebase"""
        try:
            if message['event'] == 'put':
                data = message['data']
                if data:
                    # Handle new structure where navigation_status might be nested
                    if isinstance(data, dict) and "navigation_status" in data:
                        nav_data = data["navigation_status"]
                    else:
                        nav_data = data
                    
                    # Validate navigation data
                    if self.validate_navigation_data(nav_data):
                        self.navigation_status.update(nav_data)
                        if self.on_navigation_status_update:
                            Clock.schedule_once(lambda dt: self.on_navigation_status_update(nav_data))
                        print(f"Navigation status updated: {nav_data}")
                    else:
                        print(f"Invalid navigation status data received, ignoring: {nav_data}")
                else:
                    print("Empty navigation status data received")
        except Exception as e:
            print(f"Error handling navigation status update: {e}")
            import traceback
            traceback.print_exc()
    
    def send_joystick_data(self, joystick_data):
        """Send joystick data to Firebase with enhanced validation"""
        try:
            if self.control_mode == "internet" and self.is_connected:
                # Validate the joystick data before sending
                if self.validate_joystick_data(joystick_data):
                    joystick_path = FIREBASE_PATHS["joystick"].split("/")
                    self.db.child(*joystick_path).set(joystick_data)
                    print(f"Sent joystick data to Firebase: {joystick_data}")
                    return True
                else:
                    print(f"Invalid joystick data, not sending: {joystick_data}")
                    return False
            else:
                if self.control_mode != "internet":
                    print(f"Not in internet mode (current mode: {self.control_mode})")
                elif not self.is_connected:
                    print("Firebase not connected")
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
    
    def send_mission_commands(self, mission_data):
        """Send mission commands to Firebase with validation"""
        try:
            if self.control_mode == "internet" and self.is_connected:
                # Validate the mission data before sending
                if self.validate_mission_data(mission_data):
                    mission_path = FIREBASE_PATHS["mission_commands"].split("/")
                    self.db.child(*mission_path).set(mission_data)
                    print(f"Sent mission commands to Firebase: {mission_data}")
                    return True
                else:
                    print(f"Invalid mission commands data, not sending: {mission_data}")
                    return False
            else:
                if self.control_mode != "internet":
                    print(f"Not in internet mode (current mode: {self.control_mode})")
                elif not self.is_connected:
                    print("Firebase not connected")
                return False
        except Exception as e:
            print(f"Error sending mission commands: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def send_navigation_status(self, nav_data):
        """Send navigation status to Firebase with validation"""
        try:
            if self.control_mode == "internet" and self.is_connected:
                # Validate the navigation data before sending
                if self.validate_navigation_data(nav_data):
                    nav_path = FIREBASE_PATHS["navigation_status"].split("/")
                    self.db.child(*nav_path).set(nav_data)
                    print(f"Sent navigation status to Firebase: {nav_data}")
                    return True
                else:
                    print(f"Invalid navigation status data, not sending: {nav_data}")
                    return False
            else:
                if self.control_mode != "internet":
                    print(f"Not in internet mode (current mode: {self.control_mode})")
                elif not self.is_connected:
                    print("Firebase not connected")
                return False
        except Exception as e:
            print(f"Error sending navigation status: {e}")
            import traceback
            traceback.print_exc()
            return False 