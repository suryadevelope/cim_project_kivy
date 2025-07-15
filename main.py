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
    img_src = StringProperty("./assets/bad_batt.png")
    jetsonimg_src = StringProperty("./assets/bad_batt.png")
    img_src_armstate = StringProperty("./assets/no_home.png")
    battimg = None
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
        mapplot_btn_top = Button(text="Map Plotting", size_hint_x=None, width=140, height=40, background_color=(0.1, 0.5, 0.2, 1), font_size='16sp')
        mapplot_btn_top.bind(on_release=self.goto_mapplot)
        top_nav.add_widget(mapplot_btn_top)
        top_nav.add_widget(Label(size_hint_x=1))

        root_layout = BoxLayout(orientation='vertical', size_hint=(1, 1), padding=[10, 10, 10, 10], spacing=10)
        root_layout.add_widget(top_nav)
        main_layout = BoxLayout(orientation='horizontal', spacing=16, size_hint_y=1)

        # --- Left: MapView (top) and CompassWidget + Start/Stop (bottom) ---
        left_panel = BoxLayout(orientation='vertical', spacing=12, size_hint=(0.48, 1))
        mapview_container = BoxLayout(size_hint=(1, 0.62), padding=0)
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
        if int(float(value["batvoltage"])) <= 25:
            self.img_src = './assets/bad_batt.png'
        else:
            self.img_src = './assets/good_batt.png'
        if int(float(value["jetsonvoltage"])) <= 11.5:
            self.jetsonimg_src = './assets/bad_batt.png'
        else:
            self.jetsonimg_src = './assets/good_batt.png'
        if int(value["armstate"]) == 1:
            self.img_src_armstate = "./assets/no_home.png"
        else:
            self.img_src_armstate = "./assets/at_home.png"
        Clock.schedule_once(lambda dt: self.update_ui_on_main_thread())

    def update_ui_on_main_thread(self):
        self.battimg.source = self.img_src
        self.armstateimg.source = self.img_src_armstate
        self.jetsonbattimg.source = self.jetsonimg_src

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
        # sm.current = 'main'

        return sm

if __name__ == '__main__':
    RoverApp().run()
