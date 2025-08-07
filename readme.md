# Rover Control System

A comprehensive rover control application with Firebase Realtime Database integration for remote control capabilities.

## Features

- **Dual Control Modes**: Hardware (joystick) and Internet (Firebase) control
- **Real-time Video Streaming**: Multiple camera feeds with full-screen capability
- **GPS Integration**: Real-time GPS tracking and mapping
- **Autonomous Navigation**: Waypoint-based autonomous control
- **Firebase Remote Control**: Internet-based remote control via Firebase Realtime Database
- **Compass Integration**: Real-time compass heading display
- **Battery Monitoring**: Real-time battery status monitoring

## Project Structure

```
cim_project_kivy/
├── main.py                 # Main application file
├── firebase_control.py     # Firebase integration module
├── firebase_config.py      # Firebase configuration
├── test_firebase.py        # Firebase integration tests
├── FIREBASE_SETUP.md       # Firebase setup guide
├── requirements.txt        # Python dependencies
├── assets/                 # Application assets
│   ├── logo.png
│   ├── splash_image.png
│   ├── compass_bg.png
│   ├── needle.png
│   └── ...
├── audio/                  # Audio files
│   ├── success_conn.mp3
│   ├── waiting_conn.mp3
│   └── ...
└── tests/                  # Test files
    ├── gpstest1.py
    └── maingps.py
```

## Installation

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Firebase Setup** (for remote control):
   - Follow the instructions in `FIREBASE_SETUP.md`
   - Update `firebase_config.py` with your Firebase credentials

3. **Test Firebase Integration**:
   ```bash
   python test_firebase.py
   ```

## Usage

### Running the Application

```bash
python main.py
```

### Control Modes

1. **Hardware Mode** (Default):
   - Use physical joystick for direct control
   - Green "Hardware" button in top navigation

2. **Internet Mode**:
   - Remote control via Firebase Realtime Database
   - Orange "Internet" button in top navigation
   - Control rover from anywhere with internet access

## Firebase Integration

### Remote Control via Firebase

When in Internet mode, control the rover by updating the Firebase database:

#### New Joystick Schema (Matches Socket Schema)

The joystick data now uses the same format as the socket communication:

```json
{
  "control": {
    "joystick": {
      "udp_command": "@128,8,0,0,0.5",  // Same format as socket: @speed,direction,holdobject,centerliftknob,lift_speed
      "timestamp": 1754475460.6133726
    }
  }
}
```

**UDP Command Format:** `@{speed},{direction},{holdobject},{centerliftknob},{lift_speed}`

- **speed** (0-255): Movement speed
- **direction** (1,3,4,5,6,7,8,9,115): Movement direction
  - `1` = Backward-left, `3` = Backward-right, `4` = Left, `5` = Backward
  - `6` = Right, `7` = Forward-left, `8` = Forward, `9` = Forward-right, `115` = Stop
- **holdobject** (-1,0,1): Object manipulation state
  - `-1` = No action, `1` = Hold/grab, `0` = Release
- **centerliftknob** (-1,0,1): Lift control
  - `-1` = Down, `0` = Neutral, `1` = Up
- **lift_speed** (-1.0 to 1.0): Lift speed

#### Legacy Joystick Schema (Backward Compatible)

For backward compatibility, the old format is still supported:

```json
{
  "control": {
    "joystick": {
      "x_axis": 0.5,      // -1.0 to 1.0 (left/right)
      "y_axis": -0.3,     // -1.0 to 1.0 (forward/backward)
      "lift_speed": 0.8,  // 0.0 to 1.0 (lift speed)
      "clicked": false,   // boolean (button press)
      "release": false,   // boolean (button release)
      "centerliftknob": 0 // integer (hat position)
    }
  }
}
```

#### Autonomous Control

```json
{
  "control": {
    "autonomous": {
      "run_status": true,      // Start/stop autonomous mode
      "vh_autonomous": true,   // Enable/disable autonomous navigation
      "wp_loaded_count": 5     // Number of waypoints loaded
    }
  }
}
```

### Data Flow

1. **Hardware Mode**: Joystick → Socket → Rover
2. **Internet Mode**: Firebase → UDP → Rover (same socket format)

### GUI Updates

Both socket and Firebase data now update the GUI consistently:
- Joystick status display
- Object manipulation status
- Lift control status
- Real-time data synchronization

## Configuration

### Firebase Configuration

Edit `firebase_config.py` to set up Firebase integration:

```python
FIREBASE_CONFIG = {
    "apiKey": "your-actual-api-key",
    "authDomain": "your-project-id.firebaseapp.com",
    "databaseURL": "https://your-project-id-default-rtdb.firebaseio.com",
    "projectId": "your-project-id",
    "storageBucket": "your-project-id.appspot.com",
    "messagingSenderId": "your-sender-id",
    "appId": "your-app-id"
}
```

### Control Parameters

Adjust rover control parameters in `firebase_config.py`:

```python
ROVER_CONTROL_PARAMS = {
    "joystick_deadzone": 0.1,  # Minimum joystick movement
    "max_speed": 100.0,         # Maximum speed percentage
    "update_frequency": 50,      # Control update frequency
    "udp_timeout": 1.0          # UDP timeout
}
```

## Features

### Real-time Video Streaming
- Multiple camera feeds displayed in grid layout
- Click any camera feed for full-screen view
- Auto-zoom mode for automatic full-screen on camera events

### GPS and Mapping
- Real-time GPS tracking with map integration
- Satellite and regular map view toggle
- Waypoint plotting and autonomous navigation
- Mission planning and execution

### Autonomous Navigation
- Waypoint-based navigation system
- Real-time progress tracking
- Distance and heading calculations
- Mission status monitoring

### Battery and System Monitoring
- Real-time battery voltage monitoring
- System status indicators
- Connection status monitoring
- Audio feedback for system events

## Troubleshooting

### Common Issues

1. **Firebase Connection Failed**:
   - Check internet connection
   - Verify Firebase configuration
   - Run `python test_firebase.py` to test connection

2. **Camera Not Working**:
   - Check camera permissions
   - Verify camera index in code
   - Test with different camera indices

3. **GPS Not Fixing**:
   - Ensure GPS antenna is connected
   - Check GPS module configuration
   - Wait for 3D fix (may take several minutes)

### Debug Mode

Enable debug logging by checking console output for:
- Firebase connection status
- GPS fix status
- Camera feed status
- System error messages

## Development

### Testing

Run the Firebase integration tests:
```bash
python test_firebase.py
```

### Building Executable

Use PyInstaller to create a standalone executable:
```bash
pyinstaller Rover.spec
```

## License

This project is designed for educational and research purposes.

## Support

For issues or questions:
1. Check the console logs for error messages
2. Verify Firebase configuration
3. Test with simple database updates first
4. Ensure network connectivity to Firebase servers

Step 2: Update the Code

Update the paths in your main.py to point to the images in the assets folder:

python

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.clock import Clock
from kivy.uix.popup import Popup
from kivy.uix.camera import Camera

# Splash Screen
class SplashScreen(Screen):
    def __init__(self, **kwargs):
        super(SplashScreen, self).__init__(**kwargs)
        self.add_widget(Image(source='assets/splash_image.png'))

    def on_enter(self):
        Clock.schedule_once(self.switch_to_main, 5)

    def switch_to_main(self, dt):
        self.manager.current = 'main'

# Main Screen
class MainScreen(Screen):
    def __init__(self, **kwargs):
        super(MainScreen, self).__init__(**kwargs)
        layout = BoxLayout(orientation='horizontal')

        # Left column with buttons and image
        left_column = BoxLayout(orientation='vertical', size_hint=(0.2, 1))
        self.logo = Image(source='assets/logo.png', size_hint=(1, 0.2))
        left_column.add_widget(self.logo)
        self.buttons = ['Button 1', 'Button 2', 'Button 3']
        for button_text in self.buttons:
            btn = Button(text=button_text)
            left_column.add_widget(btn)
        
        # Right grid for live camera feeds
        right_grid = GridLayout(cols=2)
        self.cameras = []
        for i in range(4):
            camera = Camera(index=i, resolution=(640, 480), play=True)  # Ensure camera index exists
            camera.bind(on_touch_down=self.on_camera_touch)
            right_grid.add_widget(camera)
            self.cameras.append(camera)

        layout.add_widget(left_column)
        layout.add_widget(right_grid)
        self.add_widget(layout)

    def on_camera_touch(self, instance, touch):
        if instance.collide_point(*touch.pos):
            self.show_full_screen(instance.index)

    def show_full_screen(self, camera_index):
        popup_layout = BoxLayout(orientation='vertical')
        popup_camera = Camera(index=camera_index, resolution=(640, 480), play=True)
        close_btn = Button(text='X', size_hint=(1, 0.1))
        popup_layout.add_widget(popup_camera)
        popup_layout.add_widget(close_btn)

        self.popup = Popup(content=popup_layout, auto_dismiss=False, size_hint=(1, 1))
        close_btn.bind(on_release=self.popup.dismiss)
        self.popup.open()

# App class
class RoverApp(App):
    def build(self):
        sm = ScreenManager()
        sm.add_widget(SplashScreen(name='splash'))
        sm.add_widget(MainScreen(name='main'))
        return sm

if __name__ == '__main__':
    RoverApp().run()

Step 3: Update the Spec File

Modify the rover_app.spec file to include the assets folder:

python

# rover_app.spec
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('assets/splash_image.png', 'assets'),
        ('assets/logo.png', 'assets')
    ],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='rover_app',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='rover_app',
)

Step 4: Run PyInstaller

Run PyInstaller with the updated spec file:

bash

pyinstaller rover_app.spec

This will create a dist directory with an executable named rover_app.
Step 5: Update the .desktop File

Update the rover_app.desktop file to reflect the new paths:

ini

[Desktop Entry]
Version=1.0
Name=Rover
Comment=A neat and good looking GUI app
Exec=/path/to/your/project/dist/rover_app/rover_app
Icon=/path/to/your/project/assets/logo.png
Terminal=false
Type=Application
Categories=Utility;

Make sure to replace /path/to/your/project with the actual path to your project directory.
Step 6: Make the .desktop File Executable

Make the .desktop file executable and move it to the appropriate directory:

bash

chmod +x rover_app.desktop
mv rover_app.desktop ~/.local/share/applications/

Complete Project Directory Structure

css

rover_app/
├── main.py
├── assets/
│   ├── splash_image.png
│   ├── logo.png
├── rover_app.spec
└── dist/
    └── rover_app/
        └── rover_app (executable)

Running the App

You should now be able to find "Rover" in your application menu and run it like any other application.





PyInstaller.exceptions.PythonLibraryNotFoundError: Python library not found: libpython3.11.so, libpython3.11.so.1.0
    This means your Python installation does not come with proper shared library files.
    This usually happens due to missing development package, or unsuitable build parameters of the Python installation.

    * On Debian/Ubuntu, you need to install Python development packages:
      * apt-get install python3-dev
      * apt-get install python-dev
    * If you are building Python by yourself, rebuild with `--enable-shared` (or, `--enable-framework` on macOS).


sudo apt-get update
sudo apt-get install python3-dev python3.11-dev
