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
        needle = self.ids.needle
        needle.size_hint = (width, height)
    def update_compass(self, angle):
        self.needle.angle = -angle
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
from kivy.properties import NumericProperty
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
        mapview_container = BoxLayout(size_hint=(1, 0.62), padding=0)
        try:
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
        button_box = BoxLayout(orientation='vertical', size_hint=(0.45, 1), spacing=18, padding=[0, 30, 0, 30])
        start_btn = Button(text='Start', size_hint=(1, None), height=45, font_size='18sp', background_color=(0.1, 0.5, 0.2, 1))
        stop_btn = Button(text='Stop', size_hint=(1, None), height=45, font_size='18sp', background_color=(0.6, 0.1, 0.1, 1))
        button_box.add_widget(start_btn)
        button_box.add_widget(stop_btn)
        bottom_row.add_widget(button_box)
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
        # Battery and arm state logic
        if int(float(value.get("batvoltage", 0))) <= 25:
            self.img_src = './assets/bad_batt.png'
        else:
            self.img_src = './assets/good_batt.png'
        if int(float(value.get("jetsonvoltage", 0))) <= 11.5:
            self.jetsonimg_src = './assets/bad_batt.png'
        else:
            self.jetsonimg_src = './assets/good_batt.png'
        if int(value.get("armstate", 0)) == 1:
            self.img_src_armstate = "./assets/no_home.png"
        else:
            self.img_src_armstate = "./assets/at_home.png"

        # print("Utils data:", value.get("gps"))
        # print("Utils data:", value)

        gpsvalue = ast.literal_eval(value.get("gps"))

        # GPS info
        self.satcount = str(gpsvalue.get("num_sats", "0"))
        self.irnss_accuracy = str(gpsvalue.get("irnss_stats", "N/A"))
        self.fix_type = str(gpsvalue.get("fix_type", "N/A"))
        self.gps_fix = bool(gpsvalue.get("fix", False))
        # GPS marker update
        lat = gpsvalue.get("lat")
        lng = gpsvalue.get("lng")
        heading = value.get("compass")
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

    def update_ui_on_main_thread(self):
        self.battimg.source = self.img_src
        self.armstateimg.source = self.img_src_armstate
        self.jetsonbattimg.source = self.jetsonimg_src
        # Update GPS info labels
        self.satcount_label.text = f"Satcount: {self.satcount}"
        self.irnss_accuracy_label.text = f"IRNSS Acc: {self.irnss_accuracy}"
        self.fix_type_label.text = f"Fix: {self.fix_type}"
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


# --- Map Plotting Screen ---
class MapPlotScreen(Screen):
    gps_marker = None
    def __init__(self, **kwargs):
        super(MapPlotScreen, self).__init__(**kwargs)
        self.user_markers = []  # List of (MapMarker, (lat, lon))
        self.path_line = None
        self.last_right_click_pos = None
        layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        # --- Top controls ---
        controls = BoxLayout(orientation='horizontal', size_hint=(1, None), height=50, spacing=10)
        self.zoom_my_loc_btn = Button(text="Zoom to My Location", size_hint=(None, 1), width=180)
        self.zoom_last_marker_btn = Button(text="Zoom to Last Marker", size_hint=(None, 1), width=180)
        self.clear_mission_btn = Button(text="Clear Mission", size_hint=(None, 1), width=140, background_color=(0.8,0.2,0.2,1))
        self.write_mission_btn = Button(text="Write Mission", size_hint=(None, 1), width=140, background_color=(0.2,0.7,0.2,1))
        self.zoom_my_loc_btn.bind(on_release=self.zoom_to_my_location)
        self.zoom_last_marker_btn.bind(on_release=self.zoom_to_last_marker)
        self.clear_mission_btn.bind(on_release=self.clear_mission)
        self.write_mission_btn.bind(on_release=self.write_mission)
        controls.add_widget(self.zoom_my_loc_btn)
        controls.add_widget(self.zoom_last_marker_btn)
        controls.add_widget(self.clear_mission_btn)
        controls.add_widget(self.write_mission_btn)
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
        from kivy.clock import Clock
        def do_add_marker(dt):
            self.mapview.add_marker(marker)
            self.user_markers.append((marker, (lat, lon)))
            popup.dismiss()
            self.update_path_line()
        Clock.schedule_once(do_add_marker)

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
        if not mission_points:
            from kivymd.toast import toast
            from kivy.clock import Clock
            Clock.schedule_once(lambda dt: toast("No mission points to send!"))
            return
        mission_data = json.dumps({"mission": mission_points})
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

    def go_back(self, instance):
        self.manager.current = 'main'


class RoverApp(MDApp):
    def build(self):
        sm = ScreenManager()
        sm.add_widget(SplashScreen(name='splash'))
        main_screen = MainScreen(name='main')
        sm.add_widget(main_screen)
        sm.add_widget(MapPlotScreen(name='mapplot'))
        # sm.current = 'main'

        return sm

if __name__ == '__main__':
    RoverApp().run()
