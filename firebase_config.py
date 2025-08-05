# Firebase Configuration
# Replace these values with your own Firebase project configuration

FIREBASE_CONFIG = {
    "apiKey": "your-api-key-here",
    "authDomain": "your-project-id.firebaseapp.com",
    "databaseURL": "https://your-project-id-default-rtdb.firebaseio.com",
    "projectId": "your-project-id",
    "storageBucket": "your-project-id.appspot.com",
    "messagingSenderId": "your-sender-id",
    "appId": "your-app-id"
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