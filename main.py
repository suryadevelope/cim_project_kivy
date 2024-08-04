import os
import random
import threading
import time
import cv2
from kivy.app import App
from kivymd.app import MDApp
from kivy.uix.screenmanager import ScreenManager, Screen
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
    canvas.before:
        Rectangle:
            # pos: self.pos
            size: min(root.width, root.height) * 1.45, min(root.width, root.height) * 1.10
            source: './assets/compass_bg.png'
 

    needle: needle
    Image:
        id: needle
        source: './assets/needle.png'
        size_hint: None, None
        size: min(root.width, root.height)*2.5, min(root.width, root.height)*1.5 # Set the size of the needle to 80% of the minimum dimension of the CompassWidget
        center: self.parent.center # Position the needle at the center of the CompassWidget
        keep_ratio: True
        allow_stretch: True
        angle: 0
        canvas.before:
            PushMatrix
            Rotate:
                angle: self.angle
                origin: self.center
                # origin: root.calculate_rotation_origin(self.angle, self.center_x, self.center_y, self.parent.width, self.parent.height) 
                # origin: self.calculate_rotation_origin(self.angle, self.width, self.height)  # Dynamically set origin based on angle
        canvas.after:
            PopMatrix
    
''')


class CompassWidget(BoxLayout):
    def calculate_rotation_origin(self, angle, center_x, center_y, width, height):
            # Calculate the rotation origin based on the angle, center, and dimensions
            import math
            half_width = width / 2
            half_height = height / 2
            angle = abs(angle)
            radians = math.radians(angle)
            x_offset = half_width * math.cos(radians)
            y_offset = half_height * math.sin(radians)
            return (center_x - x_offset, center_y - y_offset)  # Adjusted to ensure center positioning

    
    def set_needle_params(self, width, height):
        needle = self.ids.needle
        needle.size_hint = (width, height)
    def update_compass(self, angle):
        self.needle.angle = -angle
    def update_angle(self, dt):
        # Example: Rotate the needle randomly between 0 and 360 degrees.
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
        
      

    def on_enter(self):
        
        play_sound("waiting_conn.mp3")
        # Schedule a check to see if the condition is met every second
        # Clock.schedule_interval(self.check_condition, 1)
        # self.animate_progress_bar()

        
        Clock.schedule_once(self.switch_to_main, 5)


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
class MainScreen(Screen):

    img_src = StringProperty("./assets/bad_batt.png")
    jetsonimg_src = StringProperty("./assets/bad_batt.png")
    img_src_armstate = StringProperty("./assets/no_home.png")
    battimg = None
    def __init__(self, **kwargs):
        super(MainScreen, self).__init__(**kwargs)
        with self.canvas.before:
            Color(0.75, 0.75, 0.75, 1)  # Gray metal color
            self.rect = Rectangle(size=self.size, pos=self.pos)
        self.bind(size=self._update_rect, pos=self._update_rect)

        self.autoshowfullscreen = False
        self.updatefullscreenval=False
  
        self.allvideopopups = []
        


        layout = BoxLayout(orientation='horizontal', padding=10, spacing=10, size_hint=(1, 1))

        left_layout = BoxLayout(orientation='vertical', spacing=3, size_hint=(0.3, 1))

        bottom_box = BoxLayout(orientation='vertical', spacing=3, size_hint=(1, 0.5))

        clayout = BoxLayout(orientation='vertical')
        # clayout.canvas.before.add(Color(0, 1, 0, 1))  # Green color
        # clayout.canvas.before.add(Rectangle(size=clayout.size, pos=clayout.pos))

        # Create your custom widget and add it to the layout
        # self.compass_widget = CompassWidget()
        # self.compass_widget = None
        
        # self.compass_widget.size_hint = (None, None)
        # self.compass_widget.set_needle_params(1,1)

        # print("surya",self.compass_widget.pos)
        # streaming.setcompasswidget(self.compass_widget)
        
        # clayout.add_widget(self.compass_widget)

        # self.buttons = ['Cam 1', 'Cam 2', 'Cam 3']
        # for button_text in self.buttons:
        #     btn = Button(text=button_text, size_hint=(1, None), height=40)
        #     bottom_box.add_widget(btn)

        self.battimg = Image(source=self.img_src,size_hint=(1, None))
        self.armstateimg = Image(source=self.img_src_armstate,size_hint=(0.8, None))
        self.battstate = ""

        self.jetsonbattimg = Image(source=self.jetsonimg_src, size_hint=(1, None))

        layouttoped = BoxLayout(orientation='horizontal')
        mainbattview = BoxLayout(orientation='vertical',size_hint=(1, 1))
        armposview = BoxLayout(orientation='vertical',size_hint=(1, 1))
        batt_label = Label(text="Main Battery", size_hint=(1, 0.6),color=(1, 0, 1, 1))
        armpos_label = Label(text="Arm position", size_hint=(1, 0.7),color=(1, 0, 1, 1))

        # Add the images to the layout
        mainbattview.add_widget(self.battimg)
        mainbattview.add_widget(batt_label)

        armposview.add_widget(self.armstateimg)
        armposview.add_widget(armpos_label)

        layouttoped.add_widget(mainbattview)
        layouttoped.add_widget(armposview)
        

        card = MDCard(
            orientation='vertical',
            size_hint=(1, 1.8),
            pos_hint={"center_x": 0.5, "center_y": 0.5},
            elevation=3,
            md_bg_color="white"
        )


        card.add_widget(layouttoped)

        bottom_box.add_widget(card)  # Ensure this image exists
        

        self.switch = Switch(active=False)  # Switch starts in the off position
        self.switch.bind(active=self.on_switch_active)  # Bind the switch to a callback function

        # Create a label to display the switch state
        self.switch_label = Label(text="Switch is OFF")

        card = MDCard(
            orientation='vertical',
                size_hint=(1, 1.5),
                pos_hint={"center_x": 0.5, "center_y": 0.5},
                elevation=1,
                md_bg_color="white",
                padding=10
            )
        jetson_batt_label = Label(text="Jetson battery", size_hint=(1, 0.7),color=(1, 0, 1, 1))
        
        switch_label = Label(text="Switch", size_hint=(1, 0.7),color=(1, 0, 1, 1))
        
        
        layouttoped2 = BoxLayout(orientation='horizontal')

        layouttoped21 = BoxLayout(orientation='vertical')
        layouttoped21.add_widget(self.jetsonbattimg)
        layouttoped21.add_widget(jetson_batt_label)

        layouttoped22 = BoxLayout(orientation='vertical')
        layouttoped22.add_widget(self.switch)
        layouttoped22.add_widget(switch_label)

        layouttoped2.add_widget(layouttoped21)
        layouttoped2.add_widget(layouttoped22)


        card.add_widget(layouttoped2)
        
        bottom_box.add_widget(card)

        left_layout.add_widget(bottom_box)
        left_layout.add_widget(clayout)

        # Right grid for videos
        self.right_grid = GridLayout(cols=2, spacing=5, padding=5, size_hint=(0.7, 1))  # Adjusted size_hint for right grid
        self.image_widgets = []
        for _ in range(3):
            image = Image(source="./assets/no_cam.png")
            # image.bind(on_touch_down=self.on_video_touch)
            self.image_widgets.append(image)
            card = MDCard(
            orientation='vertical',
                size_hint=(1, 1),
                pos_hint={"center_x": 0.5, "center_y": 0.5},
                elevation=1,
                md_bg_color="white",
                padding=10
            )


            card.add_widget(image)

            self.right_grid.add_widget(card)
            streaming.bind(update_event=self.update_joystickview)
        
        streaming.bind(update_utils=self.update_utilsdata_ui)

        layout.add_widget(left_layout)
        layout.add_widget(self.right_grid)
        self.add_widget(layout)
        streaming.videosections = self.image_widgets

        self.queue = Queue()

        # Start the thread to capture video feed
        # self.capture_thread = threading.Thread(target=self.capture_video_feed)
        # self.capture_thread.daemon = True
        # self.capture_thread.start()
        toast("App started")

       

        self.bind(size=self.on_size)  # Bind the on_size method to be called whenever the size changes
    
    # Start the thread to capture video feed
    def on_switch_active(self, instance, value):
        # Update the label text when the switch is toggled
        
        if value:
            self.switch_label.text = "Switch is ON"
            self.autoshowfullscreen=True
            toast("Auto cam zoom mode ON")
            
        else:
            self.switch_label.text = "Switch is OFF"
            self.autoshowfullscreen=False
            toast("Auto cam zoom mode OFF")

            if(self.updatefullscreenval==True):
                self.dismiss_full_screen(self.popup)


            
    def update_utilsdata_ui(self, instance, value):
        print("surya", float(value["batvoltage"])<=25)
        
        if int(float(value["batvoltage"])) <= 25:
            print("low voltage")
            self.img_src = './assets/bad_batt.png'
        else:
            print("high voltage")
            self.img_src = './assets/good_batt.png'

        if int(float(value["jetsonvoltage"])) <= 11.5:
            print("low voltage")
            self.jetsonimg_src = './assets/bad_batt.png'
        else:
            print("high voltage")
            self.jetsonimg_src = './assets/good_batt.png'

        if int(value["armstate"]) == 1:
            self.img_src_armstate = "./assets/no_home.png"
        else:
            self.img_src_armstate = "./assets/at_home.png"

      
        Clock.schedule_once(lambda dt: self.update_ui_on_main_thread())

    def update_ui_on_main_thread(self):
        # Perform any additional UI updates here if needed
        self.battimg.source = self.img_src
        self.armstateimg.source = self.img_src_armstate
        self.jetsonbattimg.source = self.jetsonimg_src
      
  
        

    def update_joystickview(self, instance, value):
        if(self.autoshowfullscreen):
            value = int(value)

            if(value >= 0):
                # self.on_image_click(self.image_widgets[value])
                self.close_all_popups()
                img = None
                if(value == 0):
                    img = self.image_widgets[value]
                elif(value == 1):
                    img = self.image_widgets[value]
                elif(value == 2):
                    img = self.image_widgets[value]
                    
                
                class SimulatedTouch:
                    def __init__(self, pos):
                        self.pos = pos

                simulated_touch = SimulatedTouch(img.center)
               
                Clock.schedule_once(lambda dt: img.dispatch('on_touch_down', simulated_touch), 0)
            

            if(value <0):
                if(self.updatefullscreenval==True):
                    # self.dismiss_full_screen(self.popup)
                    self.close_all_popups()

   
   
    def update_image(self, dt):
              
            keys = list(self.videoreceiver.video_frames.keys())
            for i, identifier in enumerate(keys):
                if identifier in self.videoreceiver.video_frames:
                    frame = self.videoreceiver.video_frames[identifier]
                    if frame is not None:
                        # Convert the frame to Kivy texture
                        # Convert frame to uint8 if necessary (ensure it's already in uint8 format)
                        if frame.dtype != np.uint8:
                            frame = frame.astype(np.uint8)
                        # Add text to the frame
                        cv2.putText(frame, f"cam{i}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)
                        
                        # Flip the frame if needed (adjust as per your requirement)
                        frame = cv2.flip(frame, 0)

                        # Convert frame to bytes for texture blitting
                        buffer = frame.tobytes()
                        texture = Texture.create(size=(frame.shape[1], frame.shape[0]), colorfmt='bgr')
                        texture.blit_buffer(buffer, colorfmt='bgr', bufferfmt='ubyte')

                        # Update the image widget with the new texture
                        self.image_widgets[i].texture = texture
                   

    def create_texture(self, frame_rgb):
        texture = Texture.create(size=(frame_rgb.shape[1], frame_rgb.shape[0]))
        texture.blit_buffer(frame_rgb.tobytes(), colorfmt='rgb', bufferfmt='ubyte')
        return texture
    
    def updatefullscreen(self,image_widget,fullscreenview):
        fullscreenview.texture = image_widget.texture


    def on_image_click(self, image_widget):
        texture = image_widget.texture
        self.updatefullscreenval=True
        if texture:
            popup_layout = BoxLayout(orientation='vertical')
            popup_image = Image(texture=texture, size_hint=(1, 1),allow_stretch=True, keep_ratio=False)
            close_btn = Button(text='Close', size_hint=(1, 0.1))
            popup_layout.add_widget(popup_image)
            popup_layout.add_widget(close_btn)

            self.popup = Popup(content=popup_layout, auto_dismiss=False, size_hint=(1, 1))
            self.allvideopopups.append(self.popup)
            close_btn.bind(on_release=lambda instance: self.dismiss_full_screen(self.allvideopopups[-1]))

            self.popup.open()
            Clock.schedule_interval(lambda dt: self.updatefullscreen(image_widget,popup_image), 1.0 / 30.0)

            # self.updatefullscreenthread = threading.Thread(target=self.updatefullscreen,args=(image_widget,popup_image,))
            # self.updatefullscreenthread.start()
           
    
    def dismiss_full_screen(self, popup):
            # Stop updating the image widget
            Clock.unschedule(self.updatefullscreen)
            # Dismiss the popup
            popup.dismiss()
            # Set update_full_screen_val to False
            self.update_full_screen_val = False
 
    def close_all_popups(self):
            for popup in self.allvideopopups:
                # popup.dismiss()
                self.dismiss_full_screen(popup)
            if len(self.allvideopopups) > 10:
                # Delete the first item (index 0)
                del self.allvideopopups[0]
            # self.allvideopopups.clear()
            
    def on_enter(self):
        # Bind the image click event
        for image_widget in self.image_widgets:
            image_widget.bind(on_touch_down=self.on_image_touch)

         # Schedule the update of images in the GUI
        self.videoreceiver = VideoReceiver()
        # self.videoreceiver.bind(streamchange=self.capture_video_feed)  # Bind the switch to a callback function


        Clock.schedule_interval(self.update_image, 1.0 / 30.0)  # Update at 30 FPS


       

    def on_image_touch(self, image_widget, touch):
        if image_widget.collide_point(*touch.pos):
            self.on_image_click(image_widget)

    def on_leave(self):
        # Unbind the image click event
        for image_widget in self.image_widgets:
            image_widget.unbind(on_touch_down=self.on_image_touch)

    def on_size(self, instance, size):
        # Update the size of the compass widget dynamically based on the available space
        # self.compass_widget.size = (size[0] * 0.3, size[1] * 0.4)  # Adjust size as needed
        for image_widget in self.image_widgets:
            image_widget.size = (size[0] * 0.35, size[1] * 0.45)

    def _update_rect(self, instance, value):
            self.rect.size = instance.size
            self.rect.pos = instance.pos

# App class
class RoverApp(MDApp):
    def build(self):
        sm = ScreenManager()
        sm.add_widget(SplashScreen(name='splash'))
        main_screen = MainScreen(name='main')
        sm.add_widget(main_screen)
        

        return sm

if __name__ == '__main__':
    RoverApp().run()
