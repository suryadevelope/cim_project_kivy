

import subprocess
from tkinter import Image

# Step 1: List all listening sockets and their processes
command = "netstat -tulnp"
try:
    # Step 2: Execute the command and capture the output
    result = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, text=True)
    output_lines = result.stdout.splitlines()

    # Step 3: Extract PIDs and kill processes
    for line in output_lines[2:]:  # Skip the first two header lines
        fields = line.split()
        if len(fields) >= 7:
            proto = fields[0]
            recvq = fields[1]
            sendq = fields[2]
            local_address = fields[3]
            foreign_address = fields[4]
            state = fields[5]
            pid_program = fields[6]

            # Split PID and program name if available
            if '/' in pid_program:
                pid, program = pid_program.split('/')
                pid = pid.strip()
                program = program.strip()
                # Kill the process using its PID
                kill_command = f"kill -9 {pid}"
                subprocess.run(kill_command, shell=True, check=True)
                print(f"Killed process {program} with PID {pid}")
            else:
                print(f"Skipping line: {line}. PID and program name not found.")

    print("All processes with open sockets killed.")
except subprocess.CalledProcessError as e:
    print(f"Error executing command: {e}")





import socket
import cv2
import numpy as np
import pickle
import threading
from kivy.event import EventDispatcher

from kivy.properties import NumericProperty,ObjectProperty

class VideoReceiver(EventDispatcher):
    streamchange = NumericProperty(0)
    
    def __init__(self):
        super(VideoReceiver, self).__init__()
        self.port = 8000
        self.video_frames = {}

        receiver_thread = threading.Thread(target=self.setup_socket)
        receiver_thread.start()

    def setup_socket(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        socket_address = ("0.0.0.0", self.port)
        
        try:
            print(f"Listening at {socket_address}")
            self.server_socket.bind(socket_address)
            self.receive_video()
        
        except Exception as e:
            print(f"Error binding socket: {e}")
            
    def receive_video(self):
        while True:
            try:
                data, addr = self.server_socket.recvfrom(65507)  # Maximum UDP packet size
                
                # Deserialize the pickled frame
                identifier, encoded_frame = pickle.loads(data)
                
                nparr = np.frombuffer(encoded_frame, np.uint8)
                
                # Decode frame using OpenCV
                frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                
                # Check if the frame was successfully decoded
                if frame is None:
                    print(f"Failed to decode frame, skipping...{addr}")
                    continue
                
                # Update frame in the GUI
                self.video_frames[identifier] = frame

                self.streamchange = identifier

                # print(f"receiving video: {identifier}")
                # cv2.imshow(str(identifier),frame)
                
            except Exception as e:
                print(f"Error receiving video: {e}")
                # break
        
        self.server_socket.close()
    
    def getfeedbyid(self, id):
        if id in self.video_frames:
            return self.video_frames[id]
        else:
            return None