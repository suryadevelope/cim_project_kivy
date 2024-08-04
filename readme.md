Step 1: Update the Project Directory Structure

css

rover_app/
├── main.py
├── assets/
│   ├── splash_image.png
│   ├── logo.png
└── rover_app.spec

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
