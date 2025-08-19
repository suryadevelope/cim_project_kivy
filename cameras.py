

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
import time
from kivy.event import EventDispatcher
from kivy.properties import NumericProperty, ObjectProperty

class VideoReceiver(EventDispatcher):
    streamchange = NumericProperty(0)
    
    def __init__(self):
        super(VideoReceiver, self).__init__()
        self.port = 8000  # Use different port than control system
        self.video_frames = {}
        self.running = True
        self.socket_lock = threading.Lock()  # Add lock for socket operations
        self.last_frame_time = {}  # Track last frame time for each camera

        # Start receiver thread
        self.receiver_thread = threading.Thread(target=self.setup_socket, daemon=True)
        self.receiver_thread.start()
        
        # Start cleanup thread to remove stale frames
        self.cleanup_thread = threading.Thread(target=self.cleanup_stale_frames, daemon=True)
        self.cleanup_thread.start()

    def setup_socket(self):
        """Setup UDP socket for video reception with better error handling"""
        try:
            with self.socket_lock:
                self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.server_socket.settimeout(1.0)  # Add timeout to prevent blocking
                socket_address = ("0.0.0.0", self.port)
                
                print(f"Video receiver listening at {socket_address}")
                self.server_socket.bind(socket_address)
                
                # Start receiving video
                self.receive_video()
        except Exception as e:
            print(f"Error setting up video socket: {e}")
            self.running = False

    def receive_video(self):
        """Receive video frames with improved error handling and non-blocking operation"""
        print("Starting video reception...")
        
        while self.running:
            try:
                with self.socket_lock:
                    if not hasattr(self, 'server_socket') or self.server_socket is None:
                        break
                    
                    # Use timeout to prevent blocking
                    data, addr = self.server_socket.recvfrom(65507)
                    
                    if not data:
                        continue
                    
                    # Process the received frame
                    self.process_video_frame(data, addr)
                    
            except socket.timeout:
                # Timeout is expected, continue listening
                continue
            except Exception as e:
                print(f"Error receiving video: {e}")
                time.sleep(0.1)  # Small delay before retrying
                continue
        
        # Clean up socket
        try:
            with self.socket_lock:
                if hasattr(self, 'server_socket') and self.server_socket:
                    self.server_socket.close()
        except Exception as e:
            print(f"Error closing video socket: {e}")

    def process_video_frame(self, data, addr):
        """Process received video frame data"""
        try:
            # Deserialize the pickled frame
            identifier, encoded_frame = pickle.loads(data)
            
            # Decode frame using OpenCV
            nparr = np.frombuffer(encoded_frame, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            # Check if the frame was successfully decoded
            if frame is None or frame.size == 0:
                print(f"Failed to decode frame from {addr}, skipping...")
                return
            
            # Update frame in the GUI with timestamp
            current_time = time.time()
            self.video_frames[identifier] = frame
            self.last_frame_time[identifier] = current_time
            
            # Trigger UI update
            self.streamchange = identifier
            
        except Exception as e:
            print(f"Error processing video frame: {e}")

    def cleanup_stale_frames(self):
        """Remove frames that are older than 5 seconds to prevent memory issues"""
        while self.running:
            try:
                current_time = time.time()
                stale_cameras = []
                
                for camera_id, last_time in self.last_frame_time.items():
                    if current_time - last_time > 5.0:  # 5 second timeout
                        stale_cameras.append(camera_id)
                
                # Remove stale frames
                for camera_id in stale_cameras:
                    if camera_id in self.video_frames:
                        del self.video_frames[camera_id]
                    if camera_id in self.last_frame_time:
                        del self.last_frame_time[camera_id]
                
                time.sleep(1.0)  # Check every second
                
            except Exception as e:
                print(f"Error in cleanup thread: {e}")
                time.sleep(1.0)

    def getfeedbyid(self, id):
        """Get video frame by camera ID with validation"""
        if id in self.video_frames:
            frame = self.video_frames[id]
            # Check if frame is still valid
            if frame is not None and frame.size > 0:
                return frame
        return None

    def stop(self):
        """Stop the video receiver gracefully"""
        self.running = False
        try:
            with self.socket_lock:
                if hasattr(self, 'server_socket') and self.server_socket:
                    self.server_socket.close()
        except Exception as e:
            print(f"Error stopping video receiver: {e}")

    def is_running(self):
        """Check if video receiver is running"""
        return self.running
