import socket
import cv2
import pickle
import struct
import threading
import queue
import time

IP = "0.0.0.0"
PORT = 8000

frame_queue = queue.Queue()

def handle_client(conn, addr):
    print(f"Client connected: {addr}")
    data = b""

    while True:
        try:
            while len(data) < 8:
                packet = conn.recv(4096)
                if not packet:
                    print(f"Client {addr} disconnected")
                    return
                data += packet

            packed_size = data[:8]
            data = data[8:]
            msg_size = struct.unpack("Q", packed_size)[0]

            while len(data) < msg_size:
                data += conn.recv(4096)

            frame_data = data[:msg_size]
            data = data[msg_size:]

            cam_index, encoded_frame = pickle.loads(frame_data)
            frame = cv2.imdecode(encoded_frame, cv2.IMREAD_COLOR)

            if frame is not None:
                # Push the frame to the display queue
                frame_queue.put((cam_index, frame))

        except Exception as e:
            print(f"Error with client {addr}: {e}")
            break

    conn.close()

def display_frames():
    windows = {}

    while True:
        try:
            cam_index, frame = frame_queue.get(timeout=1)
            win_name = f"Camera {cam_index}"

            if win_name not in windows:
                cv2.namedWindow(win_name)

            cv2.imshow(win_name, frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        except queue.Empty:
            continue

    cv2.destroyAllWindows()

def start_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((IP, PORT))
    server_socket.listen(5)
    print(f"Server listening on {IP}:{PORT}")

    threading.Thread(target=display_frames, daemon=True).start()

    while True:
        conn, addr = server_socket.accept()
        t = threading.Thread(target=handle_client, args=(conn, addr))
        t.daemon = True
        t.start()

if __name__ == "__main__":
    start_server()
