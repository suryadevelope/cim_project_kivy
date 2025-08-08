# Firebase Configuration
# Replace these values with your own Firebase project configuration

FIREBASE_CONFIG ={
  "apiKey": "AIzaSyCOanfw1qDie_c5l8OClkkWLtwD7DC4g_E",
  "authDomain": "army-rover-new.firebaseapp.com",
  "databaseURL": "https://army-rover-new-default-rtdb.firebaseio.com",
  "projectId": "army-rover-new",
  "storageBucket": "army-rover-new.firebasestorage.app",
  "messagingSenderId": "533033277095",
  "appId": "1:533033277095:web:0632e963db8a555b2d6d82",
  "measurementId": "G-K7V64EM2WV"
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