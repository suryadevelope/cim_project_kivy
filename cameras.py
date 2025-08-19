

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
        self.socket_lock = threading.Lock()
        self.last_frame_time = {}
        self.receiver_thread = threading.Thread(target=self.setup_socket, daemon=True)
        self.receiver_thread.start()
        self.cleanup_thread = threading.Thread(target=self.cleanup_stale_frames, daemon=True)
        self.cleanup_thread.start()
        
    def setup_socket(self):
        """Setup UDP socket for video reception"""
        try:
            with self.socket_lock:
                self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.server_socket.settimeout(1.0)  # 1 second timeout
                self.server_socket.bind(('0.0.0.0', self.port))
                print(f"Video receiver listening on port {self.port}")
                
            # Start receiving video after socket setup
            self.receive_video()
            
        except Exception as e:
            print(f"Error setting up video socket: {e}")
            self.running = False
    
    def receive_video(self):
        """Receive video frames from UDP socket"""
        while self.running:
            try:
                with self.socket_lock:
                    if not hasattr(self, 'server_socket'):
                        time.sleep(0.1)
                        continue
                        
                    data, addr = self.server_socket.recvfrom(65536)  # Increased buffer size
                    
                # Process the received data
                self.process_video_frame(data, addr)
                
            except socket.timeout:
                # Socket timeout is expected, continue
                continue
            except Exception as e:
                print(f"Error receiving video: {e}")
                time.sleep(0.1)
                
        # Cleanup socket
        try:
            with self.socket_lock:
                if hasattr(self, 'server_socket'):
                    self.server_socket.close()
        except:
            pass
    
    def process_video_frame(self, data, addr):
        """Process received video frame data"""
        try:
            # The transmission code sends: pickle.dumps((camera_index, encoded_frame))
            # So we need to unpickle and extract both values
            camera_index, encoded_frame = pickle.loads(data)
            
            # Decode the JPEG frame
            frame = cv2.imdecode(encoded_frame, cv2.IMREAD_COLOR)
            
            if frame is not None:
                # Store frame with camera index as key
                self.video_frames[camera_index] = frame
                self.last_frame_time[camera_index] = time.time()
                
                # Trigger UI update
                self.streamchange += 1
                
                print(f"Received frame from camera {camera_index}, size: {frame.shape}")
            else:
                print(f"Failed to decode frame from camera {camera_index}")
                
        except Exception as e:
            print(f"Error processing video frame: {e}")
    
    def cleanup_stale_frames(self):
        """Remove stale video frames to prevent memory accumulation"""
        while self.running:
            try:
                current_time = time.time()
                stale_cameras = []
                
                for cam_idx, last_time in self.last_frame_time.items():
                    if current_time - last_time > 5.0:  # 5 seconds timeout
                        stale_cameras.append(cam_idx)
                
                for cam_idx in stale_cameras:
                    if cam_idx in self.video_frames:
                        del self.video_frames[cam_idx]
                    if cam_idx in self.last_frame_time:
                        del self.last_frame_time[cam_idx]
                    print(f"Removed stale frames from camera {cam_idx}")
                
                time.sleep(1.0)  # Check every second
                
            except Exception as e:
                print(f"Error in cleanup thread: {e}")
                time.sleep(1.0)
    
    def get_latest_frame(self, camera_index=0):
        """Get the latest frame from specified camera"""
        return self.video_frames.get(camera_index, None)
    
    def get_all_frames(self):
        """Get all available video frames"""
        return self.video_frames.copy()
    
    def stop(self):
        """Stop the video receiver"""
        self.running = False
        if hasattr(self, 'receiver_thread'):
            self.receiver_thread.join(timeout=1.0)
        if hasattr(self, 'cleanup_thread'):
            self.cleanup_thread.join(timeout=1.0)
    
    def is_running(self):
        """Check if the video receiver is running"""
        return self.running
