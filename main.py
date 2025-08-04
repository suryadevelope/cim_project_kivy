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
        
        time.sleep(2)
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
        with self.canvas.before:
            Color(0.95, 0.95, 0.97, 1)
            self.rect = Rectangle(size=self.size, pos=self.pos)
        self.bind(size=self._update_rect, pos=self._update_rect)

        self.autoshowfullscreen = False
        self.updatefullscreenval = False
        self.allvideopopups = []
        self.image_widgets = []
        self.autonomous_event = None

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
        self.battimg = Image(source=self.img_src, size_hint_x=None, width=40, allow_stretch=True, keep_ratio=True)
        top_nav.add_widget(self.battimg)
        self.jetsonbattimg = Image(source=self.jetsonimg_src, size_hint_x=None, width=40, allow_stretch=True, keep_ratio=True)
        top_nav.add_widget(self.jetsonbattimg)
        self.armstateimg = Image(source=self.img_src_armstate, size_hint_x=None, width=40, allow_stretch=True, keep_ratio=True)
        top_nav.add_widget(self.armstateimg)
        self.top_switch = Switch(active=False, size_hint_x=None, width=60)
        self.top_switch.bind(active=self.on_switch_active)
        top_nav.add_widget(self.top_switch)
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
        
        # Start/Stop Buttons
        button_box = BoxLayout(orientation='vertical', size_hint=(1, None), height=90, spacing=8)
        start_btn = Button(text='Start', size_hint=(1, None), height=40, font_size='16sp', background_color=(0.1, 0.5, 0.2, 1))
        stop_btn = Button(text='Stop', size_hint=(1, None), height=40, font_size='16sp', background_color=(0.6, 0.1, 0.1, 1))
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

    def on_switch_active(self, instance, value):
        if value:
            self.autoshowfullscreen = True
            toast("Auto cam zoom mode ON")
        else:
            self.autoshowfullscreen = False
            toast("Auto cam zoom mode OFF")
            if self.updatefullscreenval:
                self.dismiss_full_screen(self.popup)

    def update_utilsdata_ui(self, instance, value):
        print(f"[DEBUG] update_utilsdata_ui called with value: {value}")
        print(f"[DEBUG] Value type: {type(value)}")
        
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
        
        # Battery and arm state logic
        batvoltage = value.get("batvoltage", 0)
        jetsonvoltage = value.get("jetsonvoltage", 0)
        armstate = value.get("armstate", 0)
        
        print(f"[DEBUG] batvoltage: {batvoltage} (type: {type(batvoltage)})")
        print(f"[DEBUG] jetsonvoltage: {jetsonvoltage} (type: {type(jetsonvoltage)})")
        print(f"[DEBUG] armstate: {armstate} (type: {type(armstate)})")
        print(f"[DEBUG] All keys in value: {list(value.keys())}")
        
        try:
            if float(batvoltage) <= 25:
                self.img_src = './assets/bad_batt.png'
            else:
                self.img_src = './assets/good_batt.png'
        except (ValueError, TypeError) as e:
            print(f"[DEBUG] Error processing batvoltage: {e}")
            self.img_src = './assets/bad_batt.png'
            
        try:
            if float(jetsonvoltage) <= 11.5:
                self.jetsonimg_src = './assets/bad_batt.png'
            else:
                self.jetsonimg_src = './assets/good_batt.png'
        except (ValueError, TypeError) as e:
            print(f"[DEBUG] Error processing jetsonvoltage: {e}")
            self.jetsonimg_src = './assets/bad_batt.png'
            
        try:
            if int(armstate) == 1:
                self.img_src_armstate = "./assets/no_home.png"
            else:
                self.img_src_armstate = "./assets/at_home.png"
        except (ValueError, TypeError) as e:
            print(f"[DEBUG] Error processing armstate: {e}")
            self.img_src_armstate = "./assets/at_home.png"

        # Handle GPS data
        gpsvalue = value.get("gps")
        if isinstance(gpsvalue, str):
            try:
                gpsvalue = ast.literal_eval(gpsvalue)
            except:
                gpsvalue = {}
        elif not isinstance(gpsvalue, dict):
            gpsvalue = {}

        # GPS info
        self.satcount = str(gpsvalue.get("num_sats", "0"))
        self.irnss_accuracy = str(gpsvalue.get("irnss_stats", "N/A"))
        self.fix_type = str(gpsvalue.get("fix_type", "N/A"))
        self.gps_fix = bool(gpsvalue.get("fix", False))
        
        print(f"[DEBUG] Set satcount to: {self.satcount}")
        print(f"[DEBUG] Set irnss_accuracy to: {self.irnss_accuracy}")
        print(f"[DEBUG] Set fix_type to: {self.fix_type}")
        print(f"[DEBUG] Set gps_fix to: {self.gps_fix}")
        
        # GPS marker update
        lat = gpsvalue.get("lat")
        lng = gpsvalue.get("lng")
        heading = value.get("compass")
        
        # Handle Autonomous Navigation data
        autonomous_data = value.get("autonomous", {})
        if isinstance(autonomous_data, str):
            try:
                autonomous_data = ast.literal_eval(autonomous_data)
            except:
                autonomous_data = {}
        elif not isinstance(autonomous_data, dict):
            autonomous_data = {}
            
        print(f"[DEBUG] Autonomous data received: {autonomous_data}")
            
        # Update autonomous navigation display
        self.update_autonomous_display(autonomous_data)
        
        # print(f"[DEBUG] mapview type: {type(self.mapview)}")
        # print(f"[DEBUG] lat: {lat}, lng: {lng}")
        from kivy.clock import Clock
        def _update_marker_on_main_thread(dt):
            from kivy_garden.mapview import MapView
            if lat is not None and lng is not None and isinstance(self.mapview, MapView):
                try:
                    if self.gps_marker is None:
                        # print("[DEBUG] Creating new GPS marker...")
                        self.gps_marker = RotatingMapMarker(lat=float(lat), lon=float(lng), source='./assets/rover_icon.png')
                        self.gps_marker.size = (30, 30)
                        if heading is not None:
                            self.gps_marker.heading = float(heading)
                        self.mapview.add_marker(self.gps_marker)
                        # print(f"[DEBUG] Marker created at lat: {self.gps_marker.lat}, lon: {self.gps_marker.lon}")
                        self.mapview.center_on(float(lat), float(lng))
                    else:
                        # print("[DEBUG] Updating existing GPS marker...")
                        self.gps_marker.lat = float(lat)
                        self.gps_marker.lon = float(lng)
                        self.gps_marker.size = (30, 30)
                        if heading is not None:
                            self.gps_marker.heading = float(heading)
                        # print(f"[DEBUG] Marker updated to lat: {self.gps_marker.lat}, lon: {self.gps_marker.lon}")
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
        """Update autonomous navigation display with new data"""
        try:
            print(f"[DEBUG] Updating autonomous display with data: {autonomous_data}")
            
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
            
            # Determine navigation status based on run_status
            if run_status:
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
            
            print(f"[DEBUG] Mission State: {self.mission_state}")
            print(f"[DEBUG] Current Waypoint: {wp_number}")
            print(f"[DEBUG] Total Waypoints: {wp_loaded_count}")
            print(f"[DEBUG] Completed Waypoints: {self.completed_waypoints}")
            print(f"[DEBUG] Mission Progress: {self.mission_progress}%")
            print(f"[DEBUG] Distance to Waypoint: {wp_distance}")
            print(f"[DEBUG] Navigation State: {self.navigation_state}")
            print(f"[DEBUG] Autonomous Mode: {self.autonomous_mode}")
            print(f"[DEBUG] Run Status: {run_status}")
            
            # Update detailed labels
            self.update_autonomous_labels()
            
        except Exception as e:
            print(f"Error updating autonomous display: {e}")

    def update_autonomous_labels(self):
        """Update the detailed autonomous navigation labels"""
        try:
            # Mission status with more detailed information
            if hasattr(self, 'mission_complete') and self.mission_complete:
                mission_text = "Mission: Complete"
                mission_color = (0.2, 0.8, 0.2, 1)  # Green
            elif hasattr(self, 'has_pending_waypoints') and self.has_pending_waypoints:
                mission_text = "Mission: Active"
                mission_color = (0.2, 0.6, 0.8, 1)  # Blue
            elif hasattr(self, 'mission_state') and self.mission_state == "not_started":
                mission_text = "Mission: Not Started"
                mission_color = (0.6, 0.6, 0.6, 1)  # Gray
            else:
                mission_text = "Mission: No Mission"
                mission_color = (0.6, 0.6, 0.6, 1)  # Gray
            
            if hasattr(self, 'mission_status_label'):
                self.mission_status_label.text = mission_text
                self.mission_status_label.color = mission_color
            
            # Waypoint progress with current waypoint number
            if hasattr(self, 'total_waypoints') and hasattr(self, 'completed_waypoints'):
                current_wp = getattr(self, 'current_waypoint', None)
                if current_wp is not None:
                    wp_text = f"Waypoints: {self.completed_waypoints}/{self.total_waypoints} (Current: {current_wp})"
                else:
                    wp_text = f"Waypoints: {self.completed_waypoints}/{self.total_waypoints}"
                
                if hasattr(self, 'waypoint_detail_label'):
                    self.waypoint_detail_label.text = wp_text
            
            # Distance to waypoint with more details
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
                            
                except (ValueError, TypeError):
                    distance_text = "Distance: N/A"
            else:
                distance_text = "Distance: N/A"
            
            if hasattr(self, 'distance_label'):
                self.distance_label.text = distance_text
            
            # Navigation state with more details
            if hasattr(self, 'navigation_state'):
                nav_text = f"State: {self.navigation_state}"
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
        if self.autoshowfullscreen:
            value = int(value)
            if value >= 0:
                self.close_all_popups()
                img = self.image_widgets[value]
                class SimulatedTouch:
                    def __init__(self, pos):
                        self.pos = pos
                simulated_touch = SimulatedTouch(img.center)
                Clock.schedule_once(lambda dt: img.dispatch('on_touch_down', simulated_touch), 0)
            if value < 0:
                if self.updatefullscreenval:
                    self.close_all_popups()

    def update_image(self, dt):
        keys = list(self.videoreceiver.video_frames.keys())
        for i, identifier in enumerate(keys):
            if identifier in self.videoreceiver.video_frames:
                frame = self.videoreceiver.video_frames[identifier]
                if frame is not None:
                    if frame.dtype != np.uint8:
                        frame = frame.astype(np.uint8)
                    cv2.putText(frame, f"cam{i}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)
                    frame = cv2.flip(frame, 0)
                    buffer = frame.tobytes()
                    texture = Texture.create(size=(frame.shape[1], frame.shape[0]), colorfmt='bgr')
                    texture.blit_buffer(buffer, colorfmt='bgr', bufferfmt='ubyte')
                    self.image_widgets[i].texture = texture

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
            Clock.schedule_interval(lambda dt: self.updatefullscreen(image_widget, popup_image), 1.0 / 30.0)

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
        for image_widget in self.image_widgets:
            image_widget.bind(on_touch_down=self.on_image_touch)
        Clock.schedule_interval(self.update_image, 1.0 / 30.0)

    def on_image_touch(self, image_widget, touch):
        if image_widget.collide_point(*touch.pos):
            self.on_image_click(image_widget)

    def on_leave(self):
        for image_widget in self.image_widgets:
            image_widget.unbind(on_touch_down=self.on_image_touch)

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

    def send_start_status(self, instance):
        self.last_status = 'start'
        self.send_status_udp('start')
        self.start_autonomous_mission_sender()

    def send_stop_status(self, instance):
        self.last_status = 'stop'
        self.send_status_udp('stop')
        self.stop_autonomous_mission_sender()

    def start_autonomous_mission_sender(self):
        if self.autonomous_event is None:
            from kivy.clock import Clock
            self.autonomous_event = Clock.schedule_interval(self.send_autonomous_mission, 1.0)

    def stop_autonomous_mission_sender(self):
        if self.autonomous_event is not None:
            from kivy.clock import Clock
            Clock.unschedule(self.autonomous_event)
            self.autonomous_event = None

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
        data = json.dumps({"mission": mission_points, "status": status})
        import socket
        from kivy.clock import Clock
        from kivymd.toast import toast
        host = '192.168.1.10'
        port = 5005
        def send(data, host, port):
            try:
                udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                udp_socket.sendto(data.encode('utf-8'), (host, port))
                udp_socket.close()
            except Exception as e:
                print(f"Autonomous mission send error: {e}")
        threading.Thread(target=send, args=(data, host, port), daemon=True).start()

    def send_status_udp(self, status):
        import socket
        from kivy.clock import Clock
        from kivymd.toast import toast
        # Send status in the same JSON format as mission: {"mission": [], "status": status}
        data = json.dumps({"mission": [], "status": status})
        host = '192.168.1.10'
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
        # Send mission_data to remote device (simple socket client)
        def send_mission(data, host='192.168.1.10', port=5005):
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
