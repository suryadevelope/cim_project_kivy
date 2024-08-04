import random
import threading
import cv2
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.image import Image
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button, Label
from kivy.clock import Clock
from kivy.uix.video import Video
from kivy.uix.popup import Popup
from kivy.uix.gridlayout import GridLayout
from kivy.graphics import Color, Rectangle
from stream import Stream
from kivy.graphics.texture import Texture
from kivy.uix.togglebutton import ToggleButton

# from compass import CompassWidget

from kivy.lang import Builder
from kivy.core.image import Image as CoreImage
from queue import Queue
from kivy.uix.switch import Switch

Builder.load_string('''
<CompassWidget>:
    size_hint: 1, 1
   
    canvas.before:
        Rectangle:
            pos: self.pos
            size: self.size
            source: './assets/compass_bg.png'

    needle: needle
    Image:
        id: needle
        source: './assets/needle.png'
        size_hint: None, None
        size: min(root.width, root.height) * 0.8, min(root.width, root.height) * 0.8  # Set the size of the needle to 80% of the minimum dimension of the CompassWidget
        center: self.parent.center  # Position the needle at the center of the CompassWidget
        allow_stretch: True
        keep_ratio: True
        angle: 0
        canvas.before:
            PushMatrix
            Rotate:
                angle: self.angle
                origin: self.center
        canvas.after:
            PopMatrix
''')


class CompassWidget(BoxLayout):
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
        self.add_widget(Image(source='./assets/splash_image.png'))  # Ensure this image exists

    def on_enter(self):
        Clock.schedule_once(self.switch_to_main, 3)

    def switch_to_main(self, dt):
        self.manager.current = 'main'

# Main Screen
class MainScreen(Screen):
    def __init__(self, **kwargs):
        super(MainScreen, self).__init__(**kwargs)
        self.autoshowfullscreen = False


        layout = BoxLayout(orientation='horizontal', padding=10, spacing=10, size_hint=(1, 1))

        left_layout = BoxLayout(orientation='vertical', spacing=10, size_hint=(0.3, 1))

        bottom_box = BoxLayout(orientation='vertical', spacing=10, size_hint=(1, 0.5))

        clayout = BoxLayout(orientation='vertical')
        # clayout.canvas.before.add(Color(0, 1, 0, 1))  # Green color
        # clayout.canvas.before.add(Rectangle(size=clayout.size, pos=clayout.pos))

        # Create your custom widget and add it to the layout
        self.compass_widget = CompassWidget()
        self.compass_widget.size_hint = (None, None)
        self.compass_widget.set_needle_params(1,1)

        print("surya",self.compass_widget.pos)
        streaming.setcompasswidget(self.compass_widget)
        clayout.add_widget(self.compass_widget)

        self.buttons = ['Cam 1', 'Cam 2', 'Cam 3']
        for button_text in self.buttons:
            btn = Button(text=button_text, size_hint=(1, None), height=40)
            bottom_box.add_widget(btn)

        self.switch = Switch(active=False)  # Switch starts in the off position
        self.switch.bind(active=self.on_switch_active)  # Bind the switch to a callback function

        # Create a label to display the switch state
        self.switch_label = Label(text="Switch is OFF")
        bottom_box.add_widget(self.switch)

        left_layout.add_widget(bottom_box)
        left_layout.add_widget(clayout)

        # Right grid for videos
        self.right_grid = GridLayout(cols=2, spacing=5, padding=5, size_hint=(0.7, 1))  # Adjusted size_hint for right grid
        self.image_widgets = []
        for _ in range(4):
            image = Image()
            # image.bind(on_touch_down=self.on_video_touch)
            self.image_widgets.append(image)
            self.right_grid.add_widget(image)

        layout.add_widget(left_layout)
        layout.add_widget(self.right_grid)
        self.add_widget(layout)

        self.queue = Queue()

        # Start the thread to capture video feed
        self.capture_thread = threading.Thread(target=self.capture_video_feed)
        self.capture_thread.daemon = True
        self.capture_thread.start()

        # Schedule the update of images in the GUI
        Clock.schedule_interval(self.update_image, 1.0 / 30.0)  # Update at 30 FPS


        self.bind(size=self.on_size)  # Bind the on_size method to be called whenever the size changes
    # Start the thread to capture video feed
    def on_switch_active(self, instance, value):
        # Update the label text when the switch is toggled
        
        if value:
            self.switch_label.text = "Switch is ON"
            self.autoshowfullscreen=True
        else:
            self.switch_label.text = "Switch is OFF"
            self.autoshowfullscreen=False


    def capture_video_feed(self):
        cap = cv2.VideoCapture(0)  # Access the default camera
        while True:
            ret, frame = cap.read()
            if ret:
                frame = cv2.flip(frame, 0)  # Flip the frame vertically (optional)

                # Convert the frame to RGB format (Kivy requires RGB)
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                # Put the frame into the queue
                self.queue.put(frame_rgb)

   
    def update_image(self, dt):
        while not self.queue.empty():
            frame_rgb = self.queue.get()
            texture = self.create_texture(frame_rgb)
            for image_widget in self.image_widgets:
                image_widget.texture = texture

    def create_texture(self, frame_rgb):
        texture = Texture.create(size=(frame_rgb.shape[1], frame_rgb.shape[0]))
        texture.blit_buffer(frame_rgb.tostring(), colorfmt='rgb', bufferfmt='ubyte')
        return texture
    
    def updatefullscreen(self,image_widget,fullscreenview):
        fullscreenview.texture = image_widget.texture


    def on_image_click(self, image_widget):
        texture = image_widget.texture
        self.updatefullscreenval=True
        if texture:
            popup_layout = BoxLayout(orientation='vertical')
            popup_image = Image(texture=texture, size_hint=(1, 1))
            close_btn = Button(text='Close', size_hint=(1, 0.1))
            popup_layout.add_widget(popup_image)
            popup_layout.add_widget(close_btn)

            popup = Popup(content=popup_layout, auto_dismiss=False, size_hint=(1, 1))
            close_btn.bind(on_release=lambda instance: self.dismiss_full_screen(popup))

            popup.open()
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
 

    def on_enter(self):
        # Bind the image click event
        for image_widget in self.image_widgets:
            image_widget.bind(on_touch_down=self.on_image_touch)

    def on_image_touch(self, image_widget, touch):
        if image_widget.collide_point(*touch.pos):
            self.on_image_click(image_widget)

    def on_leave(self):
        # Unbind the image click event
        for image_widget in self.image_widgets:
            image_widget.unbind(on_touch_down=self.on_image_touch)

    def on_size(self, instance, size):
        # Update the size of the compass widget dynamically based on the available space
        self.compass_widget.size = (size[0] * 0.3, size[1] * 0.4)  # Adjust size as needed
        for image_widget in self.image_widgets:
            image_widget.size = (size[0] * 0.35, size[1] * 0.45)


# App class
class RoverApp(App):
    def build(self):
        sm = ScreenManager()
        sm.add_widget(SplashScreen(name='splash'))
        main_screen = MainScreen(name='main')
        sm.add_widget(main_screen)
        return sm

if __name__ == '__main__':
    RoverApp().run()
