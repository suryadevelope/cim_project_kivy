import cv2

# RTSP URLs (replace with server IP)
urls = [
    "rtsp://192.168.1.10:8554/cam0",
    "rtsp://192.168.1.10:8554/cam1",
    "rtsp://192.168.1.10:8554/cam2"
]

caps = [cv2.VideoCapture(url) for url in urls]

while True:
    for i, cap in enumerate(caps):
        ret, frame = cap.read()
        if ret:
            cv2.imshow(f"Camera {i}", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

for cap in caps:
    cap.release()
cv2.destroyAllWindows()
