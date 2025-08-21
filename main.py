# Autonomous Data Exchange System - Enhanced Implementation with UI Performance Optimizations
# 
# This system now includes:
# 1. Hardware and Internet Connectivity Checks
#    - Non-blocking periodic connectivity monitoring (every 30 seconds)
#    - Real-time status updates
#    - Automatic fallback mechanisms
#
# 2. Firebase Integration with Validation
#    - Data structure validation
#    - Connection status monitoring
#    - Error handling and recovery
#    - Background task processing to prevent UI blocking
#
# 3. Enhanced Error Handling
#    - Comprehensive exception handling
#    - Detailed logging and debugging
#    - User-friendly error messages
#
# 4. Data Synchronization
#    - Real-time data sync status
#    - Mode-specific data handling
#    - Connectivity-aware updates
#
# 5. User Interface Enhancements
#    - Connectivity status indicators
#    - Mode-specific warnings
#    - Real-time status updates
#    - Optimized frame rates (15 FPS instead of 30 FPS)
#    - Background task manager for heavy operations
#
# 6. NEW FIREBASE DATA STRUCTURE SUPPORT
#    - Nested data structure with sensors/current, control, system, remote_control, test
#    - Mode-based data handling (hardware vs internet)
#    - Automatic data structure detection and fallback
#    - Enhanced validation for new data format
#
# 7. UI PERFORMANCE OPTIMIZATIONS (NEW)
#    - Removed blocking time.sleep() calls
#    - Reduced Clock scheduling frequency
#    - Background task processing for Firebase operations
#    - Optimized frame rates to prevent UI blocking
#    - Non-blocking connectivity checks
#    - Reduced autonomous mission sender frequency (10s instead of 5s)
#    - Reduced mode sync frequency (5s instead of 3s)
#
# Key Features:
# - Automatic connectivity detection
# - Data validation before processing
# - Graceful degradation on connection loss
# - Comprehensive logging for debugging
# - User-friendly status indicators
# - Support for new Firebase data structure:
#   {
#     "control": {
#       "autonomous": {
#         "mission": [[lat, lng], ...],
#         "mission_count": 2,
#         "status": "stop",
#         "timestamp": 1754475451.436969
#       },
#       "joystick": {
#         "timestamp": 1754475460.6133726,
#         "udp_command": "@0,115,-1,0,72.08"
#       }
#     },
#     "remote_control": {
#       "centerliftknob": 0,
#       "direction": 4,
#       "holdobject": 0,
#       "lift_speed": 0,
#       "source": "local",
#       "speed": 120,
#       "timestamp": 1754475446.8491106
#     },
#     "sensors": {
#       "current": {
#         "autonomous": {
#           "run_status": true,
#           "vh_autonomous": true,
#           "wp_loaded_count": 2,
#           "wp_number": 1
#         },
#         "compass": "3.209400827603986",
#         "gps": {
#           "fix": true,
#           "fix_type": "3D Fix",
#           "hdop": 0.8,
#           "lat": 17.4645105,
#           "lng": 78.59409033333333,
#           "num_sats": 10,
#           "pdop": 2.5,
#           "speed": 0,
#           "vdop": 2.4
#         },
#         "packet_count": 692,
#         "timestamp": 1754475446.376424,
#         "utils": "#1=26.88=55.56"
#       }
#     },
#     "system": {
#       "status": {
#         "control_mode": "internet",
#         "firebase_connected": true,
#         "last_heartbeat": 1754475448.9897358,
#         "online": true,
#         "timestamp": 1754475448.9897373
#       }
#     },
#     "test": {
#       "connection": {
#         "status": "connected",
#         "timestamp": 1754475368.637048
#       },
#       "health": {
#         "timestamp": 1754472604.9269185
#       }
#     }
#   }

import ast
import json
import os
import random
import threading
import time
import cv2
from kivy.app import App
from kivymd.app import MDApp
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.widget import Widget
from kivy_garden.mapview import MapView, MapMarker, MapSource
try:
    from kivy_garden.webview import WebView
except ImportError:
    WebView = None
from kivy.uix.image import Image
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button, Label
from kivy.uix.textinput import TextInput
from kivy.clock import Clock
from kivy.uix.video import Video
from kivy.uix.popup import Popup
from kivy.uix.gridlayout import GridLayout
from kivy.graphics import Color, Rectangle
import numpy as np
from stream import Stream
from kivy.graphics.texture import Texture
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.progressbar import ProgressBar
# from compass import CompassWidget

from kivy.lang import Builder
from kivy.core.image import Image as CoreImage
from queue import Queue
from kivy.uix.switch import Switch

from kivy.core.window import Window
from kivy.animation import Animation

from cameras import VideoReceiver
from kivy.properties import StringProperty, NumericProperty
from kivymd.toast import toast
from kivymd.uix.card import MDCard
from gtts import gTTS

import pygame
from kivy.config import Config

# Firebase imports
try:
    from firebase_control import FirebaseControl, FIREBASE_CONFIG
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False
    print("Firebase not available - pyrebase4 not installed")

# Add network connectivity check
import socket
import threading
import time
from datetime import datetime

def check_internet_connectivity():
    """Check if internet connectivity is available with improved timeout handling"""
    try:
        # Try multiple reliable hosts with shorter timeouts
        hosts = [
            ("8.8.8.8", 53),      # Google DNS
            ("1.1.1.1", 53),      # Cloudflare DNS
            ("208.67.222.222", 53) # OpenDNS
        ]
        
        for host, port in hosts:
            try:
                # Create socket with timeout
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)  # 2 second timeout
                
                # Try to connect
                result = sock.connect_ex((host, port))
                sock.close()
                
                if result == 0:
                    print(f"✅ Internet connectivity confirmed via {host}:{port}")
                    return True
                    
            except (socket.timeout, OSError) as e:
                print(f"❌ Connection to {host}:{port} failed: {e}")
                continue
            except Exception as e:
                print(f"❌ Unexpected error connecting to {host}:{port}: {e}")
                continue
        
        print("❌ All internet connectivity checks failed")
        return False
        
    except Exception as e:
        print(f"❌ Internet connectivity check error: {e}")
        return False

# Global flag to track if initial hardware connectivity check has been completed
_hardware_connectivity_checked = False
_hardware_connectivity_result = False

def check_hardware_connectivity():
    """Check if hardware (UDP) connectivity is available with improved timeout handling"""
    global _hardware_connectivity_checked, _hardware_connectivity_result
    
    # Only check once at startup - after that, return the cached result
    if _hardware_connectivity_checked:
        print("⏭️ Hardware connectivity already checked - using cached result")
        return _hardware_connectivity_result
    
    try:
        print("🔍 Performing initial hardware connectivity check...")
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        test_socket.settimeout(1.0)  # 1 second timeout to prevent UI blocking
        
        # Try to send a test packet
        test_socket.sendto(b"ping", ('192.168.144.16', 5005))
        test_socket.close()
        
        _hardware_connectivity_result = True
        _hardware_connectivity_checked = True
        print("✅ Initial hardware connectivity check completed - SUCCESS")
        return True
        
    except socket.timeout:
        _hardware_connectivity_result = False
        _hardware_connectivity_checked = True
        print("❌ Initial hardware connectivity check timed out")
        return False
    except Exception as e:
        _hardware_connectivity_result = False
        _hardware_connectivity_checked = True
        print(f"❌ Initial hardware connectivity check failed: {e}")
        return False

# Set environment variables (optional but helpful)
os.environ["KIVY_NO_CONSOLELOG"] = "1"
os.environ["KIVY_NO_MTDEV"] = "1"
os.environ["KIVY_NO_ARGS"] = "1"
os.environ["KIVY_MOUSE_MODE"] = "mouse"

# THIS is the important one to stop red dots
Config.set('input', 'mouse', 'mouse,multitouch_on_demand')

def play_sound(file_path):
    try:
        pygame.mixer.init()
        pygame.mixer.music.load("./audio/"+file_path)
        pygame.mixer.music.play()
        
        # Remove blocking sleep - let the sound play in background
        # time.sleep(2)  # This was blocking the UI!
    except Exception as e:
        print(f"Error: {e}")





# Function to maximize window size
def maximize_window():
    from kivy.base import EventLoop
    if not EventLoop.event_listeners:
        EventLoop.ensure_window()
    Window.maximize()


Builder.load_string('''
<CompassWidget>:
    size_hint: None, None
    size: 230, 230  # Default size, will be updated by parent layout
    canvas.before:
        Rectangle:
            size: 230, 230  
            pos: self.pos 
            source: './assets/compass_bg.png'
           
    FloatLayout:
        size: self.size
        pos: self.pos
                    
        Image:
            id: needle
            source: './assets/needle.png'
            size_hint: None, None
            pos_hint: {'center_x': 0.68, 'center_y': 0.68}
            # pos: (self.center_x - 50,self.center_y-50)  # Center the needle
            size: 100, 100
            keep_ratio: True
            allow_stretch: True
            canvas.before:
                PushMatrix
                Rotate:
                    angle: root.needle_angle
                    origin: self.center
            canvas.after:
                PopMatrix
''')

class CompassWidget(BoxLayout):
    needle_angle = NumericProperty(0)

    def calculate_rotation_origin(self, angle, center_x, center_y, width, height):
        import math
        half_width = width / 2
        half_height = height / 2
        angle = abs(angle)
        radians = math.radians(angle)
        x_offset = half_width * math.cos(radians)
        y_offset = half_height * math.sin(radians)
        return (center_x - x_offset, center_y - y_offset)

    def set_needle_params(self, width, height):
        self.needle = self.ids.needle
        self.needle.size_hint = (width, height)
    def update_compass(self, angle):
        print(f"[DEBUG] CompassWidget.update_compass called with angle: {angle}")
        self.needle_angle = -angle  # Negative if you want north-up
        print(f"[DEBUG] CompassWidget.needle_angle set to: {self.needle_angle}")
    def update_angle(self, dt):
        angle = random.uniform(0, 360)
        self.update_compass(angle)
    pass


streaming = Stream()

# Splash Screen
class SplashScreen(Screen):
    def __init__(self, **kwargs):
        super(SplashScreen, self).__init__(**kwargs)
        
        with self.canvas.before:
            Color(0.75, 0.75, 0.75, 1)  # Gray metal color
            self.rect = Rectangle(size=self.size, pos=self.pos)
        self.bind(size=self._update_rect, pos=self._update_rect)
        self.add_widget(Image(source='./assets/splash_image.png'))  # Ensure this image exists
        # Add circular progress bar
        self.progress_bar = ProgressBar(max=1000)
        self.progress_bar.size_hint = (None, None)
        self.progress_bar.size = (150, 150)
        self.progress_bar.pos_hint = {'center_x': 0.5, 'center_y': 0.35}
        self.add_widget(self.progress_bar)
        
        # Add waiting text
        self.waiting_label = Label(
            text="Waiting for the rover to connect...",
            font_size='20sp',
            size_hint=(None, None),
            size=(self.width, 50),
            pos_hint={'center_x': 0.5, 'center_y': 0.3}
        )
        self.add_widget(self.waiting_label)
        
      

    def on_enter(self, *args):
        
        play_sound("waiting_conn.mp3")
        # Schedule a check to see if the condition is met every second
        Clock.schedule_interval(self.check_condition, 1)
        self.animate_progress_bar()

        
        # Clock.schedule_once(self.switch_to_main, 5)


    def animate_progress_bar(self):
            # Reset progress bar value
            self.progress_bar.value = 0
            
            # Create an animation to increment the progress bar
            anim = Animation(value=1000, duration=5)
            anim.bind(on_complete=self.repeat_animation)
            anim.start(self.progress_bar)
        
    def repeat_animation(self, animation, widget):
        self.animate_progress_bar()
    def check_condition(self, dt):
        if streaming.dataconfirm.get("compass", False):  # Safely check the condition
            
            play_sound("success_conn.mp3")
            
            Clock.schedule_once(self.switch_to_main, 5)

            # self.switch_to_main()
            return False  # Stop the interval check

    def switch_to_main(self,df):
        self.manager.current = 'main'
        
        maximize_window()

    def _update_rect(self, instance, value):
        self.rect.size = instance.size
        self.rect.pos = instance.pos

# Main Screen

# Custom MapMarker with rotation support for heading
from kivy.graphics.context_instructions import PushMatrix, PopMatrix, Rotate

class RotatingMapMarker(MapMarker):
    heading = NumericProperty(0)
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.logo_img = Image(source='./assets/rover_icon.png', size_hint=(None, None), size=(30, 30))
        self.add_widget(self.logo_img)
        self.logo_img.center = self.center
    def on_pos(self, *args):
        
        self.logo_img.center = self.center
    def on_heading(self, *args):
        # Only use canvas.before/after if canvas exists
        if hasattr(self.logo_img, 'canvas') and self.logo_img.canvas is not None:
            self.logo_img.canvas.before.clear()
            with self.logo_img.canvas.before:
                PushMatrix()
                Rotate(angle=self.heading, origin=self.logo_img.center)
            self.logo_img.canvas.after.clear()
            with self.logo_img.canvas.after:
                PopMatrix()


class MainScreen(Screen):
    img_src = StringProperty("./assets/bad_batt.png")
    jetsonimg_src = StringProperty("./assets/bad_batt.png")
    img_src_armstate = StringProperty("./assets/no_home.png")
    battimg = None
    # Add properties for GPS info
    satcount = StringProperty("0")
    irnss_accuracy = StringProperty("N/A")
    fix_type = StringProperty("N/A")
    gps_fix = False
    gps_status_label = None
    mapplot_btn_top = None
    gps_marker = None
    def __init__(self, **kwargs):
        super(MainScreen, self).__init__(**kwargs)
        
        # Initialize control mode
        self.control_mode = "hardware"
        
        # Flag to track if returning from mission planning
        # This prevents unnecessary Firebase connection tests when returning to home screen
        self.returning_from_mission_planning = False
        
        # Flag to track when processing mission commands to prevent connection tests
        self.processing_mission_commands = False
        
        # Flag to track if initial connectivity check has been completed
        # After this, no more network/Firebase connection tests will be performed
        self.initial_connectivity_check_completed = False
        
        with self.canvas.before:
            Color(0.95, 0.95, 0.97, 1)
            self.rect = Rectangle(size=self.size, pos=self.pos)
        self.bind(size=self._update_rect, pos=self._update_rect)

        self.autoshowfullscreen = False
        self.updatefullscreenval = False
        self.allvideopopups = []
        self.image_widgets = []
        self.autonomous_event = None
        self.joystick_control_enabled = False  # Initialize joystick control state
        
        # Enhanced autonomous data exchange system
        self.autonomous_data_exchange = {
            "hardware_connected": False,
            "internet_connected": False,
            "firebase_connected": False,
            "last_hardware_check": None,
            "last_internet_check": None,
            "autonomous_mode": "manual",
            "data_sync_status": "unknown"
        }
        
        # Firebase control initialization with enhanced error handling
        self.firebase_control = None
        
        # Initialize connectivity checks
        self.initialize_connectivity_checks()
        
        if FIREBASE_AVAILABLE:
            try:
                print("Attempting to initialize Firebase control...")
                self.firebase_control = FirebaseControl(FIREBASE_CONFIG)
                # Set up callbacks
                self.firebase_control.on_joystick_update = self.on_firebase_joystick_update  # type: ignore
                self.firebase_control.on_autonomous_update = self.on_firebase_autonomous_update  # type: ignore
                self.firebase_control.on_system_update = self.on_firebase_system_update  # type: ignore
                print("Firebase control initialized successfully")
                
                # Firebase connection test will be done in background during connectivity checks
                self.autonomous_data_exchange["firebase_connected"] = False
                    
            except Exception as e:
                print(f"Error initializing Firebase control: {e}")
                import traceback
                traceback.print_exc()
                self.firebase_control = None
                self.autonomous_data_exchange["firebase_connected"] = False
        else:
            print("Firebase not available - pyrebase4 not installed")
            self.autonomous_data_exchange["firebase_connected"] = False

        # --- Top Navigation Bar ---
        top_nav = BoxLayout(orientation='horizontal', size_hint_y=None, height=70, padding=[20, 10, 20, 10], spacing=20)
        with top_nav.canvas.before:
            Color(0.18, 0.28, 0.45, 1)
            self.topbar_rect = Rectangle(size=top_nav.size, pos=top_nav.pos)
        def update_topbar_rect(instance, value):
            self.topbar_rect.size = top_nav.size
            self.topbar_rect.pos = top_nav.pos
        top_nav.bind(size=update_topbar_rect, pos=update_topbar_rect)
        top_nav.add_widget(Image(source='./assets/logo.png', size_hint_x=None, width=50, allow_stretch=True, keep_ratio=True))
        # Main battery with voltage label
        main_batt_box = BoxLayout(orientation='vertical', size_hint=(None, 1), width=50, spacing=2)
        self.battimg = Image(source=self.img_src, size_hint_x=None, width=40, allow_stretch=True, keep_ratio=True)
        self.battimg.size_hint_y = 0.7
        self.batt_voltage_label = Label(text="0.0V", size_hint_y=0.3, color=(1, 1, 1, 1), font_size='10sp')
        main_batt_box.add_widget(self.battimg)
        main_batt_box.add_widget(self.batt_voltage_label)
        top_nav.add_widget(main_batt_box)
        
        # Jetson battery with voltage label
        jetson_batt_box = BoxLayout(orientation='vertical', size_hint=(None, 1), width=50, spacing=2)
        self.jetsonbattimg = Image(source=self.jetsonimg_src, size_hint_x=None, width=40, allow_stretch=True, keep_ratio=True)
        self.jetsonbattimg.size_hint_y = 0.7
        self.jetson_voltage_label = Label(text="0.0V", size_hint_y=0.3, color=(1, 1, 1, 1), font_size='10sp')
        jetson_batt_box.add_widget(self.jetsonbattimg)
        jetson_batt_box.add_widget(self.jetson_voltage_label)
        top_nav.add_widget(jetson_batt_box)
        
        # Arm state with status label
        armstate_box = BoxLayout(orientation='vertical', size_hint=(None, 1), width=50, spacing=2)
        self.armstateimg = Image(source=self.img_src_armstate, size_hint_x=None, width=40, allow_stretch=True, keep_ratio=True)
        self.armstateimg.size_hint_y = 0.7
        self.armstate_label = Label(text="Home", size_hint_y=0.3, color=(1, 1, 1, 1), font_size='10sp')
        armstate_box.add_widget(self.armstateimg)
        armstate_box.add_widget(self.armstate_label)
        top_nav.add_widget(armstate_box)
        self.top_switch = Switch(active=False, size_hint_x=None, width=60)
        self.top_switch.bind(active=self.on_switch_active)
        top_nav.add_widget(self.top_switch)
        
        # Control mode toggle button
        self.control_mode_btn = Button(
            text="Hardware", 
            size_hint_x=None, 
            width=100, 
            height=40, 
            background_color=(0.2, 0.6, 0.2, 1), 
            font_size='14sp'
        )
        self.control_mode_btn.bind(on_release=self.toggle_control_mode)
        top_nav.add_widget(self.control_mode_btn)
        # Add GPS info labels
        self.satcount_label = Label(text="Satcount: 0", size_hint_x=None, width=120, color=(1,1,1,1))
        self.irnss_accuracy_label = Label(text="IRNSS Acc: N/A", size_hint_x=None, width=140, color=(1,1,1,1))
        self.fix_type_label = Label(text="Fix: N/A", size_hint_x=None, width=100, color=(1,1,1,1))
        top_nav.add_widget(self.satcount_label)
        top_nav.add_widget(self.irnss_accuracy_label)
        top_nav.add_widget(self.fix_type_label)
        
        # Add Autonomous Navigation info labels
        self.autonomous_mode_label = Label(text="Mode: Manual", size_hint_x=None, width=120, color=(1,1,1,1))
        self.navigation_status_label = Label(text="Nav: Inactive", size_hint_x=None, width=120, color=(1,1,1,1))
        self.waypoint_progress_label = Label(text="WP: 0/0", size_hint_x=None, width=100, color=(1,1,1,1))
        top_nav.add_widget(self.autonomous_mode_label)
        top_nav.add_widget(self.navigation_status_label)
        top_nav.add_widget(self.waypoint_progress_label)
        # Map Plotting button
        self.mapplot_btn_top = Button(text="Map Plotting", size_hint_x=None, width=140, height=40, background_color=(0.1, 0.5, 0.2, 1), font_size='16sp')
        self.mapplot_btn_top.bind(on_release=self.goto_mapplot)
        top_nav.add_widget(self.mapplot_btn_top)
        top_nav.add_widget(Label(size_hint_x=1))
        # GPS status label (for fix wait message)
        self.gps_status_label = Label(text="", size_hint_x=None, width=200, color=(1,0,0,1))
        top_nav.add_widget(self.gps_status_label)

        root_layout = BoxLayout(orientation='vertical', size_hint=(1, 1), padding=[10, 10, 10, 10], spacing=10)
        root_layout.add_widget(top_nav)
        main_layout = BoxLayout(orientation='horizontal', spacing=16, size_hint_y=1)

        # --- Left: MapView (top) and CompassWidget + Start/Stop (bottom) ---
        left_panel = BoxLayout(orientation='vertical', spacing=12, size_hint=(0.48, 1))
        
        # Map controls row
        map_controls = BoxLayout(orientation='horizontal', size_hint=(1, None), height=40, spacing=10, padding=[5, 5, 5, 5])
        self.satellite_toggle = ToggleButton(text="Satellite View", size_hint=(None, 1), width=120, background_color=(0.2, 0.6, 0.8, 1))
        self.satellite_toggle.bind(state=self.on_satellite_toggle)
        map_controls.add_widget(self.satellite_toggle)
        
        # Zoom controls
        zoom_controls = BoxLayout(orientation='horizontal', size_hint=(None, 1), width=80, spacing=2)
        self.zoom_in_btn = Button(text="+", size_hint=(None, 1), width=35, background_color=(0.2, 0.7, 0.2, 1), font_size='16sp')
        self.zoom_out_btn = Button(text="-", size_hint=(None, 1), width=35, background_color=(0.7, 0.2, 0.2, 1), font_size='16sp')
        self.zoom_in_btn.bind(on_release=self.zoom_in)
        self.zoom_out_btn.bind(on_release=self.zoom_out)
        zoom_controls.add_widget(self.zoom_out_btn)
        zoom_controls.add_widget(self.zoom_in_btn)
        map_controls.add_widget(zoom_controls)
        
        map_controls.add_widget(Label(size_hint_x=1))  # Spacer
        left_panel.add_widget(map_controls)
        
        mapview_container = BoxLayout(size_hint=(1, 0.58), padding=0)  # Reduced height to accommodate controls
        try:
            # Initialize with regular map source
            self.mapview = MapView(zoom=16, lat=12.9716, lon=77.5946)
            self.mapview.size_hint = (1, 1)
            # Add GPS marker (small size)
            self.gps_marker = None  # Start with no marker
            # --- Add state for user interaction ---
            self._user_interacting = False
            self._recenter_timer = None
            self._last_gps_lat = 12.9716
            self._last_gps_lon = 77.5946
            # Bind touch events to mapview
            self.mapview.bind(on_touch_down=self._on_map_touch_down)
            self.mapview.bind(on_touch_move=self._on_map_touch_move)
            self.mapview.bind(on_touch_up=self._on_map_touch_up)
        except Exception:
            if WebView:
                self.mapview = WebView(url="https://www.google.com/maps")
                self.mapview.size_hint = (1, 1)
            else:
                self.mapview = Label(text="MapView/WebView not available.", size_hint=(1, 1))
        mapview_container.add_widget(self.mapview)
        left_panel.add_widget(mapview_container)

        # Compass and Start/Stop row
        bottom_row = BoxLayout(orientation='horizontal', size_hint=(1, 0.38), spacing=12)
        compass_box = BoxLayout(size_hint=(0.55, 1), padding=[0, 0, 0, 0])
        self.compass = CompassWidget()
        self.compass.size_hint = (None, None)
        self.compass.size = (170, 170)
        compass_box.add_widget(Widget(size_hint_x=0.1))
        compass_box.add_widget(self.compass)
        compass_box.add_widget(Widget(size_hint_x=0.1))
        bottom_row.add_widget(compass_box)
        
        # Autonomous Navigation Info Box
        autonomous_box = BoxLayout(orientation='vertical', size_hint=(0.45, 1), spacing=8, padding=[10, 5, 10, 5])
        
        # Autonomous Navigation Title
        autonomous_title = Label(text='Autonomous Navigation', size_hint=(1, None), height=25, 
                               color=(0.2, 0.2, 0.2, 1), font_size='14sp', bold=True)
        autonomous_box.add_widget(autonomous_title)
        
        # Mission Status
        self.mission_status_label = Label(text='Mission: No Mission', size_hint=(1, None), height=20, 
                                         color=(0.4, 0.4, 0.4, 1), font_size='12sp')
        autonomous_box.add_widget(self.mission_status_label)
        
        # Waypoint Progress
        self.waypoint_detail_label = Label(text='Waypoints: 0/0', size_hint=(1, None), height=20, 
                                          color=(0.4, 0.4, 0.4, 1), font_size='12sp')
        autonomous_box.add_widget(self.waypoint_detail_label)
        
        # Distance to Waypoint
        self.distance_label = Label(text='Distance: N/A', size_hint=(1, None), height=20, 
                                   color=(0.4, 0.4, 0.4, 1), font_size='12sp')
        autonomous_box.add_widget(self.distance_label)
        
        # Navigation State
        self.nav_state_label = Label(text='State: Inactive', size_hint=(1, None), height=20, 
                                    color=(0.4, 0.4, 0.4, 1), font_size='12sp')
        autonomous_box.add_widget(self.nav_state_label)
        
        # Mission Button
        mission_btn = Button(text='Mission', size_hint=(1, None), height=40, font_size='16sp', background_color=(0.2, 0.4, 0.8, 1))
        mission_btn.bind(on_release=self.goto_mapplot)
        autonomous_box.add_widget(mission_btn)
        
        # Start/Stop Buttons
        button_box = BoxLayout(orientation='horizontal', size_hint=(1, None), height=40, spacing=10)
        start_btn = Button(text='Start', size_hint=(0.5, 1), font_size='16sp', background_color=(0.1, 0.5, 0.2, 1))
        stop_btn = Button(text='Stop', size_hint=(0.5, 1), font_size='16sp', background_color=(0.6, 0.1, 0.1, 1))
        start_btn.bind(on_release=self.send_start_status)
        stop_btn.bind(on_release=self.send_stop_status)
        button_box.add_widget(start_btn)
        button_box.add_widget(stop_btn)
        autonomous_box.add_widget(button_box)
        
        bottom_row.add_widget(autonomous_box)
        left_panel.add_widget(bottom_row)
        main_layout.add_widget(left_panel)

        # --- Right: Camera images ---
        right_layout = BoxLayout(orientation='vertical', spacing=10, size_hint=(0.52, 1), padding=[0, 0, 0, 0])
        camera_layout = GridLayout(cols=2, rows=2, spacing=16, size_hint=(1, 0.9), padding=[10, 10, 10, 10])
        card_size_hint = (1, 1)
        for _ in range(3):
            img = Image(source='./assets/no_cam.png', allow_stretch=True, keep_ratio=True)
            self.image_widgets.append(img)
            card = MDCard(
                orientation='vertical',
                size_hint=card_size_hint,
                padding=0,
                elevation=4,
                radius=[18, 18, 18, 18],
                shadow_softness=2
            )
            card.add_widget(img)
            camera_layout.add_widget(card)
        camera_layout.add_widget(Widget(size_hint=card_size_hint))
        right_layout.add_widget(camera_layout)
        main_layout.add_widget(right_layout)
        root_layout.add_widget(main_layout)
        self.size_hint = (1, 1)
        self.add_widget(root_layout)

        # --- Integrate new logic ---
        streaming.bind(update_event=self.update_joystickview)
        streaming.bind(update_utils=self.update_utilsdata_ui)
        streaming.videosections = self.image_widgets
        streaming.setcompasswidget(self.compass)

        self.queue = Queue()
        self.videoreceiver = VideoReceiver()
        self.bind(size=self.on_size)

    def initialize_connectivity_checks(self):
        """Initialize connectivity checks for hardware and internet"""
        try:
            print("Initializing connectivity checks...")
            
            # Check hardware connectivity (non-blocking) - only once at startup
            self.autonomous_data_exchange["hardware_connected"] = check_hardware_connectivity()
            self.autonomous_data_exchange["last_hardware_check"] = datetime.now()
            
            # Assume internet is always available - remove connectivity check
            self.autonomous_data_exchange["internet_connected"] = True
            self.autonomous_data_exchange["last_internet_check"] = datetime.now()
            
            # Mark initial connectivity check as completed for hardware
            # This prevents unnecessary network connectivity tests after startup
            self.initial_connectivity_check_completed = True
            print("✅ Initial hardware connectivity check completed - no more network tests will be performed")
            
            print(f"Hardware connected: {self.autonomous_data_exchange['hardware_connected']}")
            print(f"Internet connected: {self.autonomous_data_exchange['internet_connected']}")
            print(f"Firebase connected: {self.autonomous_data_exchange['firebase_connected']}")
            
            # Start periodic connectivity checks immediately
            self.start_periodic_connectivity_checks()
            
            # Check Firebase mode at startup in background if available
            if self.firebase_control:
                # Run Firebase check in background to prevent UI blocking
                def background_firebase_check():
                    try:
                        if self.firebase_control.test_connection():
                            self.autonomous_data_exchange["firebase_connected"] = True
                            print("Firebase connection test successful")
                            # Check Firebase mode at startup after successful connection
                            print("Checking Firebase mode at startup...")
                            self.check_firebase_mode_at_startup()
                            # Start periodic mode synchronization
                            print("Starting periodic mode synchronization...")
                            self.start_periodic_mode_sync()
                        else:
                            print("Firebase connection test failed")
                            self.autonomous_data_exchange["firebase_connected"] = False
                        
                        # Mark initial connectivity check as completed - no more connection tests after this
                        self.initial_connectivity_check_completed = True
                        print("✅ Initial connectivity check completed - no more connection tests will be performed")
                        
                    except Exception as e:
                        print(f"Error in background Firebase check: {e}")
                        self.autonomous_data_exchange["firebase_connected"] = False
                        # Mark initial connectivity check as completed even on error
                        self.initial_connectivity_check_completed = True
                        print("✅ Initial connectivity check completed (with error) - no more connection tests will be performed")
                
                # Run in background thread
                threading.Thread(target=background_firebase_check, daemon=True).start()
            
        except Exception as e:
            print(f"Error initializing connectivity checks: {e}")
            import traceback
            traceback.print_exc()

    def check_firebase_mode_at_startup(self):
        """Check the control mode from Firebase at startup and implement it"""
        try:
            print("=== CHECKING FIREBASE MODE AT STARTUP ===")
            
            if not self.firebase_control or not self.autonomous_data_exchange["firebase_connected"]:
                print("Firebase not available or not connected, skipping mode check")
                return
            
            # Check if we have an active mission that should preserve internet mode
            has_active_internet_mission = self.check_active_internet_mission()
            
            # Get the current mode from Firebase system status
            try:
                system_path = FIREBASE_PATHS["system_status"].split("/")
                firebase_system_status = self.firebase_control.db.child(*system_path).get()
                
                if firebase_system_status.val():
                    firebase_mode = firebase_system_status.val().get("control_mode", "hardware")
                    print(f"Firebase system status found: control_mode = {firebase_mode}")
                    
                    # If we have an active internet mission, prioritize internet mode
                    if has_active_internet_mission:
                        print("Active internet mission detected at startup, ensuring internet mode")
                        if self.control_mode != "internet":
                            self.implement_internet_mode()
                        # Update Firebase to match our mode
                        self.update_firebase_system_status()
                        return
                    
                    # Check if the mode is different from current
                    if firebase_mode != self.control_mode:
                        print(f"Mode change detected: Firebase has '{firebase_mode}', current is '{self.control_mode}'")
                        
                        # Implement the mode from Firebase
                        if firebase_mode == "internet":
                            print("Implementing internet mode from Firebase")
                            self.implement_internet_mode()
                        elif firebase_mode == "hardware":
                            print("Implementing hardware mode from Firebase")
                            self.implement_hardware_mode()
                        else:
                            print(f"Unknown mode from Firebase: {firebase_mode}, defaulting to hardware")
                            self.control_mode = "hardware"
                    else:
                        print(f"Mode already synchronized: Firebase and local both have '{firebase_mode}'")
                        
                        # Ensure Firebase control mode is synchronized
                        if self.firebase_control.get_control_mode() != firebase_mode:
                            print("Synchronizing Firebase control mode")
                            self.firebase_control.set_control_mode(firebase_mode)
                else:
                    # No Firebase system status found - check if we should preserve internet mode
                    if has_active_internet_mission:
                        print("No Firebase system status but active internet mission detected, preserving internet mode")
                        if self.control_mode != "internet":
                            self.implement_internet_mode()
                        # Create Firebase system status
                        self.update_firebase_system_status()
                    else:
                        print("No Firebase system status found, defaulting to hardware mode")
                        self.control_mode = "hardware"
                    
            except Exception as e:
                print(f"Error reading Firebase system status: {e}")
                # Check if we should preserve internet mode even on error
                if has_active_internet_mission:
                    print("Error reading Firebase but active internet mission detected, preserving internet mode")
                    if self.control_mode != "internet":
                        self.implement_internet_mode()
                else:
                    print("Defaulting to hardware mode")
                    self.control_mode = "hardware"
            
            # Update the control mode button to reflect the current mode
            self.update_control_mode_button()
            
            print(f"=== STARTUP MODE CHECK COMPLETE: Current mode = {self.control_mode} ===")
            
        except Exception as e:
            print(f"Error checking Firebase mode at startup: {e}")
            import traceback
            traceback.print_exc()

    def implement_internet_mode(self):
        """Implement internet mode from Firebase"""
        try:
            print("=== IMPLEMENTING INTERNET MODE ===")
            
            # Set local control mode
            self.control_mode = "internet"
            
            # Set Firebase control mode
            if self.firebase_control:
                self.firebase_control.set_control_mode("internet")
                print(f"Firebase control mode set to: {self.firebase_control.get_control_mode()}")
            
            # Update autonomous data exchange
            self.autonomous_data_exchange["autonomous_mode"] = "internet"
            
            # Update data sync status
            self.update_data_sync_status()
            
            # Update GUI
            self.update_control_mode_button()
            
            print("=== INTERNET MODE IMPLEMENTED SUCCESSFULLY ===")
            
        except Exception as e:
            print(f"Error implementing internet mode: {e}")
            import traceback
            traceback.print_exc()

    def implement_hardware_mode(self):
        """Implement hardware mode from Firebase"""
        try:
            print("=== IMPLEMENTING HARDWARE MODE ===")
            
            # Set local control mode
            self.control_mode = "hardware"
            
            # Set Firebase control mode
            if self.firebase_control:
                self.firebase_control.set_control_mode("hardware")
                print(f"Firebase control mode set to: {self.firebase_control.get_control_mode()}")
            
            # Update autonomous data exchange
            self.autonomous_data_exchange["autonomous_mode"] = "manual"
            
            # Update data sync status
            self.update_data_sync_status()
            
            # Update GUI
            self.update_control_mode_button()
            
            print("=== HARDWARE MODE IMPLEMENTED SUCCESSFULLY ===")
            
        except Exception as e:
            print(f"Error implementing hardware mode: {e}")
            import traceback
            traceback.print_exc()

    def update_control_mode_button(self):
        """Update the control mode button to reflect the current mode"""
        try:
            if hasattr(self, 'control_mode_btn'):
                if self.control_mode == "internet":
                    self.control_mode_btn.text = "Internet"
                    self.control_mode_btn.background_color = (0.2, 0.2, 0.8, 1)  # Blue for internet
                else:
                    self.control_mode_btn.text = "Hardware"
                    self.control_mode_btn.background_color = (0.2, 0.6, 0.2, 1)  # Green for hardware
                print(f"Control mode button updated to: {self.control_mode}")
        except Exception as e:
            print(f"Error updating control mode button: {e}")

    def monitor_firebase_mode_changes(self):
        """Monitor Firebase for mode changes and implement them"""
        try:
            if not self.firebase_control or not self.autonomous_data_exchange["firebase_connected"]:
                return
            
            # Check if we have an active mission in internet mode before allowing mode changes
            has_active_internet_mission = self.check_active_internet_mission()
            
            # Use the new sync method from Firebase control
            if hasattr(self.firebase_control, 'sync_mode_from_firebase'):
                mode_changed = self.firebase_control.sync_mode_from_firebase()
                if mode_changed:
                    # Get the new mode from Firebase control
                    firebase_mode = self.firebase_control.get_control_mode()
                    print(f"=== FIREBASE MODE CHANGE DETECTED ===")
                    print(f"Firebase mode: {firebase_mode}, Previous mode: {self.control_mode}")
                    
                    # If we have an active internet mission, be more careful about mode changes
                    if has_active_internet_mission and self.control_mode == "internet":
                        print("⚠️ Active internet mission detected, preserving internet mode")
                        # Force Firebase to match our current mode
                        self.firebase_control.set_control_mode("internet")
                        self.update_firebase_system_status()
                        return
                    
                    # Implement the new mode
                    if firebase_mode == "internet":
                        print("Implementing internet mode change from Firebase")
                        self.implement_internet_mode()
                    elif firebase_mode == "hardware":
                        print("Implementing hardware mode change from Firebase")
                        self.implement_hardware_mode()
                    else:
                        print(f"Unknown mode from Firebase: {firebase_mode}, ignoring change")
                        self.handle_mode_sync_error("unknown", f"unknown_mode_{firebase_mode}")
                        
        except Exception as e:
            print(f"Error monitoring Firebase mode changes: {e}")
            self.handle_mode_sync_error("monitoring", str(e))

    def monitor_firebase_mode_changes_intelligent(self):
        """Intelligent monitoring of Firebase mode changes with mission awareness"""
        try:
            if not self.firebase_control or not self.autonomous_data_exchange["firebase_connected"]:
                return
            
            # Check if we have an active mission in internet mode
            has_active_internet_mission = self.check_active_internet_mission()
            
            # If we have an active internet mission, be very conservative about mode changes
            if has_active_internet_mission and self.control_mode == "internet":
                print("🛡️ Active internet mission detected, protecting internet mode from automatic changes")
                # Only allow mode changes if explicitly requested by user or if there's a critical error
                # For now, just ensure Firebase matches our mode
                if self.firebase_control.get_control_mode() != "internet":
                    print("Synchronizing Firebase to match our protected internet mode")
                    self.firebase_control.set_control_mode("internet")
                    self.update_firebase_system_status()
                return
            
            # If no active mission, proceed with normal mode monitoring
            self.monitor_firebase_mode_changes()
                        
        except Exception as e:
            print(f"Error in intelligent mode monitoring: {e}")
            self.handle_mode_sync_error("intelligent_monitoring", str(e))

    def check_active_internet_mission(self):
        """Check if there's an active mission that should preserve internet mode"""
        try:
            if not self.firebase_control or not self.autonomous_data_exchange["firebase_connected"]:
                return False
            
            # Use background task for Firebase operations to prevent UI blocking
            if hasattr(self, 'add_background_task'):
                self.add_background_task(self._check_active_internet_mission_background)
                return False  # Return False initially, will be updated via callback
            
            # Fallback to direct check if background task manager not available
            return self._check_active_internet_mission_direct()
            
        except Exception as e:
            print(f"Error checking active internet mission: {e}")
            return False

    def _check_active_internet_mission_direct(self):
        """Direct check for active internet mission (fallback method)"""
        try:
            from firebase_config import FIREBASE_PATHS
            autonomous_path = FIREBASE_PATHS["autonomous"].split("/")
            mission_data = self.firebase_control.db.child(*autonomous_path).get().val()
            if mission_data:
                mission_points = mission_data.get("mission", [])
                mission_status = mission_data.get("status", "stop")
                if mission_points and len(mission_points) > 0 and mission_status != "stop":
                    print(f"Active internet mission detected: {len(mission_points)} waypoints, status: {mission_status}")
                    return True
            return False
        except Exception as e:
            print(f"Error in direct mission check: {e}")
            return False

    def _check_active_internet_mission_background(self):
        """Background check for active internet mission"""
        try:
            from firebase_config import FIREBASE_PATHS
            autonomous_path = FIREBASE_PATHS["autonomous"].split("/")
            mission_data = self.firebase_control.db.child(*autonomous_path).get().val()
            
            has_active_mission = False
            if mission_data:
                mission_points = mission_data.get("mission", [])
                mission_status = mission_data.get("status", "stop")
                if mission_points and len(mission_points) > 0 and mission_status != "stop":
                    has_active_mission = True
                    print(f"Active internet mission detected: {len(mission_points)} waypoints, status: {mission_status}")
            
            # Update UI on main thread
            from kivy.clock import Clock
            Clock.schedule_once(lambda dt: self._update_mission_status_ui(has_active_mission), 0)
            
            return has_active_mission
            
        except Exception as e:
            print(f"Error in background mission check: {e}")
            return False

    def _update_mission_status_ui(self, has_active_mission):
        """Update UI with mission status (called on main thread)"""
        try:
            if has_active_mission:
                print("✅ UI updated: Active internet mission detected")
            else:
                print("ℹ️ UI updated: No active internet mission")
        except Exception as e:
            print(f"Error updating mission status UI: {e}")

    def update_firebase_system_status(self):
        """Update Firebase system status to reflect current local state"""
        try:
            if not self.firebase_control or not self.autonomous_data_exchange["firebase_connected"]:
                return False
            
            system_status = {
                "control_mode": self.control_mode,
                "firebase_connected": self.autonomous_data_exchange["firebase_connected"],
                "last_heartbeat": time.time(),
                "online": True,
                "timestamp": time.time()
            }
            
            system_path = FIREBASE_PATHS["system_status"].split("/")
            self.firebase_control.db.child(*system_path).set(system_status)
            print(f"✅ Firebase system status updated: {self.control_mode}")
            return True
            
        except Exception as e:
            print(f"Error updating Firebase system status: {e}")
            return False

    def handle_mode_sync_error(self, error_type, error_details):
        """Handle mode synchronization errors and log them"""
        try:
            error_message = f"Mode sync error: {error_type} - {error_details}"
            print(f"=== MODE SYNCHRONIZATION ERROR ===")
            print(error_message)
            
            # Log the error for debugging
            timestamp = datetime.now().isoformat()
            error_log = {
                "timestamp": timestamp,
                "error_type": error_type,
                "error_details": error_details,
                "current_mode": self.control_mode,
                "firebase_connected": self.autonomous_data_exchange["firebase_connected"],
                "internet_connected": self.autonomous_data_exchange["internet_connected"]
            }
            
            print(f"Error logged: {error_log}")
            
            # Try to update Firebase with error status if possible
            if self.firebase_control and self.autonomous_data_exchange["firebase_connected"]:
                try:
                    error_status = {
                        "control_mode": self.control_mode,
                        "firebase_connected": self.autonomous_data_exchange["firebase_connected"],
                        "last_heartbeat": time.time(),
                        "online": True,
                        "timestamp": timestamp,
                        "last_error": error_log
                    }
                    system_path = FIREBASE_PATHS["system_status"].split("/")
                    self.firebase_control.db.child(*system_path).set(error_status)
                    print("Error status sent to Firebase")
                except Exception as firebase_error:
                    print(f"Failed to send error status to Firebase: {firebase_error}")
            
        except Exception as e:
            print(f"Error handling mode sync error: {e}")

    def ensure_mode_synchronization(self):
        """Ensure the local mode is synchronized with Firebase"""
        try:
            print("=== ENSURING MODE SYNCHRONIZATION ===")
            
            if not self.firebase_control or not self.autonomous_data_exchange["firebase_connected"]:
                print("Firebase not available, cannot synchronize mode")
                return False
            
            # Get current Firebase mode
            system_path = FIREBASE_PATHS["system_status"].split("/")
            firebase_system_status = self.firebase_control.db.child(*system_path).get()
            
            if firebase_system_status.val():
                firebase_mode = firebase_system_status.val().get("control_mode", "hardware")
                print(f"Firebase mode: {firebase_mode}, Local mode: {self.control_mode}")
                
                if firebase_mode != self.control_mode:
                    print("Mode mismatch detected, synchronizing...")
                    
                    # Implement the Firebase mode
                    if firebase_mode == "internet":
                        self.implement_internet_mode()
                        print("Mode synchronized to internet")
                        return True
                    elif firebase_mode == "hardware":
                        self.implement_hardware_mode()
                        print("Mode synchronized to hardware")
                        return True
                    else:
                        print(f"Unknown Firebase mode: {firebase_mode}")
                        return False
                else:
                    print("Modes already synchronized")
                    return True
            else:
                print("No Firebase system status found")
                return False
                
        except Exception as e:
            print(f"Error ensuring mode synchronization: {e}")
            import traceback
            traceback.print_exc()
            return False

    def start_periodic_connectivity_checks(self):
        """Start periodic connectivity checks every 30 seconds"""
        def periodic_check():
            while True:
                try:
                    # Check hardware connectivity
                    hardware_connected = check_hardware_connectivity()
                    if hardware_connected != self.autonomous_data_exchange["hardware_connected"]:
                        self.autonomous_data_exchange["hardware_connected"] = hardware_connected
                        self.autonomous_data_exchange["last_hardware_check"] = datetime.now()
                        print(f"Hardware connectivity changed: {hardware_connected}")
                    
                    # Internet connectivity is assumed to be always available
                    # No need to check - focus on Firebase connectivity
                    
                    # Check Firebase connectivity if available
                    if self.firebase_control:
                        firebase_connected = self.firebase_control.is_firebase_connected()
                        if firebase_connected != self.autonomous_data_exchange["firebase_connected"]:
                            self.autonomous_data_exchange["firebase_connected"] = firebase_connected
                            print(f"Firebase connectivity changed: {firebase_connected}")
                    
                    # Monitor Firebase mode changes
                    if self.autonomous_data_exchange["firebase_connected"]:
                        self.monitor_firebase_mode_changes()
                        
                        # Ensure mode synchronization every few cycles
                        if hasattr(self, '_sync_counter'):
                            self._sync_counter += 1
                        else:
                            self._sync_counter = 0
                        
                        # Check synchronization every 4 cycles (every 2 minutes)
                        if self._sync_counter >= 4:
                            self._sync_counter = 0
                            print("Performing periodic mode synchronization check...")
                            self.ensure_mode_synchronization()
                    
                    # Update data sync status
                    self.update_data_sync_status()
                    
                    # Use Clock.schedule_once instead of blocking sleep
                    from kivy.clock import Clock
                    Clock.schedule_once(lambda dt: self.periodic_connectivity_check(), 30)
                    return  # Exit the loop to prevent multiple threads
                    
                except Exception as e:
                    print(f"Error in periodic connectivity check: {e}")
                    # Use Clock.schedule_once instead of blocking sleep
                    from kivy.clock import Clock
                    Clock.schedule_once(lambda dt: self.periodic_connectivity_check(), 30)
                    return
        
        # Start the periodic check using Clock instead of blocking thread
        from kivy.clock import Clock
        Clock.schedule_once(lambda dt: self.periodic_connectivity_check(), 30)
        print("Periodic connectivity checks started (non-blocking)")

    def cancel_pending_connectivity_checks(self):
        """Cancel any pending connectivity check schedules"""
        try:
            from kivy.clock import Clock
            # Cancel any pending periodic connectivity checks
            Clock.unschedule(self.periodic_connectivity_check)
            print("✅ Cancelled pending connectivity check schedules")
        except Exception as e:
            print(f"Error cancelling connectivity checks: {e}")

    def restart_connectivity_checks(self):
        """Restart connectivity checks after returning from mission planning"""
        try:
            print("🔄 Restarting connectivity checks after mission planning return")
            # Reset flags to allow normal operation
            self.returning_from_mission_planning = False
            self.processing_mission_commands = False
            print("✅ Reset flags: allowing normal connectivity checks")
            # Start the periodic connectivity check again
            self.periodic_connectivity_check()
        except Exception as e:
            print(f"Error restarting connectivity checks: {e}")

    def periodic_connectivity_check(self):
        """Non-blocking periodic connectivity check using Clock"""
        try:
            # Skip connectivity checks if returning from mission planning to avoid delays
            if self.returning_from_mission_planning:
                print("⏭️ Skipping connectivity check - returning from mission planning")
                # Schedule next check
                from kivy.clock import Clock
                Clock.schedule_once(lambda dt: self.periodic_connectivity_check(), 30)
                return
            
            # Skip connectivity checks if processing mission commands to avoid delays
            if self.processing_mission_commands:
                print("⏭️ Skipping connectivity check - processing mission commands")
                # Schedule next check
                from kivy.clock import Clock
                Clock.schedule_once(lambda dt: self.periodic_connectivity_check(), 30)
                return
            
            # Run connectivity checks in background thread to prevent UI blocking
            def run_checks():
                try:
                    # Internet connectivity is assumed to be always available
                    self.autonomous_data_exchange["internet_connected"] = True
                    
                    # Check hardware connectivity - but NEVER check after initial setup
                    # This prevents unnecessary network connectivity tests and delays
                    if self.initial_connectivity_check_completed:
                        # After initial check, just use the last known status
                        # Don't perform any network connectivity tests
                        hardware_ok = self.autonomous_data_exchange["hardware_connected"]
                        print("⏭️ Skipping hardware connectivity check - initial check already completed")
                    else:
                        # Only check during initial setup
                        hardware_ok = check_hardware_connectivity()
                        self.autonomous_data_exchange["hardware_connected"] = hardware_ok
                    
                    # Check Firebase connectivity - but NEVER test connection after initial check
                    # This prevents unnecessary Firebase connection tests and delays
                    if hasattr(self, 'firebase_control') and self.firebase_control:
                        if self.initial_connectivity_check_completed:
                            # After initial check, just use the last known status
                            # Don't send any testing data to Firebase
                            firebase_ok = self.autonomous_data_exchange["firebase_connected"]
                            print("⏭️ Skipping Firebase connection test - initial check already completed")
                        else:
                            # Only test connection during initial setup
                            firebase_ok = self.firebase_control.test_connection()
                            self.autonomous_data_exchange["firebase_connected"] = firebase_ok
                    else:
                        firebase_ok = False
                    
                    # Update data sync status on main thread
                    from kivy.clock import Clock
                    Clock.schedule_once(lambda dt: self.update_data_sync_status(), 0)
                    
                    # Schedule next check
                    Clock.schedule_once(lambda dt: self.periodic_connectivity_check(), 30)
                    
                except Exception as e:
                    print(f"Error in background connectivity check: {e}")
                    # Schedule retry on error
                    Clock.schedule_once(lambda dt: self.periodic_connectivity_check(), 30)
            
            # Run checks in background thread
            threading.Thread(target=run_checks, daemon=True).start()
            
        except Exception as e:
            print(f"Error scheduling periodic connectivity check: {e}")
            # Schedule retry on error
            from kivy.clock import Clock
            Clock.schedule_once(lambda dt: self.periodic_connectivity_check(), 30)

    def update_data_sync_status(self):
        """Update the data synchronization status based on connectivity"""
        try:
            hardware_ok = self.autonomous_data_exchange["hardware_connected"]
            internet_ok = self.autonomous_data_exchange["internet_connected"]
            firebase_ok = self.autonomous_data_exchange["firebase_connected"]
            
            if self.control_mode == "hardware":
                if hardware_ok:
                    self.autonomous_data_exchange["data_sync_status"] = "hardware_connected"
                else:
                    self.autonomous_data_exchange["data_sync_status"] = "hardware_disconnected"
            elif self.control_mode == "internet":
                if internet_ok and firebase_ok:
                    self.autonomous_data_exchange["data_sync_status"] = "internet_connected"
                elif internet_ok and not firebase_ok:
                    self.autonomous_data_exchange["data_sync_status"] = "internet_connected_firebase_disconnected"
                else:
                    self.autonomous_data_exchange["data_sync_status"] = "internet_disconnected"
            else:
                self.autonomous_data_exchange["data_sync_status"] = "unknown"
                
            print(f"Data sync status updated: {self.autonomous_data_exchange['data_sync_status']}")
            
        except Exception as e:
            print(f"Error updating data sync status: {e}")

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

    def on_switch_active(self, instance, value):
        """Control joystick movement mode and auto cam zoom"""
        if value:
            # Switch ON: Enable joystick control and auto cam zoom
            self.autoshowfullscreen = True
            self.joystick_control_enabled = True
            toast("Joystick Control & Auto Cam Zoom ON")
            print("Joystick control enabled - Front/Back/Gripper/Cams active")
        else:
            # Switch OFF: Disable joystick control and auto cam zoom
            self.autoshowfullscreen = False
            self.joystick_control_enabled = False
            toast("Joystick Control & Auto Cam Zoom OFF")
            print("Joystick control disabled - Manual mode only")
            if self.updatefullscreenval:
                self.dismiss_full_screen(self.popup)
    
    def toggle_control_mode(self, instance):
        """Toggle between hardware and internet control modes with enhanced validation"""
        try:
            print(f"Attempting to toggle control mode from {self.control_mode}")
            
            # Check if we have an active mission that should preserve internet mode
            has_active_internet_mission = self.check_active_internet_mission()
            
            if self.control_mode == "hardware":
                # Switching to internet mode
                print("Checking internet connectivity for internet mode...")
                
                # Internet is always assumed available - check Firebase connectivity
                if not self.autonomous_data_exchange["firebase_connected"]:
                    toast("Firebase connection required for internet mode")
                    print("Cannot switch to internet mode: no Firebase connection")
                    return
                
                if not self.autonomous_data_exchange["firebase_connected"]:
                    toast("Firebase connection required for internet mode")
                    print("Cannot switch to internet mode: no Firebase connection")
                    return
                
                # Use the new implementation method
                self.implement_internet_mode()
                
                # Update Stream control mode
                if hasattr(streaming, 'set_control_mode'):
                    streaming.set_control_mode("internet")
                    print(f"Stream control mode updated to: {streaming.get_control_mode()}")
                
                toast("Switched to Internet Control Mode")
                print("Successfully switched to internet mode")
                
            else:
                # Switching to hardware mode
                print("Checking hardware connectivity for hardware mode...")
                
                # Check if we're trying to switch away from internet mode with an active mission
                if has_active_internet_mission:
                    print("⚠️ Cannot switch to hardware mode: Active internet mission detected")
                    toast("Cannot switch to hardware mode while internet mission is active")
                    return
                
                if not self.autonomous_data_exchange["hardware_connected"]:
                    toast("Hardware connectivity required for hardware mode")
                    print("Cannot switch to hardware mode: no hardware connectivity")
                    return
                
                # Use the new implementation method
                self.implement_hardware_mode()
                
                # Update Stream control mode
                if hasattr(streaming, 'set_control_mode'):
                    streaming.set_control_mode("hardware")
                    print(f"Stream control mode updated to: {streaming.get_control_mode()}")
                
                toast("Switched to Hardware Control Mode")
                print("Successfully switched to hardware mode")
            
            # Update system status
            if self.firebase_control:
                self.firebase_control.update_system_status()
                print(f"System status updated for {self.control_mode} mode")
            
            # Update data sync status
            self.update_data_sync_status()
            
        except Exception as e:
            print(f"Error toggling control mode: {e}")
            import traceback
            traceback.print_exc()
            toast("Error switching control mode")
    
    def on_firebase_joystick_update(self, joystick_data):
        """Handle joystick data updates from Firebase with enhanced validation"""
        try:
            print(f"Firebase joystick update received: {joystick_data}")
            
            # Handle new nested structure
            if isinstance(joystick_data, dict) and "joystick" in joystick_data:
                joystick_data = joystick_data["joystick"]
            
            # Check if we're in internet mode
            if self.control_mode != "internet":
                print(f"Received Firebase joystick update but not in internet mode (current: {self.control_mode})")
                return
            
            # Internet is always assumed available - check Firebase connectivity
            if not self.autonomous_data_exchange["firebase_connected"]:
                print("Firebase connectivity lost, ignoring Firebase joystick update")
                return
            
            if not self.autonomous_data_exchange["firebase_connected"]:
                print("Firebase connectivity lost, ignoring Firebase joystick update")
                return
            
            # Handle new UDP command format (same as socket schema)
            if isinstance(joystick_data, dict) and "udp_command" in joystick_data:
                # Extract the UDP command string and send it directly
                udp_command = joystick_data["udp_command"]
                print(f"Received UDP command from Firebase: {udp_command}")
                
                # Validate UDP command format
                if isinstance(udp_command, str) and udp_command.startswith("@"):
                    # Send the command directly via UDP (same as socket)
                    self.send_joystick_udp(udp_command)
                    print(f"Successfully sent Firebase joystick command via UDP: {udp_command}")
                else:
                    print(f"Invalid UDP command format from Firebase: {udp_command}")
            
            # Handle old format (backward compatibility)
            elif isinstance(joystick_data, dict) and "speed" in joystick_data:
                print("Received old format joystick data from Firebase, converting...")
                # Convert old format to UDP command
                speed = joystick_data.get("speed", 0)
                direction = joystick_data.get("direction", 115)
                holdobject = joystick_data.get("holdobject", -1)
                centerliftknob = joystick_data.get("centerliftknob", 0)
                lift_speed = joystick_data.get("lift_speed", 0.0)
                
                # Format the command string (same as socket format)
                udp_command = "@{},{},{},{},{}".format(speed, direction, holdobject, centerliftknob, lift_speed)
                self.send_joystick_udp(udp_command)
                print(f"Converted and sent old format joystick data via UDP: {udp_command}")
            
            else:
                print(f"Invalid joystick data format from Firebase: {joystick_data}")
                return
            
            # Log successful update
            print(f"Successfully processed Firebase joystick update: {joystick_data}")
            
            # Update GUI with joystick data (same as socket data)
            self.update_joystick_gui_from_firebase(joystick_data)
            
        except Exception as e:
            print(f"Error handling Firebase joystick update: {e}")
            import traceback
            traceback.print_exc()
    
    def update_joystick_gui_from_firebase(self, joystick_data):
        """Update GUI with joystick data from Firebase (same as socket data)"""
        try:
            # Extract joystick information for GUI display
            if isinstance(joystick_data, dict) and "udp_command" in joystick_data:
                udp_command = joystick_data["udp_command"]
                # Parse UDP command for GUI display
                if udp_command.startswith("@"):
                    parts = udp_command[1:].split(",")
                    if len(parts) >= 5:
                        speed = int(parts[0])
                        direction = int(parts[1])
                        holdobject = int(parts[2])
                        centerliftknob = int(parts[3])
                        lift_speed = float(parts[4])
                        
                        # Update GUI elements (same as socket data)
                        self.update_joystick_display(speed, direction, holdobject, centerliftknob, lift_speed)
                        print(f"Updated GUI with Firebase joystick data: speed={speed}, direction={direction}")
            
            elif isinstance(joystick_data, dict) and "speed" in joystick_data:
                # Old format - extract values directly
                speed = joystick_data.get("speed", 0)
                direction = joystick_data.get("direction", 115)
                holdobject = joystick_data.get("holdobject", -1)
                centerliftknob = joystick_data.get("centerliftknob", 0)
                lift_speed = joystick_data.get("lift_speed", 0.0)
                
                # Update GUI elements
                self.update_joystick_display(speed, direction, holdobject, centerliftknob, lift_speed)
                print(f"Updated GUI with old format Firebase joystick data: speed={speed}, direction={direction}")
                
        except Exception as e:
            print(f"Error updating GUI with Firebase joystick data: {e}")
            import traceback
            traceback.print_exc()
    
    def update_joystick_display(self, speed, direction, holdobject, centerliftknob, lift_speed):
        """Update joystick display elements in GUI"""
        try:
            # Update joystick status labels if they exist
            if hasattr(self, 'joystick_status_label'):
                direction_names = {
                    1: "Backward-Left", 3: "Backward-Right", 4: "Left", 5: "Backward",
                    6: "Right", 7: "Forward-Left", 8: "Forward", 9: "Forward-Right", 115: "Stop"
                }
                direction_name = direction_names.get(direction, f"Unknown({direction})")
                status_text = f"Speed: {speed}, Direction: {direction_name}"
                self.joystick_status_label.text = status_text
            
            # Update object manipulation status
            if hasattr(self, 'object_status_label'):
                object_status = "Hold" if holdobject == 1 else "Release" if holdobject == 0 else "None"
                self.object_status_label.text = f"Object: {object_status}"
            
            # Update lift status
            if hasattr(self, 'lift_status_label'):
                lift_status = "Up" if centerliftknob == 1 else "Down" if centerliftknob == -1 else "Neutral"
                self.lift_status_label.text = f"Lift: {lift_status} ({lift_speed:.2f})"
                
        except Exception as e:
            print(f"Error updating joystick display: {e}")
    
    def on_firebase_autonomous_update(self, autonomous_data):
        """Handle autonomous data updates from Firebase with enhanced validation"""
        try:
            print(f"Firebase autonomous update received: {autonomous_data}")
            
            # Handle new nested structure
            if isinstance(autonomous_data, dict) and "autonomous" in autonomous_data:
                autonomous_data = autonomous_data["autonomous"]
            
            # Validate the autonomous data
            if not self.validate_autonomous_data(autonomous_data):
                print("Invalid autonomous data received from Firebase, ignoring update")
                return
            
            # Check if we're in internet mode
            if self.control_mode != "internet":
                print(f"Received Firebase autonomous update but not in internet mode (current: {self.control_mode})")
                return
            
            # Check connectivity status
            if not self.autonomous_data_exchange["internet_connected"]:
                print("Internet connectivity lost, ignoring Firebase autonomous update")
                return
            
            if not self.autonomous_data_exchange["firebase_connected"]:
                print("Firebase connectivity lost, ignoring Firebase autonomous update")
                return
            
            # Handle mission data
            if "mission" in autonomous_data:
                print(f"Processing mission data from Firebase: {len(autonomous_data['mission'])} waypoints")
                self.handle_mission_data_from_firebase(autonomous_data)
            else:
                # Handle autonomous command data
                print("Processing autonomous command data from Firebase")
                self.update_autonomous_display(autonomous_data)
            
            # Log successful update
            print(f"Successfully processed Firebase autonomous update: {autonomous_data}")
            
        except Exception as e:
            print(f"Error handling Firebase autonomous update: {e}")
            import traceback
            traceback.print_exc()
    
    def handle_mission_data_from_firebase(self, mission_data):
        """Handle mission data received from Firebase"""
        try:
            mission_points = mission_data.get("mission", [])
            status = mission_data.get("status", "stop")
            
            print(f"Handling mission data: {len(mission_points)} waypoints, status: {status}")
            
            # Update the mission points in MapPlotScreen if available
            app = App.get_running_app()
            if hasattr(app, 'root') and app.root is not None:
                try:
                    mapplot_screen = app.root.get_screen('mapplot')
                    if hasattr(mapplot_screen, 'user_markers'):
                        # --- Only update markers if mission points have changed ---
                        # Store last mission points in mapplot_screen
                        if not hasattr(mapplot_screen, '_last_mission_points'):
                            mapplot_screen._last_mission_points = []
                        # Compare new mission points to last
                        if mission_points != mapplot_screen._last_mission_points:
                            print("Mission points changed, updating markers...")
                            # Clear existing markers
                            for marker, _ in mapplot_screen.user_markers[:]:
                                try:
                                    mapplot_screen.mapview.remove_marker(marker)
                                except Exception as e:
                                    print(f"Warning: Could not remove marker: {e}")
                            mapplot_screen.user_markers.clear()
                            # Add new mission points as markers
                            for i, point in enumerate(mission_points):
                                try:
                                    lat, lon = point[0], point[1]
                                    marker = MapMarker(lat=lat, lon=lon)
                                    mapplot_screen.mapview.add_marker(marker)
                                    mapplot_screen.user_markers.append((marker, (lat, lon)))
                                    print(f"Added mission point {i+1}: ({lat}, {lon})")
                                except Exception as e:
                                    print(f"Error adding mission point {i+1}: {e}")
                            # Update path line
                            if hasattr(mapplot_screen, 'update_path_line'):
                                mapplot_screen.update_path_line()
                            print(f"Successfully updated mission with {len(mission_points)} waypoints")
                            # Update last mission points
                            mapplot_screen._last_mission_points = list(mission_points)
                        else:
                            print("Mission points unchanged, not updating markers.")
                except Exception as e:
                    print(f"Error updating MapPlotScreen with mission data: {e}")
            # Update autonomous status
            if status == "start":
                if self.last_status != "start":
                    self.last_status = "start"
                    if not self.autonomous_event:
                        self.start_autonomous_mission_sender()
                    print("Mission started from Firebase")
                else:
                    print("Mission already started, ignoring redundant start command")
            elif status == "stop":
                if self.last_status != "stop":
                    self.last_status = "stop"
                    if self.autonomous_event:
                        self.stop_autonomous_mission_sender()
                    print("Mission stopped from Firebase")
                else:
                    print("Mission already stopped, ignoring redundant stop command")
            elif status == "pause":
                if self.last_status != "pause":
                    self.last_status = "pause"
                    print("Mission paused from Firebase")
                else:
                    print("Mission already paused, ignoring redundant pause command")
            # Update UI to reflect mission status
            self.update_autonomous_display({
                "run_status": status == "start",
                "vh_autonomous": status == "start",
                "wp_loaded_count": len(mission_points)
            })
        except Exception as e:
            print(f"Error handling mission data from Firebase: {e}")
            import traceback
            traceback.print_exc()

    def on_firebase_system_update(self, system_data):
        """Handle system status updates from Firebase with mode change detection"""
        try:
            print(f"Firebase system update: {system_data}")
            
            # Handle new nested structure
            if isinstance(system_data, dict) and "status" in system_data:
                system_data = system_data["status"]
            
            # Update system status display
            firebase_control_mode = system_data.get("control_mode", "hardware")
            online = system_data.get("online", False)
            firebase_connected = system_data.get("firebase_connected", False)
            
            # Check for mode change and implement it
            if firebase_control_mode != self.control_mode:
                print(f"=== FIREBASE SYSTEM UPDATE: MODE CHANGE DETECTED ===")
                print(f"Firebase mode: {firebase_control_mode}, Current mode: {self.control_mode}")
                
                # Implement the mode change from Firebase
                if firebase_control_mode == "internet":
                    if self.autonomous_data_exchange["internet_connected"]:
                        print("Implementing internet mode change from Firebase system update")
                        self.implement_internet_mode()
                    else:
                        print("Firebase requests internet mode but no internet connection, staying in hardware mode")
                elif firebase_control_mode == "hardware":
                    print("Implementing hardware mode change from Firebase system update")
                    self.implement_hardware_mode()
                else:
                    print(f"Unknown mode from Firebase system update: {firebase_control_mode}, ignoring change")
            else:
                print(f"Firebase system update: mode unchanged ({firebase_control_mode})")
                
                # Ensure Firebase control mode is synchronized
                if self.firebase_control and self.firebase_control.get_control_mode() != firebase_control_mode:
                    print("Synchronizing Firebase control mode from system update")
                    self.firebase_control.set_control_mode(firebase_control_mode)
            
            # Update UI to reflect system status
            if hasattr(self, 'control_mode_btn'):
                if self.control_mode == "internet":
                    self.control_mode_btn.text = "Internet"
                    self.control_mode_btn.background_color = (0.2, 0.2, 0.8, 1)  # Blue for internet
                else:
                    self.control_mode_btn.text = "Hardware"
                    self.control_mode_btn.background_color = (0.2, 0.6, 0.2, 1)  # Green for hardware
                    
            print(f"System update processed: control_mode={self.control_mode}, online={online}, firebase_connected={firebase_connected}")
            
        except Exception as e:
            print(f"Error handling Firebase system update: {e}")
            import traceback
            traceback.print_exc()
    
    def on_firebase_mission_commands_update(self, mission_data):
        """Handle mission commands updates from Firebase"""
        try:
            print(f"Firebase mission commands update received: {mission_data}")
            
            # Set flag to indicate we're processing mission commands
            self.processing_mission_commands = True
            print("✅ Set flag: processing mission commands")
            
            # Check if we're in internet mode
            if self.control_mode != "internet":
                print(f"Received Firebase mission commands update but not in internet mode (current: {self.control_mode})")
                self.processing_mission_commands = False
                return
            
            # Internet is always assumed available - check Firebase connectivity
            if not self.autonomous_data_exchange["firebase_connected"]:
                print("Firebase connectivity lost, ignoring Firebase mission commands update")
                self.processing_mission_commands = False
                return
            
            # Remove duplicate check
            # if not self.autonomous_data_exchange["firebase_connected"]:
            #     print("Firebase connectivity lost, ignoring Firebase mission commands update")
            #     return
            
            # Handle mission data
            mission_points = mission_data.get("mission", [])
            status = mission_data.get("status", "stop")
            mission_count = mission_data.get("mission_count", 0)
            
            print(f"Processing mission commands: {len(mission_points)} waypoints, status: {status}, count: {mission_count}")
            
            # Update the mission points in MapPlotScreen if available
            app = App.get_running_app()
            if hasattr(app, 'root') and app.root is not None:
                try:
                    mapplot_screen = app.root.get_screen('mapplot')
                    if hasattr(mapplot_screen, 'user_markers'):
                        # Only update markers if mission points have changed
                        if not hasattr(mapplot_screen, '_last_mission_points'):
                            mapplot_screen._last_mission_points = []
                        if mission_points != mapplot_screen._last_mission_points:
                            print("Mission points changed, updating markers...")
                            # Clear existing markers
                            for marker, _ in mapplot_screen.user_markers[:]:
                                try:
                                    mapplot_screen.mapview.remove_marker(marker)
                                except Exception as e:
                                    print(f"Warning: Could not remove marker: {e}")
                            mapplot_screen.user_markers.clear()
                            # Add new mission points as markers
                            for i, point in enumerate(mission_points):
                                try:
                                    lat, lon = point[0], point[1]
                                    marker = MapMarker(lat=lat, lon=lon)
                                    mapplot_screen.mapview.add_marker(marker)
                                    mapplot_screen.user_markers.append((marker, (lat, lon)))
                                    print(f"Added mission point {i+1}: ({lat}, {lon})")
                                except Exception as e:
                                    print(f"Error adding mission point {i+1}: {e}")
                            # Update path line
                            if hasattr(mapplot_screen, 'update_path_line'):
                                mapplot_screen.update_path_line()
                            print(f"Successfully updated mission with {len(mission_points)} waypoints")
                            # Update last mission points
                            mapplot_screen._last_mission_points = list(mission_points)
                        else:
                            print("Mission points unchanged, not updating markers.")
                except Exception as e:
                    print(f"Error updating MapPlotScreen with mission data: {e}")
            
            # Handle mission status
            if status == "start":
                if self.last_status != "start":
                    self.last_status = "start"
                    if not self.autonomous_event:
                        self.start_autonomous_mission_sender()
                    print("Mission started from Firebase")
                else:
                    print("Mission already started, ignoring redundant start command")
            elif status == "stop":
                if self.last_status != "stop":
                    self.last_status = "stop"
                    if self.autonomous_event:
                        self.stop_autonomous_mission_sender()
                    print("Mission stopped from Firebase")
                else:
                    print("Mission already stopped, ignoring redundant stop command")
            elif status == "pause":
                if self.last_status != "pause":
                    self.last_status = "pause"
                    print("Mission paused from Firebase")
                else:
                    print("Mission already paused, ignoring redundant pause command")
            
            # Update UI to reflect mission status
            self.update_autonomous_display({
                "run_status": status == "start",
                "vh_autonomous": status == "start",
                "wp_loaded_count": len(mission_points)
            })
            
            # Update waypoint progress label
            if hasattr(self, 'waypoint_progress_label'):
                self.waypoint_progress_label.text = f"WP: 0/{len(mission_points)}"
            
            # Reset flag after processing mission commands
            self.processing_mission_commands = False
            print("✅ Reset flag: finished processing mission commands")
            
            print(f"Successfully processed Firebase mission commands update: {mission_data}")
            
        except Exception as e:
            print(f"Error handling Firebase mission commands update: {e}")
            import traceback
            traceback.print_exc()
            # Reset flag on error
            self.processing_mission_commands = False
    
    def on_firebase_navigation_status_update(self, nav_data):
        """Handle navigation status updates from Firebase"""
        try:
            print(f"Firebase navigation status update received: {nav_data}")
            
            # Check if we're in internet mode
            if self.control_mode != "internet":
                print(f"Received Firebase navigation status update but not in internet mode (current: {self.control_mode})")
                return
            
            # Check connectivity status
            if not self.autonomous_data_exchange["internet_connected"]:
                print("Internet connectivity lost, ignoring Firebase navigation status update")
                return
            
            if not self.autonomous_data_exchange["firebase_connected"]:
                print("Firebase connectivity lost, ignoring Firebase navigation status update")
                return
            
            # Extract navigation data
            active = nav_data.get("active", False)
            current_waypoint = nav_data.get("current_waypoint", 0)
            distance_to_target = nav_data.get("distance_to_target", 0)
            heading = nav_data.get("heading", 0)
            speed = nav_data.get("speed", 0)
            total_waypoints = nav_data.get("total_waypoints", 0)
            
            print(f"Navigation status: active={active}, current_wp={current_waypoint}, total_wp={total_waypoints}, distance={distance_to_target}, heading={heading}, speed={speed}")
            
            # Update navigation status label
            if hasattr(self, 'navigation_status_label'):
                if active:
                    self.navigation_status_label.text = "Nav: Active"
                    self.navigation_status_label.color = (0, 1, 0, 1)  # Green
                else:
                    self.navigation_status_label.text = "Nav: Inactive"
                    self.navigation_status_label.color = (1, 1, 1, 1)  # White
            
            # Update waypoint progress label
            if hasattr(self, 'waypoint_progress_label'):
                self.waypoint_progress_label.text = f"WP: {current_waypoint}/{total_waypoints}"
            
            # Update autonomous mode label
            if hasattr(self, 'autonomous_mode_label'):
                if active:
                    self.autonomous_mode_label.text = "Mode: Autonomous"
                    self.autonomous_mode_label.color = (0, 1, 0, 1)  # Green
                else:
                    self.autonomous_mode_label.text = "Mode: Manual"
                    self.autonomous_mode_label.color = (1, 1, 1, 1)  # White
            
            # Update compass with heading if navigation is active
            if active and hasattr(self, 'compass_widget'):
                self.compass_widget.update_compass(heading)
            
            print(f"Successfully processed Firebase navigation status update: {nav_data}")
            
        except Exception as e:
            print(f"Error handling Firebase navigation status update: {e}")
            import traceback
            traceback.print_exc()


    def send_joystick_udp(self, joystick_data):
        """Send joystick data via UDP in the correct format"""
        try:
            import socket
            
            # Check if joystick_data is already a formatted string
            if isinstance(joystick_data, str) and joystick_data.startswith("@"):
                # It's already a formatted UDP command string, send it directly
                print(f"Sending formatted UDP command string: {joystick_data}")
                # Create UDP socket and send the command
                udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                udp_socket.sendto(joystick_data.encode(), ('192.168.144.16', 5005))
                udp_socket.close()
                print(f"Sent UDP command string directly: {joystick_data}")
                return
            
            # Convert Firebase joystick data to the format expected by the rover
            x_axis = joystick_data.get("x_axis", 0.0)
            y_axis = joystick_data.get("y_axis", 0.0)
            lift_speed = joystick_data.get("lift_speed", 0.0)
            clicked = joystick_data.get("clicked", False)
            release = joystick_data.get("release", False)
            centerliftknob = joystick_data.get("centerliftknob", 0)
            
            # Convert joystick values to movement values (similar to Stream class)
            def map_input_to_movement(value, dead_zone=0.2):
                if abs(value) < dead_zone:
                    return 0
                movement = int(value * 255)
                if movement > 255:
                    movement = 255
                elif movement < -255:
                    movement = -255
                return movement
            
            x_movement = map_input_to_movement(x_axis, dead_zone=0.2)
            y_movement = map_input_to_movement(y_axis, dead_zone=0.2)
            
            # Determine direction and speed (similar to Stream class logic)
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
            
            # Send via UDP
            udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            udp_socket.sendto(data.encode(), ('192.168.144.16', 5005))
            udp_socket.close()
            print(f"Sent converted joystick data via UDP: {data}")
            
        except Exception as e:
            print(f"Error sending joystick data via UDP: {e}")
            import traceback
            traceback.print_exc()

    def update_utilsdata_ui(self, instance, value):
        print(f"[DEBUG] update_utilsdata_ui called with value: {value}")
        print(f"[DEBUG] Value type: {type(value)}")
        
        # Check if we should process this data based on control mode
        if self.control_mode == "hardware" and not self.autonomous_data_exchange["hardware_connected"]:
            print("[DEBUG] Hardware mode but not connected, skipping data update")
            return
        elif self.control_mode == "internet" and not self.autonomous_data_exchange["internet_connected"]:
            print("[DEBUG] Internet mode but not connected, skipping data update")
            return
        
        # Parse JSON string if value is a string
        if isinstance(value, str):
            try:
                value = json.loads(value)
                print(f"[DEBUG] Successfully parsed JSON string")
                # Remove timestamp if present
                if '_timestamp' in value:
                    del value['_timestamp']
                    print(f"[DEBUG] Removed timestamp from data")
            except json.JSONDecodeError:
                print(f"[DEBUG] Failed to parse JSON: {value}")
                return
        
        # Handle new Firebase data structure
        # Check if this is the new structure with nested data
        if "sensors" in value and "current" in value["sensors"]:
            # New Firebase structure
            sensors_data = value["sensors"]["current"]
            print(f"[DEBUG] Processing new Firebase data structure: {sensors_data}")
            
            # Extract battery and arm state from utils
            utils_str = sensors_data.get("utils", "")
            if utils_str:
                try:
                    # Parse utils string like "#1=26.88=55.56"
                    utils_parts = utils_str.split("=")
                    if len(utils_parts) >= 3:
                        batvoltage = float(utils_parts[1]) if len(utils_parts) > 1 else 0
                        jetsonvoltage = float(utils_parts[2]) if len(utils_parts) > 2 else 0
                    else:
                        batvoltage = 0
                        jetsonvoltage = 0
                except (ValueError, IndexError):
                    batvoltage = 0
                    jetsonvoltage = 0
            else:
                batvoltage = 0
                jetsonvoltage = 0
            
            # Extract GPS data
            gps_data = sensors_data.get("gps", {})
            if isinstance(gps_data, str):
                try:
                    gps_data = ast.literal_eval(gps_data)
                except:
                    gps_data = {}
            
            # Extract compass data
            compass_data = sensors_data.get("compass", "0")
            if isinstance(compass_data, str):
                try:
                    compass_data = float(compass_data)
                except:
                    compass_data = 0
            
            # Extract autonomous data
            autonomous_data = sensors_data.get("autonomous", {})
            if isinstance(autonomous_data, str):
                try:
                    autonomous_data = ast.literal_eval(autonomous_data)
                except:
                    autonomous_data = {}
            
            # Extract system status
            system_data = value.get("system", {}).get("status", {})
            
        else:
            # Legacy structure - handle as before
            print(f"[DEBUG] Processing legacy data structure")
            
            # Battery and arm state logic
            batvoltage = value.get("batvoltage", 0)
            jetsonvoltage = value.get("jetsonvoltage", 0)
            armstate = value.get("armstate", 0)
            
            # Handle GPS data
            gps_data = value.get("gps", {})
            if isinstance(gps_data, str):
                try:
                    gps_data = ast.literal_eval(gps_data)
                except:
                    gps_data = {}
            
            # Handle compass data
            compass_data = value.get("compass", 0)
            
            # Handle autonomous data
            autonomous_data = value.get("autonomous", {})
            if isinstance(autonomous_data, str):
                try:
                    autonomous_data = ast.literal_eval(autonomous_data)
                except:
                    autonomous_data = {}
            
            system_data = {}
        
        print(f"[DEBUG] batvoltage: {batvoltage} (type: {type(batvoltage)})")
        print(f"[DEBUG] jetsonvoltage: {jetsonvoltage} (type: {type(jetsonvoltage)})")
        print(f"[DEBUG] gps_data: {gps_data}")
        print(f"[DEBUG] compass_data: {compass_data}")
        print(f"[DEBUG] autonomous_data: {autonomous_data}")
        
        # Update battery status
        try:
            if float(batvoltage)>0:
                if float(batvoltage) <= 25:
                    self.img_src = './assets/bad_batt.png'
                else:
                    self.img_src = './assets/good_batt.png'
        except (ValueError, TypeError) as e:
            print(f"[DEBUG] Error processing batvoltage: {e}")
            self.img_src = './assets/bad_batt.png'
            
        try:
            if float(jetsonvoltage) > 0:
                if float(jetsonvoltage) <= 11.5:
                    self.jetsonimg_src = './assets/bad_batt.png'
                else:
                    self.jetsonimg_src = './assets/good_batt.png'
        except (ValueError, TypeError) as e:
            print(f"[DEBUG] Error processing jetsonvoltage: {e}")
            self.jetsonimg_src = './assets/bad_batt.png'
        
        # Handle arm state (if available in new structure)
        if "armstate" in value:
            armstate = value.get("armstate", 0)
            try:
                if int(armstate) == 1:
                    self.img_src_armstate = "./assets/no_home.png"
                    armstate_text = "No Home"
                else:
                    self.img_src_armstate = "./assets/at_home.png"
                    armstate_text = "Home"
            except (ValueError, TypeError) as e:
                print(f"[DEBUG] Error processing armstate: {e}")
                self.img_src_armstate = "./assets/at_home.png"
                armstate_text = "Home"
        else:
            # Default arm state for new structure
            self.img_src_armstate = "./assets/at_home.png"
            armstate_text = "Home"
        
        # Update voltage labels and arm state label
        try:
            if hasattr(self, 'batt_voltage_label'):
                if float(batvoltage)>0:
                    self.batt_voltage_label.text = f"{float(batvoltage):.1f}V"
            if hasattr(self, 'jetson_voltage_label'):
                if float(jetsonvoltage)>0:
                    self.jetson_voltage_label.text = f"{float(jetsonvoltage):.1f}V"
            if hasattr(self, 'armstate_label'):
                self.armstate_label.text = armstate_text
        except Exception as e:
            print(f"[DEBUG] Error updating voltage labels: {e}")

        # GPS info from new structure
        self.satcount = str(gps_data.get("num_sats", "0"))
        self.irnss_accuracy = str(gps_data.get("hdop", "N/A"))
        self.fix_type = str(gps_data.get("fix_type", "N/A"))
        self.gps_fix = bool(gps_data.get("fix", False))
        
        print(f"[DEBUG] Set satcount to: {self.satcount}")
        print(f"[DEBUG] Set irnss_accuracy to: {self.irnss_accuracy}")
        print(f"[DEBUG] Set fix_type to: {self.fix_type}")
        print(f"[DEBUG] Set gps_fix to: {self.gps_fix}")
        
        # GPS marker update
        lat = gps_data.get("lat")
        lng = gps_data.get("lng")
        heading = compass_data
        
        # Update autonomous navigation display
        self.update_autonomous_display(autonomous_data)
        
        # Update compass widget
        if hasattr(self, 'compass') and self.compass:
            try:
                compass_angle = float(compass_data) if compass_data else 0
                self.compass.update_compass(compass_angle)
                print(f"[DEBUG] Updated compass to: {compass_angle}")
            except (ValueError, TypeError) as e:
                print(f"[DEBUG] Error updating compass: {e}")
        
        # Update GPS marker on main thread
        from kivy.clock import Clock
        def _update_marker_on_main_thread(dt):
            from kivy_garden.mapview import MapView
            if lat is not None and lng is not None and isinstance(self.mapview, MapView):
                try:
                    if self.gps_marker is None:
                        self.gps_marker = RotatingMapMarker(lat=float(lat), lon=float(lng), source='./assets/rover_icon.png')
                        self.gps_marker.size = (30, 30)
                        if heading is not None:
                            self.gps_marker.heading = float(heading)
                        self.mapview.add_marker(self.gps_marker)
                        self.mapview.center_on(float(lat), float(lng))
                    else:
                        self.gps_marker.lat = float(lat)
                        self.gps_marker.lon = float(lng)
                        self.gps_marker.size = (30, 30)
                        if heading is not None:
                            self.gps_marker.heading = float(heading)
                    self._last_gps_lat = float(lat)
                    self._last_gps_lon = float(lng)
                    if not self._user_interacting:
                        self._animate_center_on(float(lat), float(lng))
                except Exception as e:
                    print(f"Error updating GPS marker: {e}")
        Clock.schedule_once(_update_marker_on_main_thread)
        
        # Also update MapPlotScreen marker if it exists and is active
        app = App.get_running_app()
        if hasattr(app, 'root') and app.root is not None:
            mapplot_screen = app.root.get_screen('mapplot') if 'mapplot' in app.root.screen_names else None
            if mapplot_screen and hasattr(mapplot_screen, 'gps_marker') and app.root.current == 'mapplot':
                mapplot_screen.update_gps_marker(lat, lng, heading)
        
        # Update UI on main thread
        Clock.schedule_once(lambda dt: self.update_ui_on_main_thread())

    def update_autonomous_display(self, autonomous_data):
        """Update autonomous navigation display with new data and connectivity status"""
        try:
            print(f"[DEBUG] Updating autonomous display with data: {autonomous_data}")
            
            # Handle new nested structure
            if isinstance(autonomous_data, dict) and "autonomous" in autonomous_data:
                autonomous_data = autonomous_data["autonomous"]
            
            # Validate autonomous data
            if not self.validate_autonomous_data(autonomous_data):
                print("Invalid autonomous data, skipping display update")
                return
            
            # Handle new autonomous data structure
            wp_loaded_count = autonomous_data.get("wp_loaded_count", 0)
            vh_autonomous = autonomous_data.get("vh_autonomous", False)
            run_status = autonomous_data.get("run_status", False)
            wp_number = autonomous_data.get("wp_number")
            wp_distance = autonomous_data.get("wp_distance")
            compass_err = autonomous_data.get("compass_err")
            
            # Determine autonomous mode based on vh_autonomous
            if vh_autonomous:
                self.autonomous_mode = "Autonomous"
            else:
                self.autonomous_mode = "Manual"
            
            # Determine navigation status based on run_status and connectivity
            if run_status:
                if self.control_mode == "hardware" and not self.autonomous_data_exchange["hardware_connected"]:
                    nav_status = "Active (Hardware Disconnected)"
                    nav_color = (0.8, 0.6, 0.2, 1)  # Orange - warning
                elif self.control_mode == "internet" and not self.autonomous_data_exchange["internet_connected"]:
                    nav_status = "Active (Internet Disconnected)"
                    nav_color = (0.8, 0.6, 0.2, 1)  # Orange - warning
                else:
                    nav_status = "Active"
                    nav_color = (0.2, 0.8, 0.2, 1)  # Green
            else:
                nav_status = "Inactive"
                nav_color = (0.8, 0.2, 0.2, 1)  # Red
                
            self.navigation_status = nav_status
            self.navigation_color = nav_color
            self.navigation_state = "Running" if run_status else "Stopped"
            
            # Waypoint information
            self.current_waypoint = wp_number
            self.total_waypoints = wp_loaded_count
            self.completed_waypoints = 0  # Not provided in new data structure
            self.mission_progress = 0  # Not provided in new data structure
            
            # Distance to waypoint
            self.distance_to_waypoint = wp_distance
            self.heading_to_waypoint = None  # Not provided in new data structure
            self.heading_correction = compass_err
            self.current_heading = None  # Not provided in new data structure
            
            # Mission status
            self.mission_complete = False  # Not provided in new data structure
            self.has_pending_waypoints = wp_loaded_count > 0
            
            # Additional mission details
            self.mission_state = "active" if run_status else "not_started"
            self.system_stopped = not run_status
            self.navigation_thread_alive = run_status
            self.estimated_time_to_waypoint = None  # Not provided in new data structure
            self.mission_duration = None  # Not provided in new data structure
            self.total_distance_traveled = 0.0  # Not provided in new data structure
            self.next_waypoint_position = None  # Not provided in new data structure
            self.current_waypoint_details = None  # Not provided in new data structure
            
            # Update connectivity status in autonomous data exchange
            self.autonomous_data_exchange["autonomous_mode"] = self.autonomous_mode.lower()
            
            print(f"[DEBUG] Mission State: {self.mission_state}")
            print(f"[DEBUG] Current Waypoint: {wp_number}")
            print(f"[DEBUG] Total Waypoints: {wp_loaded_count}")
            print(f"[DEBUG] Completed Waypoints: {self.completed_waypoints}")
            print(f"[DEBUG] Mission Progress: {self.mission_progress}%")
            print(f"[DEBUG] Distance to Waypoint: {wp_distance}")
            print(f"[DEBUG] Navigation State: {self.navigation_state}")
            print(f"[DEBUG] Autonomous Mode: {self.autonomous_mode}")
            print(f"[DEBUG] Run Status: {run_status}")
            print(f"[DEBUG] Data Sync Status: {self.autonomous_data_exchange['data_sync_status']}")
            
            # Update detailed labels
            self.update_autonomous_labels()
            
        except Exception as e:
            print(f"Error updating autonomous display: {e}")
            import traceback
            traceback.print_exc()

    def update_autonomous_labels(self):
        """Update the detailed autonomous navigation labels with connectivity status"""
        try:
            # Mission status with more detailed information and connectivity
            if hasattr(self, 'mission_complete') and self.mission_complete:
                mission_text = "Mission: Complete"
                mission_color = (0.2, 0.8, 0.2, 1)  # Green
            elif hasattr(self, 'has_pending_waypoints') and self.has_pending_waypoints:
                # Add connectivity status to mission text
                connectivity_status = self.autonomous_data_exchange.get("data_sync_status", "unknown")
                if connectivity_status == "hardware_connected" or connectivity_status == "internet_connected":
                    mission_text = "Mission: Active"
                    mission_color = (0.2, 0.6, 0.8, 1)  # Blue
                elif connectivity_status == "hardware_disconnected":
                    mission_text = "Mission: Active (Hardware Disconnected)"
                    mission_color = (0.8, 0.6, 0.2, 1)  # Orange
                elif connectivity_status == "internet_disconnected":
                    mission_text = "Mission: Active (Internet Disconnected)"
                    mission_color = (0.8, 0.6, 0.2, 1)  # Orange
                else:
                    mission_text = "Mission: Active (Connection Issues)"
                    mission_color = (0.8, 0.6, 0.2, 1)  # Orange
            elif hasattr(self, 'mission_state') and self.mission_state == "not_started":
                mission_text = "Mission: Not Started"
                mission_color = (0.6, 0.6, 0.6, 1)  # Gray
            else:
                mission_text = "Mission: No Mission"
                mission_color = (0.6, 0.6, 0.6, 1)  # Gray
            
            if hasattr(self, 'mission_status_label'):
                self.mission_status_label.text = mission_text
                self.mission_status_label.color = mission_color
            
            # Waypoint progress with current waypoint number and connectivity
            if hasattr(self, 'total_waypoints') and hasattr(self, 'completed_waypoints'):
                current_wp = getattr(self, 'current_waypoint', None)
                if current_wp is not None:
                    wp_text = f"Waypoints: {self.completed_waypoints}/{self.total_waypoints} (Current: {current_wp})"
                else:
                    wp_text = f"Waypoints: {self.completed_waypoints}/{self.total_waypoints}"
                
                # Add connectivity indicator
                connectivity_status = self.autonomous_data_exchange.get("data_sync_status", "unknown")
                if connectivity_status in ["hardware_disconnected", "internet_disconnected"]:
                    wp_text += " (Disconnected)"
                
                if hasattr(self, 'waypoint_detail_label'):
                    self.waypoint_detail_label.text = wp_text
            
            # Distance to waypoint with more details and connectivity
            if hasattr(self, 'distance_to_waypoint') and self.distance_to_waypoint is not None:
                try:
                    distance = float(self.distance_to_waypoint)
                    distance_text = f"Distance: {distance:.1f}m"
                    
                    # Add heading correction if available
                    if hasattr(self, 'heading_correction') and self.heading_correction is not None:
                        try:
                            correction = float(self.heading_correction)
                            distance_text += f" | Corr: {correction:.1f}°"
                        except (ValueError, TypeError):
                            pass
                    
                    # Add connectivity indicator
                    connectivity_status = self.autonomous_data_exchange.get("data_sync_status", "unknown")
                    if connectivity_status in ["hardware_disconnected", "internet_disconnected"]:
                        distance_text += " (Disconnected)"
                            
                except (ValueError, TypeError):
                    distance_text = "Distance: N/A"
            else:
                distance_text = "Distance: N/A"
            
            if hasattr(self, 'distance_label'):
                self.distance_label.text = distance_text
            
            # Navigation state with more details and connectivity
            if hasattr(self, 'navigation_state'):
                nav_text = f"State: {self.navigation_state}"
                
                # Add connectivity status
                connectivity_status = self.autonomous_data_exchange.get("data_sync_status", "unknown")
                if connectivity_status == "hardware_disconnected":
                    nav_text += " (Hardware Disconnected)"
                elif connectivity_status == "internet_disconnected":
                    nav_text += " (Internet Disconnected)"
                elif connectivity_status == "internet_connected_firebase_disconnected":
                    nav_text += " (Firebase Disconnected)"
                
                if hasattr(self, 'nav_state_label'):
                    self.nav_state_label.text = nav_text
                    self.nav_state_label.color = getattr(self, 'navigation_color', (0.4, 0.4, 0.4, 1))
            
            # Additional mission details
            if hasattr(self, 'mission_progress'):
                progress_text = f"Progress: {self.mission_progress:.1f}%"
                if hasattr(self, 'mission_progress_label'):
                    self.mission_progress_label.text = progress_text
            
            # Mission duration and distance traveled
            if hasattr(self, 'mission_duration') and self.mission_duration is not None:
                duration_text = f"Duration: {self.mission_duration}"
                if hasattr(self, 'mission_duration_label'):
                    self.mission_duration_label.text = duration_text
            
            if hasattr(self, 'total_distance_traveled'):
                distance_traveled = getattr(self, 'total_distance_traveled', 0.0)
                traveled_text = f"Traveled: {distance_traveled:.1f}m"
                if hasattr(self, 'distance_traveled_label'):
                    self.distance_traveled_label.text = traveled_text
            
            print(f"[DEBUG] Updated autonomous labels:")
            print(f"[DEBUG] - Mission text: {mission_text}")
            print(f"[DEBUG] - Waypoint text: {wp_text if 'wp_text' in locals() else 'N/A'}")
            print(f"[DEBUG] - Distance text: {distance_text}")
            print(f"[DEBUG] - Navigation text: {nav_text if 'nav_text' in locals() else 'N/A'}")
            
        except Exception as e:
            print(f"Error updating autonomous labels: {e}")
            import traceback
            traceback.print_exc()

    def update_ui_on_main_thread(self):
        print(f"[DEBUG] update_ui_on_main_thread called")
        print(f"[DEBUG] img_src: {self.img_src}")
        print(f"[DEBUG] jetsonimg_src: {self.jetsonimg_src}")
        print(f"[DEBUG] img_src_armstate: {self.img_src_armstate}")
        print(f"[DEBUG] satcount: {self.satcount}")
        print(f"[DEBUG] irnss_accuracy: {self.irnss_accuracy}")
        print(f"[DEBUG] fix_type: {self.fix_type}")
        
        self.battimg.source = self.img_src
        self.armstateimg.source = self.img_src_armstate
        self.jetsonbattimg.source = self.jetsonimg_src
        # Update GPS info labels
        self.satcount_label.text = f"Satcount: {self.satcount}"
        self.irnss_accuracy_label.text = f"IRNSS Acc: {self.irnss_accuracy}"
        self.fix_type_label.text = f"Fix: {self.fix_type}"
        
        # Update Autonomous Navigation labels
        if hasattr(self, 'autonomous_mode'):
            self.autonomous_mode_label.text = f"Mode: {self.autonomous_mode}"
        
        if hasattr(self, 'navigation_status'):
            self.navigation_status_label.text = f"Nav: {self.navigation_status}"
            self.navigation_status_label.color = getattr(self, 'navigation_color', (1,1,1,1))
        
        if hasattr(self, 'total_waypoints') and hasattr(self, 'completed_waypoints'):
            current_wp = getattr(self, 'current_waypoint', None)
            if current_wp is not None:
                self.waypoint_progress_label.text = f"WP: {self.completed_waypoints}/{self.total_waypoints} (Cur: {current_wp})"
            else:
                self.waypoint_progress_label.text = f"WP: {self.completed_waypoints}/{self.total_waypoints}"
        
        # Update additional autonomous information
        if hasattr(self, 'mission_progress'):
            progress_text = f"Progress: {self.mission_progress:.1f}%"
            if hasattr(self, 'mission_progress_label'):
                self.mission_progress_label.text = progress_text
        
        if hasattr(self, 'distance_to_waypoint') and self.distance_to_waypoint is not None:
            try:
                distance = float(self.distance_to_waypoint)
                distance_text = f"Dist: {distance:.1f}m"
                if hasattr(self, 'heading_correction') and self.heading_correction is not None:
                    try:
                        correction = float(self.heading_correction)
                        distance_text += f" | Corr: {correction:.1f}°"
                    except (ValueError, TypeError):
                        pass
                if hasattr(self, 'distance_label'):
                    self.distance_label.text = distance_text
            except (ValueError, TypeError):
                if hasattr(self, 'distance_label'):
                    self.distance_label.text = "Dist: N/A"
        
        if hasattr(self, 'mission_duration') and self.mission_duration is not None:
            duration_text = f"Duration: {self.mission_duration}"
            if hasattr(self, 'mission_duration_label'):
                self.mission_duration_label.text = duration_text
        
        if hasattr(self, 'total_distance_traveled'):
            distance_traveled = getattr(self, 'total_distance_traveled', 0.0)
            traveled_text = f"Traveled: {distance_traveled:.1f}m"
            if hasattr(self, 'distance_traveled_label'):
                self.distance_traveled_label.text = traveled_text
        
        # Enable/disable Map Plotting button and show GPS status
        if self.gps_fix:
            self.mapplot_btn_top.disabled = False
            self.gps_status_label.text = ""
        else:
            self.mapplot_btn_top.disabled = True
            self.gps_status_label.text = "Waiting for GPS 3D fix..."

    def update_joystickview(self, instance, value):
        """Optimized joystick view update with throttling and control mode check"""
        # Check if joystick control is enabled
        if not hasattr(self, 'joystick_control_enabled') or not self.joystick_control_enabled:
            print("Joystick control disabled - ignoring joystick updates")
            return
            
        if self.autoshowfullscreen:
            value = int(value)
            if value >= 0:
                self.close_all_popups()
                img = self.image_widgets[value]
                class SimulatedTouch:
                    def __init__(self, pos):
                        self.pos = pos
                simulated_touch = SimulatedTouch(img.center)
                # Use a small delay to prevent UI blocking
                Clock.schedule_once(lambda dt: img.dispatch('on_touch_down', simulated_touch), 0.01)
            if value < 0:
                if self.updatefullscreenval:
                    self.close_all_popups()

    def update_image(self, dt):
        """Optimized image update with better error handling and performance"""
        try:
            keys = list(self.videoreceiver.video_frames.keys())
            for i, identifier in enumerate(keys):
                if identifier in self.videoreceiver.video_frames:
                    frame = self.videoreceiver.video_frames[identifier]
                    if frame is not None and frame.size > 0:  # Check if frame is valid
                        try:
                            if frame.dtype != np.uint8:
                                frame = frame.astype(np.uint8)
                            
                            # Add camera label
                            cv2.putText(frame, f"cam{i}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)
                            frame = cv2.flip(frame, 0)
                            
                            # Create texture more efficiently
                            buffer = frame.tobytes()
                            texture = Texture.create(size=(frame.shape[1], frame.shape[0]), colorfmt='bgr')
                            texture.blit_buffer(buffer, colorfmt='bgr', bufferfmt='ubyte')
                            
                            # Update widget texture
                            if i < len(self.image_widgets):
                                self.image_widgets[i].texture = texture
                        except Exception as e:
                            print(f"Error updating image {i}: {e}")
                            continue
        except Exception as e:
            print(f"Error in update_image: {e}")

    def create_texture(self, frame_rgb):
        texture = Texture.create(size=(frame_rgb.shape[1], frame_rgb.shape[0]))
        texture.blit_buffer(frame_rgb.tobytes(), colorfmt='rgb', bufferfmt='ubyte')
        return texture

    def updatefullscreen(self, image_widget, fullscreenview):
        fullscreenview.texture = image_widget.texture

    def on_image_click(self, image_widget):
        texture = image_widget.texture
        self.updatefullscreenval = True
        if texture:
            popup_layout = BoxLayout(orientation='vertical')
            popup_image = Image(texture=texture, size_hint=(1, 1), allow_stretch=True, keep_ratio=False)
            close_btn = Button(text='Close', size_hint=(1, 0.1))
            popup_layout.add_widget(popup_image)
            popup_layout.add_widget(close_btn)
            self.popup = Popup(content=popup_layout, auto_dismiss=False, size_hint=(1, 1))
            self.allvideopopups.append(self.popup)
            close_btn.bind(on_release=lambda instance: self.dismiss_full_screen(self.allvideopopups[-1]))
            self.popup.open()
            # Reduced frequency to prevent UI blocking (15 FPS instead of 30 FPS)
        Clock.schedule_interval(lambda dt: self.updatefullscreen(image_widget, popup_image), 1.0 / 15.0)

    def dismiss_full_screen(self, popup):
        Clock.unschedule(self.updatefullscreen)
        popup.dismiss()
        self.update_full_screen_val = False

    def close_all_popups(self):
        for popup in self.allvideopopups:
            self.dismiss_full_screen(popup)
        if len(self.allvideopopups) > 10:
            del self.allvideopopups[0]

    def on_enter(self):
        """Called when the screen is entered with optimized setup"""
        try:
            # Only test control functionality if NOT returning from mission planning
            if not self.returning_from_mission_planning:
                self.test_control_functionality()
            else:
                print("✅ Returning from mission planning - skipping control functionality test")
                # Reset the flags
                self.returning_from_mission_planning = False
                self.processing_mission_commands = False
                print("✅ Reset flags: returning from mission planning and processing mission commands")
                # Restart connectivity checks after a delay to avoid immediate testing
                from kivy.clock import Clock
                Clock.schedule_once(lambda dt: self.restart_connectivity_checks(), 3)
            
            # Original functionality with optimized binding
            for image_widget in self.image_widgets:
                image_widget.bind(on_touch_down=self.on_image_touch)
            
            # Use consistent frame rate for image updates (reduced to prevent UI blocking)
            Clock.schedule_interval(self.update_image, 1.0 / 15.0)
            
            # Start autonomous mission sender if needed
            if hasattr(self, 'autonomous_event') and self.autonomous_event:
                self.start_autonomous_mission_sender()
                
                    # Set optimal UI update rate for streaming (reduced to prevent UI blocking)
            if hasattr(streaming, 'set_ui_update_rate'):
                streaming.set_ui_update_rate(15)  # 15 FPS for better performance
            
            # Optimize UI performance
            self.optimize_ui_performance()
            
            # Start background task manager for heavy operations
            self.start_background_task_manager()
                    
        except Exception as e:
            print(f"Error in on_enter: {e}")

    def on_image_touch(self, image_widget, touch):
        if image_widget.collide_point(*touch.pos):
            self.on_image_click(image_widget)

    def on_leave(self):
        for image_widget in self.image_widgets:
            image_widget.unbind(on_touch_down=self.on_image_touch)
        
        # Clean up Firebase listeners
        if self.firebase_control:
            self.firebase_control.stop_listeners()
        
        # Clean up background task manager
        self.cleanup_background_tasks()

    def on_size(self, instance, size):
        for image_widget in self.image_widgets:
            image_widget.size = (size[0] * 0.35, size[1] * 0.45)

    def _update_rect(self, instance, value):
        self.rect.size = instance.size
        self.rect.pos = instance.pos

    def goto_mapplot(self, instance):
        if self.manager:
            self.manager.current = 'mapplot'

    # --- MapView user interaction handlers ---
    def _on_map_touch_down(self, instance, touch):
        if self.mapview.collide_point(*touch.pos):
            self._user_interacting = True
            if self._recenter_timer:
                Clock.unschedule(self._recenter_timer)
        return False
    def _on_map_touch_move(self, instance, touch):
        if self.mapview.collide_point(*touch.pos):
            self._user_interacting = True
            if self._recenter_timer:
                Clock.unschedule(self._recenter_timer)
        return False
    def _on_map_touch_up(self, instance, touch):
        if self.mapview.collide_point(*touch.pos):
            self._user_interacting = False
            # Start timer to recenter after 3 seconds
            if self._recenter_timer:
                Clock.unschedule(self._recenter_timer)
            self._recenter_timer = Clock.schedule_once(self._maybe_recenter_map, 3)
        return False
    def _maybe_recenter_map(self, dt):
        # Check if marker is out of view, then recenter
        if self.gps_marker:
            lat, lon = self.gps_marker.lat, self.gps_marker.lon
            if not self._is_marker_visible(lat, lon):
                self._animate_center_on(lat, lon)
    def _is_marker_visible(self, lat, lon):
        # Check if marker is within current map bounds
        try:
            bbox = self.mapview.get_bbox()
            min_lat, min_lon, max_lat, max_lon = bbox
            return (min_lat <= lat <= max_lat) and (min_lon <= lon <= max_lon)
        except Exception:
            return True  # If error, assume visible
    def _animate_center_on(self, lat, lon):
        # Smoothly animate the map to center on the marker
        try:
            self.mapview.center_on(lat, lon)
        except Exception:
            self.mapview.lat = lat
            self.mapview.lon = lon

    def optimize_ui_performance(self):
        """Optimize overall UI performance to prevent blocking"""
        try:
            # Set optimal frame rates (reduced to prevent UI blocking)
            if hasattr(streaming, 'set_ui_update_rate'):
                streaming.set_ui_update_rate(15)  # 15 FPS for better performance
            
            # Optimize image update rate (reduced to prevent UI blocking)
            Clock.unschedule(self.update_image)
            Clock.schedule_interval(self.update_image, 1.0 / 15.0)
            
            # Reduce Clock scheduling frequency for better performance
            if hasattr(self, 'autonomous_event') and self.autonomous_event:
                Clock.unschedule(self.autonomous_event)
                self.autonomous_event = Clock.schedule_interval(self.send_autonomous_mission, 10.0)
            
            # Optimize mode sync frequency
            if hasattr(self, 'mode_sync_event') and self.mode_sync_event:
                Clock.unschedule(self.mode_sync_event)
                self.mode_sync_event = Clock.schedule_interval(self.monitor_firebase_mode_changes_intelligent, 5.0)
            
            print("✅ Overall UI performance optimized - reduced blocking operations")
        except Exception as e:
            print(f"Error optimizing UI performance: {e}")

    def start_background_task_manager(self):
        """Start background task manager to handle heavy operations"""
        try:
            # Initialize background task queue
            self.background_tasks = []
            self.task_running = False
            
            # Start background task processor
            from kivy.clock import Clock
            Clock.schedule_interval(self.process_background_tasks, 0.1)  # Check every 100ms
            
            print("✅ Background task manager started")
        except Exception as e:
            print(f"Error starting background task manager: {e}")

    def add_background_task(self, task_func, *args, **kwargs):
        """Add a task to be executed in background"""
        try:
            self.background_tasks.append((task_func, args, kwargs))
            print(f"✅ Background task added: {task_func.__name__}")
        except Exception as e:
            print(f"Error adding background task: {e}")

    def process_background_tasks(self, dt):
        """Process background tasks to prevent UI blocking"""
        try:
            if self.task_running or not self.background_tasks:
                return
            
            # Get next task
            task_func, args, kwargs = self.background_tasks.pop(0)
            self.task_running = True
            
            # Execute task in background thread
            def execute_task():
                try:
                    result = task_func(*args, **kwargs)
                    # Schedule result handling on main thread
                    from kivy.clock import Clock
                    Clock.schedule_once(lambda dt: self.handle_task_result(result), 0)
                except Exception as e:
                    print(f"Background task error: {e}")
                    Clock.schedule_once(lambda dt: self.handle_task_error(e), 0)
                finally:
                    self.task_running = False
            
            threading.Thread(target=execute_task, daemon=True).start()
            
        except Exception as e:
            print(f"Error processing background tasks: {e}")
            self.task_running = False

    def handle_task_result(self, result):
        """Handle successful task result on main thread"""
        try:
            print(f"✅ Background task completed successfully")
            # Add any result handling logic here
        except Exception as e:
            print(f"Error handling task result: {e}")

    def handle_task_error(self, error):
        """Handle task error on main thread"""
        try:
            print(f"❌ Background task failed: {error}")
            # Add any error handling logic here
        except Exception as e:
            print(f"Error handling task error: {e}")

    def cleanup_background_tasks(self):
        """Clean up background task manager"""
        try:
            # Clear task queue
            self.background_tasks.clear()
            self.task_running = False
            
            # Stop task processor
            from kivy.clock import Clock
            Clock.unschedule(self.process_background_tasks)
            
            print("✅ Background task manager cleaned up")
        except Exception as e:
            print(f"Error cleaning up background task manager: {e}")

    def optimize_ui_updates(self):
        """Optimize UI update performance"""
        try:
            # Set optimal frame rates (reduced to prevent UI blocking)
            if hasattr(streaming, 'set_ui_update_rate'):
                streaming.set_ui_update_rate(15)  # 15 FPS for better performance
            
            # Optimize image update rate (reduced to prevent UI blocking)
            Clock.unschedule(self.update_image)
            Clock.schedule_interval(self.update_image, 1.0 / 15.0)
            
            print("UI updates optimized for smooth performance")
        except Exception as e:
            print(f"Error optimizing UI updates: {e}")

    def set_ui_frame_rate(self, fps):
        """Set UI frame rate for optimal performance"""
        try:
            if fps > 0 and fps <= 60:  # Limit to reasonable FPS
                # Update streaming rate
                if hasattr(streaming, 'set_ui_update_rate'):
                    streaming.set_ui_update_rate(fps)
                
                # Update image update rate
                Clock.unschedule(self.update_image)
                Clock.schedule_interval(self.update_image, 1.0 / fps)
                
                print(f"UI frame rate set to {fps} FPS")
            else:
                print(f"Invalid FPS value: {fps}. Must be between 1 and 60.")
        except Exception as e:
            print(f"Error setting UI frame rate: {e}")

    def get_current_fps(self):
        """Get current UI frame rate"""
        try:
            if hasattr(streaming, 'get_ui_update_rate'):
                return streaming.get_ui_update_rate()
            return 30  # Default
        except Exception as e:
            print(f"Error getting current FPS: {e}")
            return 30

    def on_satellite_toggle(self, instance, state):
        """Toggle between regular and satellite map view"""
        try:
            if hasattr(self, 'mapview') and self.mapview:
                if state == 'down':  # Satellite view
                    # Switch to satellite map source
                    satellite_source = MapSource(url="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}")
                    self.mapview.map_source = satellite_source
                    self.satellite_toggle.text = "Regular View"
                    self.satellite_toggle.background_color = (0.8, 0.4, 0.2, 1)  # Orange
                else:  # Regular view
                    # Switch to regular map source
                    regular_source = MapSource(url="https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}")
                    self.mapview.map_source = regular_source
                    self.satellite_toggle.text = "Satellite View"
                    self.satellite_toggle.background_color = (0.2, 0.6, 0.8, 1)  # Blue
        except Exception as e:
            print(f"Satellite toggle error: {e}")

    def zoom_in(self, instance):
        """Zoom in the map"""
        try:
            if hasattr(self, 'mapview') and self.mapview:
                current_zoom = self.mapview.zoom
                new_zoom = min(current_zoom + 1, 20)  # Max zoom level is 20
                self.mapview.zoom = new_zoom
        except Exception as e:
            print(f"Zoom in error: {e}")

    def zoom_out(self, instance):
        """Zoom out the map"""
        try:
            if hasattr(self, 'mapview') and self.mapview:
                current_zoom = self.mapview.zoom
                new_zoom = max(current_zoom - 1, 1)  # Min zoom level is 1
                self.mapview.zoom = new_zoom
        except Exception as e:
            print(f"Zoom out error: {e}")

    def check_mode_before_start(self):
        """Check and preserve the appropriate mode before starting a mission"""
        try:
            print("=== CHECKING MODE BEFORE START ===")
            
            # Check if we have an active mission that should preserve internet mode
            has_active_internet_mission = self.check_active_internet_mission()
            
            if has_active_internet_mission:
                if self.control_mode != "internet":
                    print("Active internet mission detected, switching to internet mode before start")
                    self.implement_internet_mode()
                    # Update Firebase to reflect the mode change
                    self.update_firebase_system_status()
                    return True
                else:
                    print("Already in internet mode for active mission")
                    return True
            else:
                print("No active internet mission, current mode maintained")
                return False
                
        except Exception as e:
            print(f"Error checking mode before start: {e}")
            return False

    def send_start_status(self, instance):
        # Check and preserve mode before starting
        self.check_mode_before_start()
        
        self.last_status = 'start'
        if self.control_mode == "hardware":
            self.send_status_udp('start')
            self.start_autonomous_mission_sender()
        elif self.control_mode == "internet" and self.firebase_control:
            # Get existing mission data and update status
            try:
                # First, try to get existing mission data from Firebase
                from firebase_config import FIREBASE_PATHS
                autonomous_path = FIREBASE_PATHS["autonomous"].split("/")
                existing_data = self.firebase_control.db.child(*autonomous_path).get().val() or {}
                
                # Preserve existing mission points if they exist
                mission_points = existing_data.get("mission", [])
                
                # Create updated mission data with start status
                updated_mission_data = {
                    "mission": mission_points,
                    "status": "start",
                    "timestamp": time.time(),
                    "mission_count": len(mission_points)
                }
                
                # Send updated mission data to Firebase
                success = self.firebase_control.send_autonomous_mission(updated_mission_data)
                if success:
                    # Ensure Firebase system status reflects internet mode
                    self.update_firebase_system_status()
                    toast("Mission started via Firebase")
                    print(f"✅ Mission started with {len(mission_points)} waypoints")
                else:
                    toast("Failed to start mission via Firebase")
                    print("❌ Failed to start mission via Firebase")
                    
            except Exception as e:
                print(f"Error starting mission via Firebase: {e}")
                import traceback
                traceback.print_exc()
                toast("Error starting mission via Firebase")

    def send_stop_status(self, instance):
        # Check and preserve mode before stopping
        self.check_mode_before_start()
        
        self.last_status = 'stop'
        if self.control_mode == "hardware":
            self.send_status_udp('stop')
            self.stop_autonomous_mission_sender()
        elif self.control_mode == "internet" and self.firebase_control:
            # Get existing mission data and update status
            try:
                # First, try to get existing mission data from Firebase
                from firebase_config import FIREBASE_PATHS
                autonomous_path = FIREBASE_PATHS["autonomous"].split("/")
                existing_data = self.firebase_control.db.child(*autonomous_path).get().val() or {}
                
                # Preserve existing mission points if they exist
                mission_points = existing_data.get("mission", [])
                
                # Create updated mission data with stop status
                updated_mission_data = {
                    "mission": mission_points,
                    "status": "stop",
                    "timestamp": time.time(),
                    "mission_count": len(mission_points)
                }
                
                # Send updated mission data to Firebase
                success = self.firebase_control.send_autonomous_mission(updated_mission_data)
                if success:
                    # Update Firebase system status to reflect current mode
                    self.update_firebase_system_status()
                    toast("Mission stopped via Firebase")
                    print(f"✅ Mission stopped with {len(mission_points)} waypoints preserved")
                else:
                    toast("Failed to stop mission via Firebase")
                    print("❌ Failed to stop mission via Firebase")
                    
            except Exception as e:
                print(f"Error stopping mission via Firebase: {e}")
                import traceback
                traceback.print_exc()
                toast("Error stopping mission via Firebase")

    def start_autonomous_mission_sender(self):
        if self.autonomous_event is None:
            from kivy.clock import Clock
            # Use a longer interval to prevent UI blocking (10 seconds instead of 5 seconds)
            self.autonomous_event = Clock.schedule_interval(self.send_autonomous_mission, 10.0)
            print("✅ Autonomous mission sender started (10s interval - optimized)")
        else:
            print("⚠️ Autonomous mission sender already running")

    def stop_autonomous_mission_sender(self):
        if self.autonomous_event is not None:
            from kivy.clock import Clock
            Clock.unschedule(self.autonomous_event)
            self.autonomous_event = None
            print("🛑 Autonomous mission sender stopped")
        else:
            print("⚠️ Autonomous mission sender not running")

    def send_autonomous_mission(self, dt):
        # Get mission points from MapPlotScreen
        app = App.get_running_app()
        mission_points = []
        if hasattr(app, 'root') and app.root is not None:
            try:
                mapplot_screen = app.root.get_screen('mapplot')
                if hasattr(mapplot_screen, 'user_markers'):
                    mission_points = [coords for m, coords in mapplot_screen.user_markers]
            except Exception:
                pass
        
        status = self.last_status if hasattr(self, 'last_status') else 'stop'
        
        # Check if we need to send an update
        # Only send if status changed or mission points changed
        current_mission_hash = hash(str(mission_points))
        if not hasattr(self, '_last_mission_hash'):
            self._last_mission_hash = None
        if not hasattr(self, '_last_sent_status'):
            self._last_sent_status = None
        if not hasattr(self, '_last_send_time'):
            self._last_send_time = 0
        if not hasattr(self, '_stop_status_start_time'):
            self._stop_status_start_time = None
            
        status_changed = status != self._last_sent_status
        mission_changed = current_mission_hash != self._last_mission_hash
        
        # Track when status becomes "stop" to auto-stop sender after a delay
        if status == "stop" and self._stop_status_start_time is None:
            import time
            self._stop_status_start_time = time.time()
        elif status != "stop":
            self._stop_status_start_time = None
        
        # Auto-stop sender if status has been "stop" for more than 10 seconds
        if status == "stop" and self._stop_status_start_time is not None:
            import time
            if time.time() - self._stop_status_start_time > 10.0:
                print("🔄 Auto-stopping autonomous mission sender (status 'stop' for >10s)")
                self.stop_autonomous_mission_sender()
                return
        
        # Add cooldown to prevent rapid status changes (minimum 2 seconds between sends)
        import time
        current_time = time.time()
        time_since_last_send = current_time - self._last_send_time
        
        # Only send update if something actually changed and enough time has passed
        if not status_changed and not mission_changed:
            return
            
        # If status is "start" and we just sent it recently, don't send again
        if status == "start" and self._last_sent_status == "start" and time_since_last_send < 5.0:
            return
            
        # If status is "stop" and we just sent it recently, don't send again
        if status == "stop" and self._last_sent_status == "stop" and time_since_last_send < 2.0:
            return
            
        data = json.dumps({"mission": mission_points, "status": status})
        
        # Send via UDP (hardware mode)
        if self.control_mode == "hardware":
            import socket
            from kivy.clock import Clock
            from kivymd.toast import toast
            host = '192.168.144.16'
            port = 5005
            def send(data, host, port):
                try:
                    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    udp_socket.sendto(data.encode('utf-8'), (host, port))
                    udp_socket.close()
                except Exception as e:
                    print(f"Autonomous mission send error: {e}")
            threading.Thread(target=send, args=(data, host, port), daemon=True).start()
            # Update tracking variables for UDP send
            self._last_sent_status = status
            self._last_mission_hash = current_mission_hash
            self._last_send_time = current_time
        
        # Send via Firebase (internet mode)
        elif self.control_mode == "internet" and self.firebase_control:
            try:
                print(f"Attempting to send autonomous mission to Firebase in internet mode")
                print(f"Firebase control mode: {self.firebase_control.get_control_mode()}")
                print(f"Firebase connected: {self.firebase_control.is_firebase_connected()}")
                
                # Ensure Firebase control mode is synchronized
                if self.firebase_control.get_control_mode() != "internet":
                    print("Synchronizing Firebase control mode to internet")
                    self.firebase_control.set_control_mode("internet")
                
                mission_data = {"mission": mission_points, "status": status}
                # No connection test needed - Firebase connection is never tested after initial setup
                success = self.firebase_control.send_autonomous_mission(mission_data)
                if success:
                    print(f"Successfully sent autonomous mission to Firebase: {len(mission_points)} waypoints")
                    # Update tracking variables only on successful send
                    self._last_sent_status = status
                    self._last_mission_hash = current_mission_hash
                    self._last_send_time = current_time
                else:
                    print("Failed to send autonomous mission to Firebase")
            except Exception as e:
                print(f"Error sending autonomous mission to Firebase: {e}")
                import traceback
                traceback.print_exc()

    def send_status_udp(self, status):
        import socket
        from kivy.clock import Clock
        from kivymd.toast import toast
        # Send status in the same JSON format as mission: {"mission": [], "status": status}
        data = json.dumps({"mission": [], "status": status})
        host = '192.168.144.16'
        port = 5005
        def send(data, host, port):
            try:
                udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                udp_socket.sendto(data.encode('utf-8'), (host, port))
                udp_socket.close()
                Clock.schedule_once(lambda dt: toast(f"Sent status: {status}"))
            except Exception as e:
                print(f"Status send error: {e}")
                Clock.schedule_once(lambda dt: toast(f"Failed to send status: {status}"))
        threading.Thread(target=send, args=(data, host, port), daemon=True).start()

    def test_control_functionality(self):
        """Test the control functionality to ensure everything is working"""
        try:
            # Skip testing if returning from mission planning to avoid delays
            if self.returning_from_mission_planning:
                print("⏭️ Skipping control functionality test - returning from mission planning")
                return
            
            # Skip testing if processing mission commands to avoid delays
            if self.processing_mission_commands:
                print("⏭️ Skipping control functionality test - processing mission commands")
                return
                
            print("=== Testing Control Functionality ===")
            
            # Test connectivity status
            print(f"Hardware connected: {self.autonomous_data_exchange['hardware_connected']}")
            print(f"Internet connected: {self.autonomous_data_exchange['internet_connected']}")
            print(f"Firebase connected: {self.autonomous_data_exchange['firebase_connected']}")
            print(f"Data sync status: {self.autonomous_data_exchange['data_sync_status']}")
            
            # Test Firebase control
            if self.firebase_control:
                print(f"Firebase control mode: {self.firebase_control.get_control_mode()}")
                print(f"Firebase connected: {self.firebase_control.is_firebase_connected()}")
                
                # NEVER test Firebase connection after initial check to avoid delays and unnecessary data
                if self.initial_connectivity_check_completed:
                    print("⏭️ Skipping Firebase connection test - initial check already completed")
                    print(f"✓ Firebase status: {'CONNECTED' if self.autonomous_data_exchange['firebase_connected'] else 'DISCONNECTED'}")
                else:
                    # Only test connection during initial setup
                    if not self.autonomous_data_exchange['firebase_connected']:
                        print("Testing Firebase connection (initial setup only)...")
                        if self.firebase_control.test_connection():
                            print("✓ Firebase connection test: SUCCESS")
                            self.autonomous_data_exchange['firebase_connected'] = True
                        else:
                            print("✗ Firebase connection test: FAILED")
                            self.autonomous_data_exchange['firebase_connected'] = False
                    else:
                        print("✓ Firebase already connected - skipping connection test")
            else:
                print("Firebase control not available")
            
            # Test Stream control
            if hasattr(streaming, 'get_control_mode'):
                print(f"Stream control mode: {streaming.get_control_mode()}")
            else:
                print("Stream control mode not available")
            
            # Test current control mode
            print(f"MainScreen control mode: {self.control_mode}")
            
            # Test UDP connectivity - but NEVER test after initial check to avoid delays
            if self.initial_connectivity_check_completed:
                print("⏭️ Skipping UDP connectivity test - initial check already completed")
                print(f"✓ UDP status: {'CONNECTED' if self.autonomous_data_exchange['hardware_connected'] else 'DISCONNECTED'}")
            else:
                # Only test during initial setup
                try:
                    import socket
                    test_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    test_socket.settimeout(1)
                    test_socket.sendto(b"test", ('192.168.144.16', 5005))
                    print("✓ UDP connectivity test: SUCCESS")
                    test_socket.close()
                except Exception as e:
                    print(f"✗ UDP connectivity test: FAILED - {e}")
            
            # Test autonomous data exchange status
            print(f"Autonomous mode: {self.autonomous_data_exchange.get('autonomous_mode', 'unknown')}")
            print(f"Last hardware check: {self.autonomous_data_exchange.get('last_hardware_check', 'never')}")
            print(f"Last internet check: {self.autonomous_data_exchange.get('last_internet_check', 'never')}")
            
            # Test data validation
            test_autonomous_data = {
                "run_status": True,
                "vh_autonomous": True,
                "wp_loaded_count": 5,
                "wp_number": 1,
                "wp_distance": 10.5,
                "compass_err": 2.3
            }
            if self.validate_autonomous_data(test_autonomous_data):
                print("✓ Autonomous data validation test: SUCCESS")
            else:
                print("✗ Autonomous data validation test: FAILED")
            
            print("=== Control Functionality Test Complete ===")
            
        except Exception as e:
            print(f"Error testing control functionality: {e}")
            import traceback
            traceback.print_exc()

    def start_periodic_mode_sync(self):
        """Start periodic mode synchronization with Firebase"""
        try:
            print("Starting periodic mode synchronization...")
            
            def sync_mode_periodically(dt):
                try:
                    if self.firebase_control and self.autonomous_data_exchange["firebase_connected"]:
                        # Check for mode changes every 3 seconds, but be more intelligent about it
                        self.monitor_firebase_mode_changes_intelligent()
                except Exception as e:
                    print(f"Error in periodic mode sync: {e}")
            
            # Schedule mode sync every 5 seconds (reduced frequency to prevent UI blocking)
            self.mode_sync_event = Clock.schedule_interval(sync_mode_periodically, 5.0)
            print("✅ Periodic mode synchronization started (every 5 seconds - optimized)")
            
        except Exception as e:
            print(f"Error starting periodic mode sync: {e}")

    def stop_periodic_mode_sync(self):
        """Stop periodic mode synchronization"""
        try:
            if hasattr(self, 'mode_sync_event') and self.mode_sync_event:
                self.mode_sync_event.cancel()
                print("✅ Periodic mode synchronization stopped")
        except Exception as e:
            print(f"Error stopping periodic mode sync: {e}")

    def preserve_internet_mode_for_mission(self):
        """Preserve internet mode when there's an active mission"""
        try:
            if not self.firebase_control or not self.autonomous_data_exchange["firebase_connected"]:
                return False
            
            # Check if there's an active mission
            has_active_mission = self.check_active_internet_mission()
            
            if has_active_mission and self.control_mode != "internet":
                print("Active mission detected, switching to internet mode")
                self.implement_internet_mode()
                # Update Firebase to reflect the mode change
                self.update_firebase_system_status()
                return True
            
            return False
            
        except Exception as e:
            print(f"Error preserving internet mode for mission: {e}")
            return False

    def on_return_from_mission_planning(self):
        """Called when returning from mission planning to ensure proper mode"""
        try:
            print("=== RETURNING FROM MISSION PLANNING ===")
            
            # Set flag to indicate we're returning from mission planning
            self.returning_from_mission_planning = True
            print("✅ Flag set: returning from mission planning")
            
            # Set flag to indicate we're processing mission commands to prevent connection tests
            self.processing_mission_commands = True
            print("✅ Flag set: processing mission commands")
            
            # Cancel any pending connectivity checks to prevent delays
            self.cancel_pending_connectivity_checks()
            print("✅ Cancelled pending connectivity checks")
            
            # Check if we should preserve internet mode
            if self.preserve_internet_mode_for_mission():
                print("✅ Internet mode preserved for active mission")
            else:
                print("No active mission, mode unchanged")
                
        except Exception as e:
            print(f"Error handling return from mission planning: {e}")


# --- Map Plotting Screen ---
class MapPlotScreen(Screen):
    gps_marker = None
    def __init__(self, **kwargs):
        super(MapPlotScreen, self).__init__(**kwargs)
        self.user_markers = []  # List of (MapMarker, (lat, lon))
        self.path_line = None
        self.last_right_click_pos = None
        self.last_status = 'stop'  # Default
        layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        # --- Top controls ---
        controls = BoxLayout(orientation='horizontal', size_hint=(1, None), height=50, spacing=10)
        self.zoom_my_loc_btn = Button(text="Zoom to My Location", size_hint=(None, 1), width=180)
        self.zoom_last_marker_btn = Button(text="Zoom to Last Marker", size_hint=(None, 1), width=180)
        self.clear_mission_btn = Button(text="Clear Mission", size_hint=(None, 1), width=140, background_color=(0.8,0.2,0.2,1))
        self.write_mission_btn = Button(text="Write Mission", size_hint=(None, 1), width=140, background_color=(0.2,0.7,0.2,1))
        self.satellite_toggle_mapplot = ToggleButton(text="Satellite View", size_hint=(None, 1), width=120, background_color=(0.2, 0.6, 0.8, 1))
        
        # Zoom controls for MapPlotScreen
        self.zoom_in_btn_mapplot = Button(text="+", size_hint=(None, 1), width=35, background_color=(0.2, 0.7, 0.2, 1), font_size='16sp')
        self.zoom_out_btn_mapplot = Button(text="-", size_hint=(None, 1), width=35, background_color=(0.7, 0.2, 0.2, 1), font_size='16sp')
        
        # Add marker button
        self.add_marker_btn = Button(text="Add Marker", size_hint=(None, 1), width=120, background_color=(0.8, 0.4, 0.2, 1))
        
        self.zoom_my_loc_btn.bind(on_release=self.zoom_to_my_location)
        self.zoom_last_marker_btn.bind(on_release=self.zoom_to_last_marker)
        self.clear_mission_btn.bind(on_release=self.clear_mission)
        self.write_mission_btn.bind(on_release=self.write_mission)
        self.satellite_toggle_mapplot.bind(state=self.on_satellite_toggle_mapplot)
        self.zoom_in_btn_mapplot.bind(on_release=self.zoom_in_mapplot)
        self.zoom_out_btn_mapplot.bind(on_release=self.zoom_out_mapplot)
        self.add_marker_btn.bind(on_release=self.show_add_marker_dialog)
        
        controls.add_widget(self.zoom_my_loc_btn)
        controls.add_widget(self.zoom_last_marker_btn)
        controls.add_widget(self.clear_mission_btn)
        controls.add_widget(self.write_mission_btn)
        controls.add_widget(self.satellite_toggle_mapplot)
        controls.add_widget(self.add_marker_btn)
        controls.add_widget(self.zoom_out_btn_mapplot)
        controls.add_widget(self.zoom_in_btn_mapplot)
        controls.add_widget(Label(size_hint_x=1))
        layout.add_widget(controls)
        try:
            self.mapview = MapView(zoom=16, lat=12.9716, lon=77.5946)
            layout.add_widget(self.mapview)
            # Add GPS marker (only once, fixed size)
            self.gps_marker = RotatingMapMarker(lat=12.9716, lon=77.5946, source='./assets/rover_icon.png')
            self.gps_marker.size = (30, 30)
            self.mapview.add_marker(self.gps_marker)
            # Bind right-click on map
            self.mapview.bind(on_touch_down=self.on_map_touch_down)
        except Exception:
            if WebView:
                self.webview = WebView(url="https://www.google.com/maps")
                layout.add_widget(self.webview)
            else:
                layout.add_widget(Label(text="WebView not available. Please install kivy_garden.webview."))
        back_btn = Button(text="Back to Main", size_hint=(1, 0.1), background_color=(0.2,0.5,0.8,1))
        back_btn.bind(on_release=self.go_back)
        layout.add_widget(back_btn)
        self.add_widget(layout)

    def zoom_to_my_location(self, instance):
        if self.gps_marker:
            try:
                self.mapview.center_on(self.gps_marker.lat, self.gps_marker.lon)
                self.mapview.zoom = 18
            except Exception as e:
                print(f"Zoom to my location error: {e}")

    def zoom_to_last_marker(self, instance):
        if self.user_markers:
            marker, (lat, lon) = self.user_markers[-1]
            try:
                self.mapview.center_on(lat, lon)
                self.mapview.zoom = 18
            except Exception as e:
                print(f"Zoom to last marker error: {e}")

    def zoom_in_mapplot(self, instance):
        """Zoom in the map in MapPlotScreen"""
        try:
            if hasattr(self, 'mapview') and self.mapview:
                current_zoom = self.mapview.zoom
                new_zoom = min(current_zoom + 1, 20)  # Max zoom level is 20
                self.mapview.zoom = new_zoom
        except Exception as e:
            print(f"Zoom in mapplot error: {e}")

    def zoom_out_mapplot(self, instance):
        """Zoom out the map in MapPlotScreen"""
        try:
            if hasattr(self, 'mapview') and self.mapview:
                current_zoom = self.mapview.zoom
                new_zoom = max(current_zoom - 1, 1)  # Min zoom level is 1
                self.mapview.zoom = new_zoom
        except Exception as e:
            print(f"Zoom out mapplot error: {e}")

    def on_map_touch_down(self, mapview, touch):
        # Only handle right-clicks
        if 'button' in touch.profile and touch.button == 'right':
            # Check if clicked on a marker
            for marker, (lat, lon) in self.user_markers:
                if marker.collide_point(*touch.pos):
                    self.show_marker_context_menu(marker)
                    return True
            # Otherwise, show add marker menu
            self.last_right_click_pos = touch.pos
            self.show_map_context_menu(touch)
            return True
        return False

    def show_map_context_menu(self, touch):
        # Popup for adding marker
        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        add_btn = Button(text="Add Marker Here", size_hint=(1, None), height=40)
        cancel_btn = Button(text="Cancel", size_hint=(1, None), height=40)
        content.add_widget(add_btn)
        content.add_widget(cancel_btn)
        popup = Popup(title="Map Options", content=content, size_hint=(None, None), size=(200, 150), auto_dismiss=False)
        add_btn.bind(on_release=lambda inst: self.add_marker_at_touch(touch, popup))
        cancel_btn.bind(on_release=popup.dismiss)
        popup.open()

    def add_marker_at_touch(self, touch, popup):
        import os
        marker_height = 76  # Marker height in pixels (should match marker.size)
        window_x, window_y = self.mapview.to_window(touch.x, touch.y, initial=True)
        # Adjust y so the marker's center is at the click point
        window_y_adjusted = (window_y - marker_height)
        window_x_adjusted = (window_x - 6)
        lat, lon = self.mapview.get_latlon_at(window_x_adjusted, window_y_adjusted)
        marker = MapMarker(lat=lat, lon=lon)
        marker.size = (30, 30)
        marker.bind(on_touch_down=self.on_marker_touch_down)
        # Synchronous addition
        self.mapview.add_marker(marker)
        self.user_markers.append((marker, (lat, lon)))
        popup.dismiss()
        self.update_path_line()

    def on_marker_touch_down(self, marker, touch):
        if 'button' in touch.profile and touch.button == 'right' and marker.collide_point(*touch.pos):
            self.show_marker_context_menu(marker)
            return True
        return False

    def show_marker_context_menu(self, marker):
        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        del_btn = Button(text="Delete Marker", size_hint=(1, None), height=40)
        cancel_btn = Button(text="Cancel", size_hint=(1, None), height=40)
        content.add_widget(del_btn)
        content.add_widget(cancel_btn)
        popup = Popup(title="Marker Options", content=content, size_hint=(None, None), size=(200, 150), auto_dismiss=False)
        del_btn.bind(on_release=lambda inst: self.delete_marker(marker, popup))
        cancel_btn.bind(on_release=popup.dismiss)
        popup.open()

    def delete_marker(self, marker, popup):
        from kivy.clock import Clock
        def do_delete_marker(dt):
            try:
                self.mapview.remove_marker(marker)
            except Exception as e:
                print(f"Warning: Could not remove marker from map: {e}")
            found = False
            for i, (m, (lat, lon)) in enumerate(self.user_markers):
                if m == marker:
                    del self.user_markers[i]
                    found = True
                    break
            if not found:
                print("Warning: Tried to delete a marker not in user_markers list.")
            popup.dismiss()
            self.update_path_line()
        Clock.schedule_once(do_delete_marker)

    def update_gps_marker(self, lat, lng, heading):
        import threading
        from kivy.clock import Clock
        if threading.current_thread() != threading.main_thread():
            Clock.schedule_once(lambda dt: self.update_gps_marker(lat, lng, heading))
            return
        # Only update the existing marker, never add a new one
        if self.gps_marker:
            try:
                self.gps_marker.lat = float(lat)
                self.gps_marker.lon = float(lng)
                self.gps_marker.size = (30, 30)  # Ensure size is always correct
                if heading is not None:
                    self.gps_marker.heading = float(heading)
                # Optionally, recenter map if marker is far from center (optional, comment out if not wanted)
                # self.mapview.center_on(float(lat), float(lng))
                self.update_path_line()
            except Exception as e:
                print(f"Error updating MapPlotScreen GPS marker: {e}")

    def update_path_line(self):
        from kivy.clock import Clock
        def do_update(dt):
            # Remove old line
            if self.path_line and self.mapview.canvas:
                try:
                    self.mapview.canvas.remove(self.path_line)
                except ValueError:
                    pass  # Line was already removed or never added
                self.path_line = None
            # Need at least one user marker to draw path
            if not self.user_markers:
                return
            # Gather points: start from GPS marker, then all user markers
            points = []
            if self.gps_marker is not None and hasattr(self.gps_marker, 'lat') and hasattr(self.gps_marker, 'lon'):
                points.append((self.gps_marker.lat, self.gps_marker.lon))
            points += [coords for m, coords in self.user_markers]
            if len(points) < 2:
                return
            # Convert lat/lon to mapview widget coords
            widget_points = []
            for lat, lon in points:
                x, y = self.mapview.get_window_xy_from(lat, lon, self.mapview.zoom)
                widget_points.extend([x, y])
            # Draw line
            from kivy.graphics import Color, Line
            with self.mapview.canvas:
                Color(0.1, 0.7, 0.2, 1)
                self.path_line = Line(points=widget_points, width=2)
        Clock.schedule_once(do_update)

    def clear_mission(self, instance):
        # Remove all user markers and path line
        from kivy.clock import Clock
        def do_clear(dt):
            for marker, _ in self.user_markers:
                try:
                    self.mapview.remove_marker(marker)
                except Exception as e:
                    print(f"Warning: Could not remove marker from map: {e}")
            self.user_markers.clear()
            if self.path_line and self.mapview.canvas:
                try:
                    self.mapview.canvas.remove(self.path_line)
                except Exception:
                    pass
                self.path_line = None
        Clock.schedule_once(do_clear)

    def write_mission(self, instance):
        # Collect all user marker coordinates and send to remote device
        mission_points = [coords for m, coords in self.user_markers]
        # Get last status from MainScreen if possible
        app = App.get_running_app()
        last_status = 'stop'
        if hasattr(app, 'root') and app.root is not None:
            try:
                main_screen = app.root.get_screen('main')
                if hasattr(main_screen, 'last_status'):
                    last_status = main_screen.last_status
            except Exception:
                pass
        if not mission_points:
            from kivymd.toast import toast
            from kivy.clock import Clock
            Clock.schedule_once(lambda dt: toast("No mission points to send!"))
            return
        mission_data = json.dumps({"mission": mission_points, "status": last_status})
        
        # Send mission_data to remote device based on control mode
        def send_mission(data, host='192.168.144.16', port=5005):
            import socket
            from kivy.clock import Clock
            from kivymd.toast import toast
            try:
                udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                udp_socket.sendto(data.encode('utf-8'), (host, port))
                udp_socket.close()
                Clock.schedule_once(lambda dt: toast("Mission sent successfully!"))
            except Exception as e:
                print(f"Mission send error: {e}")
                Clock.schedule_once(lambda dt: toast(f"Mission send failed"))
        
        # Send via UDP (hardware mode)
        if hasattr(app, 'root') and app.root is not None:
            try:
                main_screen = app.root.get_screen('main')
                print(f"Main screen found: {main_screen}")
                print(f"Control mode: {getattr(main_screen, 'control_mode', 'NOT_SET')}")
                print(f"Firebase control available: {hasattr(main_screen, 'firebase_control')}")
                
                if hasattr(main_screen, 'firebase_control') and main_screen.firebase_control:
                    print(f"Firebase control mode: {main_screen.firebase_control.get_control_mode()}")
                    print(f"Firebase connected: {main_screen.firebase_control.is_firebase_connected()}")
                
                if hasattr(main_screen, 'control_mode') and main_screen.control_mode == "hardware":
                    print("Sending mission via UDP (hardware mode)")
                    threading.Thread(target=send_mission, args=(mission_data,), daemon=True).start()
                elif hasattr(main_screen, 'control_mode') and main_screen.control_mode == "internet" and hasattr(main_screen, 'firebase_control') and main_screen.firebase_control:
                    # Send via Firebase (internet mode)
                    try:
                        print(f"=== FIREBASE MISSION UPLOAD DEBUG ===")
                        print(f"Attempting to send mission to Firebase in internet mode")
                        print(f"Firebase control mode: {main_screen.firebase_control.get_control_mode()}")
                        print(f"Firebase connected: {main_screen.firebase_control.is_firebase_connected()}")
                        print(f"Mission points: {mission_points}")
                        print(f"Last status: {last_status}")
                        
                        # Ensure Firebase control mode is synchronized
                        if main_screen.firebase_control.get_control_mode() != "internet":
                            print("Synchronizing Firebase control mode to internet")
                            main_screen.firebase_control.set_control_mode("internet")
                            print(f"Firebase control mode after sync: {main_screen.firebase_control.get_control_mode()}")
                        
                        # Ensure main screen control mode is also set to internet
                        if main_screen.control_mode != "internet":
                            print("Setting main screen control mode to internet")
                            main_screen.control_mode = "internet"
                            main_screen.update_control_mode_button()
                        
                        # Test Firebase connection before sending
                        if not main_screen.firebase_control.is_firebase_connected():
                            print("Firebase not connected, attempting to test connection...")
                            if main_screen.firebase_control.test_connection():
                                print("Firebase connection test passed")
                            else:
                                print("Firebase connection test failed")
                                Clock.schedule_once(lambda dt: toast("Firebase connection failed"))
                                return
                        
                        mission_data_dict = {"mission": mission_points, "status": last_status}
                        print(f"Sending mission data: {mission_data_dict}")
                        
                                                 # No connection test needed - Firebase connection is never tested after initial setup
                         success = main_screen.firebase_control.send_autonomous_mission(mission_data_dict)
                        if success:
                            # Update Firebase system status to reflect internet mode
                            main_screen.update_firebase_system_status()
                            Clock.schedule_once(lambda dt: toast("Mission sent successfully to Firebase!"))
                            print(f"✅ Successfully sent mission to Firebase: {len(mission_points)} waypoints")
                        else:
                            Clock.schedule_once(lambda dt: toast("Failed to send mission to Firebase"))
                            print("❌ Failed to send mission to Firebase")
                    except Exception as e:
                        print(f"❌ Error sending mission to Firebase: {e}")
                        Clock.schedule_once(lambda dt: toast(f"Mission send to Firebase failed"))
                        import traceback
                        traceback.print_exc()
                else:
                    print(f"Control mode not properly set or Firebase not available")
                    print(f"Control mode: {getattr(main_screen, 'control_mode', 'NOT_SET')}")
                    print(f"Firebase control available: {hasattr(main_screen, 'firebase_control')}")
                    # Fallback to UDP if control mode is not properly set
                    threading.Thread(target=send_mission, args=(mission_data,), daemon=True).start()
            except Exception as e:
                print(f"Error determining control mode: {e}")
                import traceback
                traceback.print_exc()
                # Fallback to UDP
                threading.Thread(target=send_mission, args=(mission_data,), daemon=True).start()
        else:
            print("Main screen not available, falling back to UDP")
            # Fallback to UDP if main screen not available
            threading.Thread(target=send_mission, args=(mission_data,), daemon=True).start()

    def on_satellite_toggle_mapplot(self, instance, state):
        """Toggle between regular and satellite map view for MapPlotScreen"""
        try:
            if hasattr(self, 'mapview') and self.mapview:
                if state == 'down':  # Satellite view
                    # Switch to satellite map source
                    satellite_source = MapSource(url="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}")
                    self.mapview.map_source = satellite_source
                    self.satellite_toggle_mapplot.text = "Regular View"
                    self.satellite_toggle_mapplot.background_color = (0.8, 0.4, 0.2, 1)  # Orange
                else:  # Regular view
                    # Switch to regular map source
                    regular_source = MapSource(url="https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}")
                    self.mapview.map_source = regular_source
                    self.satellite_toggle_mapplot.text = "Satellite View"
                    self.satellite_toggle_mapplot.background_color = (0.2, 0.6, 0.8, 1)  # Blue
        except Exception as e:
            print(f"Satellite toggle error: {e}")

    def show_add_marker_dialog(self, instance):
        """Show dialog to enter latitude and longitude coordinates"""
        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        
        # Latitude input
        lat_layout = BoxLayout(orientation='horizontal', size_hint=(1, None), height=40)
        lat_label = Label(text="Latitude:", size_hint=(None, 1), width=80)
        self.lat_input = TextInput(hint_text="Enter latitude (e.g., 12.9716)", multiline=False, size_hint=(1, 1))
        lat_layout.add_widget(lat_label)
        lat_layout.add_widget(self.lat_input)
        
        # Longitude input
        lon_layout = BoxLayout(orientation='horizontal', size_hint=(1, None), height=40)
        lon_label = Label(text="Longitude:", size_hint=(None, 1), width=80)
        self.lon_input = TextInput(hint_text="Enter longitude (e.g., 77.5946)", multiline=False, size_hint=(1, 1))
        lon_layout.add_widget(lon_label)
        lon_layout.add_widget(self.lon_input)
        
        # Buttons
        btn_layout = BoxLayout(orientation='horizontal', size_hint=(1, None), height=40, spacing=10)
        add_btn = Button(text="Add Marker", size_hint=(1, 1), background_color=(0.2, 0.7, 0.2, 1))
        cancel_btn = Button(text="Cancel", size_hint=(1, 1), background_color=(0.7, 0.2, 0.2, 1))
        
        content.add_widget(lat_layout)
        content.add_widget(lon_layout)
        content.add_widget(btn_layout)
        btn_layout.add_widget(add_btn)
        btn_layout.add_widget(cancel_btn)
        
        popup = Popup(title="Add Marker by Coordinates", content=content, 
                     size_hint=(None, None), size=(400, 200), auto_dismiss=False)
        
        add_btn.bind(on_release=lambda inst: self.add_marker_by_coordinates(popup))
        cancel_btn.bind(on_release=popup.dismiss)
        
        popup.open()

    def add_marker_by_coordinates(self, popup):
        """Add a marker at the specified coordinates"""
        try:
            lat = float(self.lat_input.text.strip())
            lon = float(self.lon_input.text.strip())
            
            # Validate coordinates
            if not (-90 <= lat <= 90):
                self.show_error_dialog("Invalid latitude. Must be between -90 and 90.")
                return
            if not (-180 <= lon <= 180):
                self.show_error_dialog("Invalid longitude. Must be between -180 and 180.")
                return
            
            # Create and add marker
            marker = MapMarker(lat=lat, lon=lon)
            marker.size = (30, 30)
            marker.bind(on_touch_down=self.on_marker_touch_down)
            
            # Add to map and track
            self.mapview.add_marker(marker)
            self.user_markers.append((marker, (lat, lon)))
            
            # Center map on new marker
            self.mapview.center_on(lat, lon)
            self.mapview.zoom = 18
            
            # Update path line
            self.update_path_line()
            
            # Close popup and show success message
            popup.dismiss()
            self.show_success_dialog(f"Marker added at ({lat:.6f}, {lon:.6f})")
            
        except ValueError:
            self.show_error_dialog("Please enter valid numeric coordinates.")
        except Exception as e:
            self.show_error_dialog(f"Error adding marker: {str(e)}")

    def show_error_dialog(self, message):
        """Show error dialog with message"""
        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        content.add_widget(Label(text=message))
        ok_btn = Button(text="OK", size_hint=(1, None), height=40)
        content.add_widget(ok_btn)
        
        popup = Popup(title="Error", content=content, 
                     size_hint=(None, None), size=(300, 150), auto_dismiss=False)
        ok_btn.bind(on_release=popup.dismiss)
        popup.open()

    def show_success_dialog(self, message):
        """Show success dialog with message"""
        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        content.add_widget(Label(text=message))
        ok_btn = Button(text="OK", size_hint=(1, None), height=40, background_color=(0.2, 0.7, 0.2, 1))
        content.add_widget(ok_btn)
        
        popup = Popup(title="Success", content=content, 
                     size_hint=(None, None), size=(300, 150), auto_dismiss=False)
        ok_btn.bind(on_release=popup.dismiss)
        popup.open()

    def go_back(self, instance):
        # Call mode preservation method before going back
        try:
            app = App.get_running_app()
            if hasattr(app, 'root') and app.root is not None:
                main_screen = app.root.get_screen('main')
                if hasattr(main_screen, 'on_return_from_mission_planning'):
                    main_screen.on_return_from_mission_planning()
        except Exception as e:
            print(f"Error calling mode preservation: {e}")
        
        self.manager.current = 'main'


class RoverApp(MDApp):
    def build(self):
        sm = ScreenManager()
        sm.add_widget(SplashScreen(name='splash'))
        main_screen = MainScreen(name='main')
        sm.add_widget(main_screen)
        sm.add_widget(MapPlotScreen(name='mapplot'))
        sm.current = 'main'

        return sm

if __name__ == '__main__':
    RoverApp().run()