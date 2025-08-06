# Firebase Configuration
# Replace these values with your own Firebase project configuration

FIREBASE_CONFIG = {
  "apiKey": "AIzaSyBw-vayMYjNPxZcrnMuAS5I1W9WRO1yZ0s",
  "authDomain": "army-rover.firebaseapp.com",
  "databaseURL": "https://army-rover-default-rtdb.firebaseio.com",
  "projectId": "army-rover",
  "storageBucket": "army-rover.firebasestorage.app",
  "messagingSenderId": "270093464380",
  "appId": "1:270093464380:web:3872b44054ef575765e439",
  "measurementId": "G-4YZ5SN0VXR"
}

# Database paths for different control data
FIREBASE_PATHS = {
    "joystick": "control/joystick",
    "autonomous": "control/autonomous", 
    "system_status": "system/status",
    "sensors": "sensors/current"
}

# Default control settings
DEFAULT_CONTROL_SETTINGS = {
    "hardware_mode": {
        "enabled": True,
        "description": "Direct hardware control via joystick"
    },
    "internet_mode": {
        "enabled": True,
        "description": "Remote control via Firebase"
    }
}

# Rover control parameters
ROVER_CONTROL_PARAMS = {
    "joystick_deadzone": 0.1,  # Minimum joystick movement to register
    "max_speed": 100.0,         # Maximum speed percentage
    "update_frequency": 50,      # Control update frequency in Hz
    "udp_timeout": 1.0          # UDP timeout in seconds
} 