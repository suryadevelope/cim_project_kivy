# import cv2

# # Replace with your RTSP URL
# rtsp_url = "rtsp://192.168.42.81:8554/main.264"

# cap = cv2.VideoCapture(rtsp_url)

# if not cap.isOpened():
#     print("Error: Cannot open RTSP stream")
#     exit()

# while True:
#     ret, frame = cap.read()
#     if not ret:
#         print("Failed to grab frame")
#         break

#     cv2.imshow("RTSP Stream", frame)

#     # Press 'q' to quit
#     if cv2.waitKey(1) & 0xFF == ord('q'):
#         break

# cap.release()
# cv2.destroyAllWindows()












