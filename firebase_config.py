# Firebase Configuration
# Replace these values with your own Firebase project configuration

FIREBASE_CONFIG ={
  "apiKey": "AIzaSyCTNMHMgYxwdQNoFlp2hLDxNNzKgQlKy0A",
  "authDomain": "rover-d963e.firebaseapp.com",
  "databaseURL": "https://rover-d963e-default-rtdb.firebaseio.com",
  "projectId": "rover-d963e",
  "storageBucket": "rover-d963e.firebasestorage.app",
  "messagingSenderId": "330549730257",
  "appId": "1:330549730257:web:6367442819a8cbe6791ef0",
  "measurementId": "G-71GG5M4LDL"
}

# Database paths for different control data
FIREBASE_PATHS = {
    "joystick": "control/joystick",
    "autonomous": "control/autonomous", 
    "system_status": "system/status",
    "sensors": "sensors/current",
    "mission_commands": "control/mission_commands",
    "navigation_status": "control/navigation_status"
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