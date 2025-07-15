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
from kivy.properties import StringProperty
from kivymd.toast import toast
from kivymd.uix.card import MDCard
from gtts import gTTS

import pygame


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
    size: 200, 200  # Default size, will be updated by parent layout
    canvas.before:
        Rectangle:
            pos: self.pos
            size: self.size
            source: './assets/compass_bg.png'

    Image:
        id: needle
        source: './assets/needle.png'
        # size_hint: None, None
        size: root.width * 0.3, root.height * 0.3
        pos:  self.width / 2, self.height / 2
        keep_ratio: True
        allow_stretch: True
        canvas.before:
            PushMatrix
            Rotate:
                angle: root.needle_angle if hasattr(root, 'needle_angle') else 0
                origin: self.center
        canvas.after:
            PopMatrix
''')


from kivy.properties import NumericProperty

class CompassWidget(BoxLayout):
    needle_angle = NumericProperty(0)

    def update_compass(self, heading):
        # heading: 0-360, rotate needle accordingly
        self.needle_angle = -heading

    def update_angle(self, dt):
        # Example: Rotate the needle randomly between 0 and 360 degrees.
        angle = random.uniform(0, 360)
        self.update_compass(angle)



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
        
      

    def on_enter(self):
        
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

# --- Navigation Screen for Autonomous Navigation ---



class NavigationScreen(Screen):

    def __init__(self, **kwargs):
        super(NavigationScreen, self).__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        self.path_points = []  # List of (lat, lon) tuples
        self.sim_index = 0
        self.sim_gps_data = [  # Simulated GPS path
            (12.9716, 77.5946),
            (12.9720, 77.5950),
            (12.9725, 77.5955),
            (12.9730, 77.5960),
            (12.9735, 77.5965),
            (12.9740, 77.5970),
            (12.9745, 77.5975),
            (12.9750, 77.5980)
        ]
        try:
            self.mapview = MapView(zoom=16, lat=12.9716, lon=77.5946)
            self.marker = MapMarker(lat=12.9716, lon=77.5946)
            self.mapview.add_marker(self.marker)
            layout.add_widget(self.mapview)
            # For path visualization, use MapMarker for each point (polyline not natively supported)
            self.path_markers = []
            Clock.schedule_interval(self.update_rover_position, 2)  # Update every 2 seconds
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

    def update_rover_position(self, dt):
        # Simulate receiving a new GPS point
        if self.sim_index < len(self.sim_gps_data):
            lat, lon = self.sim_gps_data[self.sim_index]
            self.sim_index += 1
        else:
            lat, lon = self.sim_gps_data[-1]
        # Update marker position
        self.marker.lat = lat
        self.marker.lon = lon
        # Add to path and show path markers
        self.path_points.append((lat, lon))
        # Remove old path markers
        for m in self.path_markers:
            self.mapview.remove_marker(m)
        self.path_markers = []
        # Add new path markers (as small dots)
        for pt in self.path_points:
            m = MapMarker(lat=pt[0], lon=pt[1])
            m.size = (16, 16)
            self.mapview.add_marker(m)
            self.path_markers.append(m)
        # Do not re-add the main marker; just update its position

    def go_back(self, instance):
        self.manager.current = 'main'

class MainScreen(Screen):
    def _update_rect(self, instance, value):
        self.rect.size = instance.size
        self.rect.pos = instance.pos
    img_src = StringProperty("./assets/bad_batt.png")
    jetsonimg_src = StringProperty("./assets/bad_batt.png")
    img_src_armstate = StringProperty("./assets/no_home.png")
    battimg = None

    def goto_navigation(self, instance):
        self.manager.current = 'navigation'

    def goto_mapplot(self, instance):
        self.manager.current = 'mapplot'


    def __init__(self, **kwargs):
        super(MainScreen, self).__init__(**kwargs)
        with self.canvas.before:
            Color(0.75, 0.75, 0.75, 1)
            self.rect = Rectangle(size=self.size, pos=self.pos)
        self.bind(size=self._update_rect, pos=self._update_rect)

        self.autoshowfullscreen = False
        self.updatefullscreenval = False
        self.allvideopopups = []
        self.image_widgets = []

        # --- Top Navigation Bar ---
        top_nav = BoxLayout(orientation='horizontal', size_hint_y=None, height=80, padding=[10, 5, 10, 5], spacing=16)
        # Add background color to top bar
        with top_nav.canvas.before:
            Color(0.2, 0.3, 0.5, 1)  # Example: blue-ish color, adjust as needed
            self.topbar_rect = Rectangle(size=top_nav.size, pos=top_nav.pos)
        def update_topbar_rect(instance, value):
            self.topbar_rect.size = top_nav.size
            self.topbar_rect.pos = top_nav.pos
        top_nav.bind(size=update_topbar_rect, pos=update_topbar_rect)
        # App logo/icon (moderate size)
        top_nav.add_widget(Image(source='./assets/logo.png', size_hint_x=0.13, size_hint_y=1, allow_stretch=True, keep_ratio=True))
        # Main Battery icon (moderate size)
        self.battimg = Image(source=self.img_src, size_hint_x=0.10, size_hint_y=1, allow_stretch=True, keep_ratio=True)
        top_nav.add_widget(self.battimg)
        # Jetson Battery icon (moderate size)
        self.jetsonbattimg = Image(source=self.jetsonimg_src, size_hint_x=0.10, size_hint_y=1, allow_stretch=True, keep_ratio=True)
        top_nav.add_widget(self.jetsonbattimg)
        # Arm Position icon (moderate size)
        self.armstateimg = Image(source=self.img_src_armstate, size_hint_x=0.10, size_hint_y=1, allow_stretch=True, keep_ratio=True)
        top_nav.add_widget(self.armstateimg)
        # Switch and label
        self.top_switch = Switch(active=False, size_hint_x=0.07, size_hint_y=1)
        self.top_switch.bind(active=self.on_switch_active)
        top_nav.add_widget(self.top_switch)
        self.top_switch_label = Label(text='Auto Cam Zoom', font_size='16sp', color=(0.2, 0.5, 0.8, 1), size_hint_x=0.12, size_hint_y=1, halign='left', valign='middle')
        # top_nav.add_widget(self.top_switch_label)
        # Switch state label
        self.top_switch_state = Label(text='Switch is OFF', font_size='16sp', color=(0.2, 0.5, 0.8, 1), size_hint_x=0.12, size_hint_y=1, halign='left', valign='middle')
        # top_nav.add_widget(self.top_switch_state)
        # Add Map Plotting button to the top bar
        mapplot_btn_top = Button(text="Map Plotting", size_hint_x=0.16, size_hint_y=1, background_color=(0.1, 0.7, 0.3, 1), font_size='16sp')
        mapplot_btn_top.bind(on_release=self.goto_mapplot)
        top_nav.add_widget(mapplot_btn_top)
        # Trailing spacer (expands to fill remaining space)
        top_nav.add_widget(Label(size_hint_x=1, size_hint_y=1))

        # --- Root layout: vertical, add top_nav, spacer, then main_layout ---
        root_layout = BoxLayout(orientation='vertical', size_hint=(1, 1))
        # Top bar: fixed height (moderate)
        top_nav.size_hint_y = None
        top_nav.height = 80
        root_layout.add_widget(top_nav)
        # Add vertical spacer below top bar
        root_layout.add_widget(Label(size_hint_y=None, height=20))

        # Main horizontal layout: left = map (square) + compass, right = camera & controls
        main_layout = BoxLayout(orientation='horizontal', padding=10, spacing=10, size_hint_y=1)

        # --- Left: MapView (top) and CompassWidget (bottom) with improved alignment ---
        left_panel = BoxLayout(orientation='vertical', spacing=8, size_hint=(0.42, 1))
        # MapView container (60% height)
        mapview_container = BoxLayout(size_hint=(1, 0.6), padding=0)
        try:
            self.mapview = MapView(zoom=16, lat=12.9716, lon=77.5946)
            self.mapview.size_hint = (1, 1)
        except Exception:
            if WebView:
                self.mapview = WebView(url="https://www.google.com/maps")
                self.mapview.size_hint = (1, 1)
            else:
                self.mapview = Label(text="MapView/WebView not available.", size_hint=(1, 1))
        mapview_container.add_widget(self.mapview)
        left_panel.add_widget(mapview_container)

        # --- Below MapView: Two equal squares (left: compass, right: start/stop buttons) ---
        squares_row = BoxLayout(orientation='horizontal', size_hint=(1, 0.4), spacing=8)
        # Left square: CompassWidget centered
        compass_square = BoxLayout(size_hint=(0.5, 1), padding=0)
        self.compass = CompassWidget()
        compass_square.add_widget(Widget(size_hint_x=0.1))
        compass_square.add_widget(self.compass)
        compass_square.add_widget(Widget(size_hint_x=0.1))
        def update_compass_size(*args):
            h = compass_square.height
            self.compass.size = (h * 0.95, h * 0.95)
        compass_square.bind(height=update_compass_size)
        squares_row.add_widget(compass_square)
        # Right square: Start/Stop buttons vertically centered
        button_square = BoxLayout(size_hint=(0.5, 1), orientation='vertical')
        button_container = BoxLayout(orientation='vertical', size_hint=(1, 0.6), spacing=16)
        button_container.add_widget(Widget(size_hint_y=0.2))
        start_btn = Button(text='Start', size_hint=(1, 0.3), font_size='20sp', background_color=(0.1, 0.7, 0.3, 1))
        stop_btn = Button(text='Stop', size_hint=(1, 0.3), font_size='20sp', background_color=(0.8, 0.2, 0.2, 1))
        button_container.add_widget(start_btn)
        button_container.add_widget(stop_btn)
        button_container.add_widget(Widget(size_hint_y=0.2))
        button_square.add_widget(Widget(size_hint_y=0.2))
        button_square.add_widget(button_container)
        button_square.add_widget(Widget(size_hint_y=0.2))
        squares_row.add_widget(button_square)
        left_panel.add_widget(squares_row)

        main_layout.add_widget(left_panel)

        # --- Right: Camera images, battery, controls, etc. ---
        right_layout = BoxLayout(orientation='vertical', spacing=0, size_hint=(0.58, 1), padding=[0, 0, 0, 0])
        # Camera layout: two cameras side by side on top, one below, all square and same size, visually balanced and always centered
        camera_layout = GridLayout(cols=2, rows=2, spacing=5, size_hint=(1, 0.8), padding=[24, 8, 24, 24])
        card_size_hint = (1, 1)
        for i in range(3):
            img = Image(source='./assets/no_cam.png', allow_stretch=True, keep_ratio=True)
            self.image_widgets.append(img)
            card = MDCard(
                orientation='vertical',
                size_hint=card_size_hint,
                padding=0,
                elevation=2,
                radius=[16, 16, 16, 16],
                shadow_softness=2
            )
            card.add_widget(img)
            camera_layout.add_widget(card)
        camera_layout.add_widget(Widget(size_hint=card_size_hint))
        right_layout.add_widget(camera_layout)
        # Info and controls
        info_controls_layout = BoxLayout(orientation='horizontal', spacing=10, size_hint=(1, 0.3))
        info_panel = GridLayout(cols=2, rows=5, spacing=8, size_hint=(0.55, 1))
        for _ in range(10):
            info_panel.add_widget(Label())
        right_panel = BoxLayout(orientation='vertical', spacing=10, size_hint=(0.45, 1))
        right_panel.add_widget(Label(size_hint=(1, 1)))
        info_controls_layout.add_widget(info_panel)
        info_controls_layout.add_widget(right_panel)
        right_layout.add_widget(info_controls_layout)
        main_layout.add_widget(right_layout)
        root_layout.add_widget(main_layout)
        # Ensure MainScreen uses all available space
        self.size_hint = (1, 1)
        self.add_widget(root_layout)


    def on_switch_active(self, instance, value):
        pass




# --- Map Plotting Screen ---
class MapPlotScreen(Screen):
    def __init__(self, **kwargs):
        super(MapPlotScreen, self).__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        try:
            self.mapview = MapView(zoom=16, lat=12.9716, lon=77.5946)
            layout.add_widget(self.mapview)
            # Add controls for plotting (future: add waypoints, clear, etc.)
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

    def go_back(self, instance):
        self.manager.current = 'main'


class RoverApp(MDApp):
    def build(self):
        sm = ScreenManager()
        sm.add_widget(SplashScreen(name='splash'))
        main_screen = MainScreen(name='main')
        sm.add_widget(main_screen)
        sm.add_widget(NavigationScreen(name='navigation'))
        sm.add_widget(MapPlotScreen(name='mapplot'))
        sm.current = 'main'

        return sm

if __name__ == '__main__':
    RoverApp().run()
