import cv2

# Initialize the video capture object with the first camera (index 0)
cap = cv2.VideoCapture(0)

# Check if the camera is opened successfully
if not cap.isOpened():
    print("Error: Could not open camera.")
    exit()

# Loop to capture frames from the camera
while True:
    # Capture frame-by-frame
    ret, frame = cap.read()

    # Check if the frame is valid
    if not ret:
        print("Error: Could not receive frame.")
        break

    # Display the frame
    cv2.imshow('Camera', frame)

    # Break the loop if 'q' is pressed
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Release the video capture object and close all windows
cap.release()
cv2.destroyAllWindows()
