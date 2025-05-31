# Import required libraries
import cv2                    # OpenCV for camera access and image processing
import mediapipe as mp        # MediaPipe for real-time hand tracking
import time                   # Time module for tracking delays
import pyrebase               # pyrebase4 for interacting with Firebase Realtime Database

# Firebase configuration (credentials from Firebase project)
firebase_config = {
    "apiKey": "AIzaSyBTzqsyKJAoiEac8KpHRLSkO0-uhZWnPb8",
    "authDomain": "gestomateha.firebaseapp.com",
    "databaseURL": "https://gestomateha-default-rtdb.firebaseio.com",
    "projectId": "gestomateha",
    "storageBucket": "gestomateha.appspot.com",
    "messagingSenderId": "1234567890",
    "appId": "1:1234567890:web:abcdef123456"
}

# Initialize Firebase app and reference to the database
firebase = pyrebase.initialize_app(firebase_config)
db = firebase.database()

# Initialize MediaPipe Hands model
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    max_num_hands=2,                 # Detect up to 2 hands
    model_complexity=1,              # Use a more accurate model
    min_detection_confidence=0.8,    # Confidence threshold for detection
    min_tracking_confidence=0.8      # Confidence threshold for tracking
)
mp_draw = mp.solutions.drawing_utils  # Utility to draw hand landmarks on image

# Function to get label (Left or Right) of detected hand
def get_label(handedness):
    return handedness.classification[0].label  # Returns "Left" or "Right"

# Function to detect finger states: 1 (open), 0 (closed)
def get_finger_states(hand, label):
    tips = [4, 8, 12, 16, 20]  # Index of fingertips in MediaPipe landmarks
    fingers = []

    # Thumb logic depends on hand side (left/right)
    if label == "Right":
        fingers.append(1 if hand.landmark[4].x < hand.landmark[3].x else 0)
    else:  # Left hand
        fingers.append(1 if hand.landmark[4].x > hand.landmark[3].x else 0)

    # Other fingers (Index, Middle, Ring, Pinky)
    for i in range(1, 5):
        fingers.append(1 if hand.landmark[tips[i]].y < hand.landmark[tips[i] - 2].y else 0)

    return fingers  # Returns list like [1, 1, 0, 0, 0]

# Function to match detected finger pattern to a gesture
def recognize_gesture(fingers):
    if fingers == [1, 0, 0, 0, 0]: return "FAN ON"
    if fingers == [0, 1, 1, 1, 1]: return "FAN OFF"
    if fingers == [0, 0, 0, 0, 0]: return "LIGHT OFF"
    if fingers == [1, 1, 1, 1, 1]: return "LIGHT ON"
    if fingers == [0, 1, 0, 0, 0]: return "FAN SPEED 1"
    if fingers == [0, 1, 1, 0, 0]: return "FAN SPEED 2"
    if fingers == [0, 1, 1, 1, 0]: return "FAN SPEED 3"
    return None  # No matching gesture

# Function to update Firebase database based on gesture
def send_to_firebase(command):
    print("Firebase Update:", command)

    if "LIGHT" in command:
        db.child("appliances").update({"light": command.split()[-1].lower()})

    elif "FAN SPEED" in command:
        db.child("appliances").update({"fan_speed": command[-1]})

    elif "FAN" in command:
        db.child("appliances").update({"fan": command.split()[-1].lower()})

# Setup for filtering out unstable gestures
last_command = None
gesture_counter = {}
stable_threshold = 3  # Number of consistent frames to confirm a gesture

# Open webcam
cap = cv2.VideoCapture(0)

while True:
    success, frame = cap.read()
    frame = cv2.flip(frame, 1)  # Flip image horizontally for natural interaction
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)  # Convert BGR to RGB for MediaPipe
    result = hands.process(rgb)  # Process the frame to detect hands

    # If hands are detected
    if result.multi_hand_landmarks and result.multi_handedness:
        for hand_landmarks, handedness in zip(result.multi_hand_landmarks, result.multi_handedness):
            label = get_label(handedness)  # Get if it's left or right hand
            fingers = get_finger_states(hand_landmarks, label)  # Detect open/closed fingers
            gesture = recognize_gesture(fingers)  # Map finger pattern to gesture

            # Draw hand landmarks on screen
            mp_draw.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

            # If gesture is recognized
            if gesture:
                # Count how many frames this gesture has been stable
                gesture_counter[gesture] = gesture_counter.get(gesture, 0) + 1

                # Trigger action only if the gesture is stable for enough frames
                if gesture_counter[gesture] >= stable_threshold and gesture != last_command:
                    send_to_firebase(gesture)
                    last_command = gesture
                    gesture_counter = {}  # Reset after sending

                # Display recognized gesture on screen
                cv2.putText(frame, f"{gesture}", (10, 50),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)

    # Show the result frame
    cv2.imshow("Gesture Control", frame)

    # Exit on pressing ESC key
    if cv2.waitKey(1) & 0xFF == 27:
        break

# Release resources
cap.release()
cv2.destroyAllWindows()
