from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from gtts import gTTS
import os
import platform
import pygame

class TTSApp(App):
    def build(self):
        self.box = BoxLayout(orientation='vertical')

        self.label = Label(text='Enter text to convert to speech:')
        self.box.add_widget(self.label)

        self.text_input = TextInput(hint_text='Type here', multiline=False)
        self.box.add_widget(self.text_input)

        self.button = Button(text='Convert to Speech')
        self.button.bind(on_press=self.convert_text_to_speech)
        self.box.add_widget(self.button)

        return self.box

    def convert_text_to_speech(self, instance):
        text = self.text_input.text
        if text:
            tts = gTTS(text=text, lang='en')
            file_path = "audio/manualcammode.mp3"
            try:
                tts.save(file_path)
                self.play_sound(file_path)
                # os.remove(file_path)  # Remove the file after playing
            except Exception as e:
                print(f"Error: {e}")

    def play_sound(self, file_path):
        try:
            pygame.mixer.init()
            pygame.mixer.music.load(file_path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
        except Exception as e:
            print(f"Error: {e}")

if __name__ == '__main__':
    TTSApp().run()
