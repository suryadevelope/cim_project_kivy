

# import subprocess

# # Step 1: List all listening sockets and their processes
# command = "netstat -tulnp"
# try:
#     # Step 2: Execute the command and capture the output
#     result = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, text=True)
#     output_lines = result.stdout.splitlines()

#     # Step 3: Extract PIDs and kill processes
#     for line in output_lines[2:]:  # Skip the first two header lines
#         fields = line.split()
#         if len(fields) >= 7:
#             proto = fields[0]
#             recvq = fields[1]
#             sendq = fields[2]
#             local_address = fields[3]
#             foreign_address = fields[4]
#             state = fields[5]
#             pid_program = fields[6]

#             # Split PID and program name if available
#             if '/' in pid_program:
#                 pid, program = pid_program.split('/')
#                 pid = pid.strip()
#                 program = program.strip()
#                 # Kill the process using its PID
#                 kill_command = f"kill -9 {pid}"
#                 subprocess.run(kill_command, shell=True, check=True)
#                 print(f"Killed process {program} with PID {pid}")
#             else:
#                 print(f"Skipping line: {line}. PID and program name not found.")

#     print("All processes with open sockets killed.")
# except subprocess.CalledProcessError as e:
#     print(f"Error executing command: {e}")



# import socket
# import cv2
# import numpy as np
# import pickle
# import argparse
# import tkinter as tk
# from PIL import Image, ImageTk
# import threading

# class VideoReceiverApp:
#     def __init__(self, root, port):
#         self.root = root
#         self.port = port
#         self.video_frames = {}
#         self.setup_ui()
#         self.setup_socket()

#     def setup_ui(self):
#         self.root.title("Video Feeds")
#         self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
#         self.frames = {}
#         self.labels = {}
        
#         for i in range(2):  # Assuming 2 video feeds, adjust as needed
#             frame = tk.Frame(self.root, width=640, height=480)
#             frame.grid(row=0, column=i)
#             self.frames[i] = frame
            
#             label = tk.Label(frame)
#             label.pack()
#             self.labels[i] = label
        
#     def setup_socket(self):
#         self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
#         socket_address = ("0.0.0.0", self.port)
        
#         try:
#             self.server_socket.bind(socket_address)
#             print(f"Listening at {socket_address}")
#             self.receive_video()
        
#         except Exception as e:
#             print(f"Error binding socket: {e}")
#             self.root.destroy()
        
#     def receive_video(self):
#         while True:
#             try:
#                 data, addr = self.server_socket.recvfrom(65507)  # Maximum UDP packet size
                
#                 # Deserialize the pickled frame
#                 identifier, encoded_frame = pickle.loads(data)
#                 print(f"Received frame from {identifier}")
                
#                 nparr = np.frombuffer(encoded_frame, np.uint8)
                
#                 # Decode frame using OpenCV
#                 frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                
#                 # Check if the frame was successfully decoded
#                 if frame is None:
#                     print(f"Failed to decode frame, skipping...{addr}")
#                     continue
                
#                 # Update frame in the GUI
#                 if identifier in self.video_frames:
#                     self.video_frames[identifier] = frame
#                 else:
#                     self.video_frames[identifier] = frame
                
#                 # Display frames in the GUI
#                 self.update_gui()
            
#             except Exception as e:
#                 print(f"Error receiving video: {e}")
#                 break
        
#         self.server_socket.close()
    
#     def update_gui(self):
#         for i, identifier in enumerate(self.video_frames):
#             if identifier in self.video_frames:
#                 frame = cv2.cvtColor(self.video_frames[identifier], cv2.COLOR_BGR2RGB)
#                 frame = Image.fromarray(frame)
#                 frame = ImageTk.PhotoImage(frame)
#                 self.labels[i].config(image=frame)
#                 self.labels[i].image = frame
    
#     def on_close(self):
#         self.root.destroy()

# def start_video_receiver(root, port):
#     app = VideoReceiverApp(root, port)

# def main():
#     parser = argparse.ArgumentParser(description="Server to receive video streams over UDP.")
#     parser.add_argument('--port', type=int, default=8000, help='UDP port to listen on.')
#     args = parser.parse_args()
    
#     root = tk.Tk()
#     # Create a thread for running VideoReceiverApp
#     receiver_thread = threading.Thread(target=start_video_receiver, args=(root, args.port))
#     receiver_thread.start()
    
#     root.mainloop()
    
#     # Ensure thread terminates properly before exiting
#     receiver_thread.join()

# if __name__ == '__main__':
#     main()





import socket
import threading
import cv2
import numpy as np
import pickle
import argparse
from kivy.app import App
from kivy.uix.image import Image
from kivy.uix.boxlayout import BoxLayout
from kivy.graphics.texture import Texture
from kivy.clock import Clock

class VideoReceiverApp(App):
    def __init__(self, port, **kwargs):
        super().__init__(**kwargs)
        self.port = port
        self.video_frames = {}
        self.server_socket = None

    def build(self):
        self.root = BoxLayout(orientation='horizontal')
        self.image_widgets = []

        for _ in range(2):  # Assuming 2 video feeds, adjust as needed
            image_widget = Image(size_hint=(0.5, 1))
            self.root.add_widget(image_widget)
            self.image_widgets.append(image_widget)

        return self.root

    def on_start(self):
        self.setup_socket()
        Clock.schedule_interval(self.update_gui, 1.0 / 30)  # Update at 30 FPS

    def setup_socket(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        socket_address = ("0.0.0.0", self.port)
        
        try:
            self.server_socket.bind(socket_address)
            print(f"Listening at {socket_address}")
            self.receive_video_thread = threading.Thread(target=self.receive_video)
            self.receive_video_thread.start()
        
        except Exception as e:
            print(f"Error binding socket: {e}")
            self.stop()

    def receive_video(self):
        while True:
            try:
                data, addr = self.server_socket.recvfrom(65507)  # Maximum UDP packet size
                
                # Deserialize the pickled frame
                identifier, encoded_frame = pickle.loads(data)
                print(f"Received frame from {identifier}")
                
                nparr = np.frombuffer(encoded_frame, np.uint8)
                
                # Decode frame using OpenCV
                frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                
                # Check if the frame was successfully decoded
                if frame is None:
                    print(f"Failed to decode frame, skipping...{addr}")
                    continue
                
                # Update frame in the dictionary
                self.video_frames[identifier] = frame
            
            except Exception as e:
                print(f"Error receiving video: {e}")
                break

        self.server_socket.close()

    def update_gui(self, dt):
        for i, (identifier, frame) in enumerate(self.video_frames.items()):
            if frame is not None:
                # Convert the frame to Kivy texture
                buffer = cv2.flip(frame, 0).tobytes()
                texture = Texture.create(size=(frame.shape[1], frame.shape[0]), colorfmt='bgr')
                texture.blit_buffer(buffer, colorfmt='bgr', bufferfmt='ubyte')
                # texture.flip_vertical()

                # Update the image widget with the new texture
                self.image_widgets[i].texture = texture

    def on_stop(self):
        if self.server_socket:
            self.server_socket.close()
        if hasattr(self, 'receive_video_thread'):
            self.receive_video_thread.join()

def main():
    parser = argparse.ArgumentParser(description="Server to receive video streams over UDP.")
    parser.add_argument('--port', type=int, default=8000, help='UDP port to listen on.')
    args = parser.parse_args()
    
    VideoReceiverApp(port=args.port).run()

if __name__ == '__main__':
    main()
