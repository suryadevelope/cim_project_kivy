import signal
import subprocess
import sys
from threading import Thread
import time
import pygame
import socket
import tkinter as tk
import json
from kivy.clock import Clock
from kivy.event import EventDispatcher
from kivymd.toast import toast


from kivy.properties import NumericProperty,ObjectProperty

# root = tk.Tk()

Stream_2_IP = "192.168.1.10"
Stream_2_PORT = 5005
LISTEN_IP = "0.0.0.0"  # Listen on all interfaces
LISTEN_PORT = 5006



print("main.py started")

def is_port_in_use(port):
    try:
        output = subprocess.check_output(["netstat", "-tuln"])
        lines = output.decode("utf-8").split("\n")
        for line in lines:
            parts = line.split()
            if len(parts) >= 4:
                if parts[3] == f"0.0.0.0:{port}":
                    return True  # Port is in use
        return False  # Port is not in use
    except subprocess.CalledProcessError as e:
        print(f"Error checking port {port}: {e}")
        return None  # Error occurred

def close_port_if_running(port):
    try:
        subprocess.run(["fuser", "-k", f"{port}/tcp"])
        print(f"Closed port {port}.")
    except Exception as e:
        print(f"Error closing port {port}: {e}")


port_status = is_port_in_use(LISTEN_PORT)
if port_status is None:

    print(f"An error occurred while checking port {LISTEN_PORT}.")
    
elif port_status:
    print(f"Port {LISTEN_PORT} is in use.")
    
    close_port_if_running(LISTEN_PORT)
else:
    print(f"Port {LISTEN_PORT} is not in use.")
    




# Initialize the two UDP sockets
Stream2_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
Listen_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
Listen_socket.bind((LISTEN_IP, LISTEN_PORT))


# Define a signal handler function
def signal_handler(sig, frame):
    print('Closing socket...')
    Listen_socket.close()
    sys.exit(0)

# Register the signal handler for termination signals
signal.signal(signal.SIGINT, signal_handler)  # Handles Ctrl+C
signal.signal(signal.SIGTERM, signal_handler) # Handles termination signal



class Stream(EventDispatcher):
    update_event = NumericProperty(0)
    update_utils= ObjectProperty({})

    dataconfirm={
        "compass":False,
        "jetsonvoltage":0
    }

    videosections = None

    def __init__(self, **kwargs):
        super(Stream, self).__init__(**kwargs)
        self.compasswidget = None
        self.thread = Thread(target=self.runjoystick,daemon=True)
        self.thread.start()

        self.listen_thread = Thread(target=self.listen_udp,daemon=True)
        self.listen_thread.start()

    def updatevideoview(self,view):
        self.update_event = view
            # print(self.videosections[view])


    # Define a function to map joystick input to movement values
    def map_input_to_movement(self, value, dead_zone=0.1):
        # Apply dead zone correction
        if abs(value) < dead_zone:
            return 0
        
        # Scale joystick input to desired movement range
        movement = int(value * 255)
        if movement > 255:
            movement = 255
        elif movement < -255:
            movement = -255
        
        return movement

    # Define a function to send UDP packets to the specified destination
    def send_udp_packet(self,socket, data, ip, port):
        try:
            socket.sendto(data.encode(), (ip, port))
        except Exception as e:
            if(str(e).startswith("[Errno 101] Network is unreachable")):
                print("Please connect the router and restart the app")
                toast("Please connect the router and restart the app")

            print(f"Error sending UDP packet: {e}")

    def map_value(self,value, in_min, in_max, out_min, out_max):
        # Map the value from the input range to the output range
        return (value - in_min) * (out_max - out_min) / (in_max - in_min) + out_min



    def runjoystick(self): 
        # Initialize the pygame library and joysticks
        
           
        while True:
            pygame.init()
            pygame.joystick.init()   
            for joystick_id in range(pygame.joystick.get_count()):
                joystick = pygame.joystick.Joystick(joystick_id)
                joystick.init()
                joystick_name = joystick.get_name()

                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        pygame.quit()
                        exit()

                x_axis = joystick.get_axis(0)
                y_axis = joystick.get_axis(1)
            
                lift_speed = round(self.map_value(joystick.get_axis(3), 1, -1, 20, 100),2) 
        
                clicked = joystick.get_button(0)
                release = joystick.get_button(1)

                centerliftknob = joystick.get_hat(0)[1]

                holdobject = -1

                if(clicked ==1 and release==0):
                    holdobject = 1
                    self.updatevideoview(2)

                elif(clicked ==1 and release==1):
                    holdobject=0
                    self.updatevideoview(2)

                if(holdobject==-1):
                    self.updatevideoview(-1)




                x_movement = self.map_input_to_movement(x_axis, dead_zone=0.2)  # Example dead zone of 0.1
                y_movement = self.map_input_to_movement(y_axis, dead_zone=0.2)  # Example dead zone of 0.1


                
                speed = (abs(y_movement) + abs(x_movement))/2

                # Check diagonal directions first
                if y_movement < 0 and x_movement < 0:
                    direction = "7"  # Forward-left
                    self.updatevideoview(0)
                elif y_movement < 0 and x_movement > 0:
                    direction = "9"  # Forward-right
                    self.updatevideoview(0)
                elif y_movement > 0 and x_movement < 0:
                    direction = "1"  # Backward-left
                    self.updatevideoview(1)
                elif y_movement > 0 and x_movement > 0:
                    direction = "3"  # Backward-right
                    self.updatevideoview(1)


                elif y_movement > 0:
                    speed = abs(y_movement)
                    direction = "5"#backward
                    self.updatevideoview(1)
                elif y_movement < 0:
                    speed = abs(y_movement)
                    direction = "8"#forward
                    self.updatevideoview(0)

                # else:
                #     speed = 0
                #     direction = "115"#stop
                #     self.updatevideoview(-2)


                # data = "@{},{},{},{},{}".format(speed, direction, holdobject,centerliftknob,lift_speed)
                # print(data)
            
                # if joystick_id == 0:
                #     self.send_udp_packet(Stream2_socket, data, Stream_2_IP, Stream_2_PORT)

                elif x_movement > 0:
                    speed = abs(x_movement)
                    direction = "6"#right
                elif x_movement < 0:
                    speed = abs(x_movement)
                    direction = "4"#left
                else:
                    speed = 0
                    direction = "115"
                    self.updatevideoview(-2)

                data = "@{},{},{},{},{}".format(speed, direction, holdobject,centerliftknob,lift_speed)

                if joystick_id == 0:
                    self.send_udp_packet(Stream2_socket, data, Stream_2_IP, Stream_2_PORT)

                # print(data)
                pygame.time.wait(1)

    def listen_udp(self):
        while True:
        
            try:
                data, addr = Listen_socket.recvfrom(1024)
                compassdata = str(data.decode())

                if(compassdata!='None'):
                    # Try to parse as JSON first (new format)
                    try:
                        json_data = json.loads(compassdata)
                        print("Received JSON data:", json_data)
                        
                        # Handle new JSON data structure
                        if "utils" in json_data and "compass" in json_data and "gps" in json_data and "autonomous" in json_data:
                            # Parse utils data (format: "#1=26.66=55.56")
                            utils_str = json_data["utils"]
                            if utils_str.startswith("#"):
                                parts = utils_str[1:].split("=")
                                if len(parts) >= 3:
                                    self.update_utils = {
                                        "armstate": parts[0] if len(parts) > 0 else "0",
                                        "batvoltage": parts[1] if len(parts) > 1 else "0",
                                        "jetsonvoltage": parts[2] if len(parts) > 2 else "0",
                                        "gps": json_data["gps"],
                                        "compass": json_data["compass"],
                                        "autonomous": json_data["autonomous"]
                                    }
                                    
                                    # Update compass widget
                                    if json_data["compass"] != "None" and self.compasswidget is not None:
                                        try:
                                            self.compasswidget.update_compass(float(json_data["compass"]))
                                            self.dataconfirm["compass"] = True
                                        except (ValueError, TypeError):
                                            print("Invalid compass value:", json_data["compass"])
                                    else:
                                        print("Compass data is None or compass widget not set")
                                else:
                                    print("Utils data format incorrect")
                            else:
                                print("Utils data doesn't start with #")
                        else:
                            print("Missing required fields in JSON data")
                            
                    except json.JSONDecodeError:
                        # Fallback to old format
                        if(compassdata.startswith("#")):
                            parts = compassdata[1:].split("=")
                            print(parts)
                            if(len(parts)==5):
                                self.update_utils={
                                    "armstate":parts[0],
                                    "batvoltage":parts[1],
                                    "jetsonvoltage":parts[2],
                                    "gps":parts[4],
                                    "compass":parts[3]
                                }
                                

                                if(parts[3]!="None" and self.compasswidget is not None):
                                    self.compasswidget.update_compass(float(parts[3]))
                                    self.dataconfirm["compass"] = True
                            else:
                                print("utils data missing ")
                # print(f"Received message: {data.decode()} from {addr}")
            except Exception as e:
                print(f"Error receiving UDP packet: {e}")

    def setcompasswidget(self,compasswidget=None):
        self.compasswidget = compasswidget
        # if(self.compasswidget!=None):
        #     Clock.schedule_interval(self.compasswidget.update_angle, 1)

# root.mainloop()
