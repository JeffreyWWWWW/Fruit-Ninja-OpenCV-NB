import cv2
import mediapipe as mp
import numpy as np
from collections import deque

class HandTracker:
    def __init__(self):
        self.mp_hands = mp.solutions.hands
        self.mp_draw = mp.solutions.drawing_utils
        self.hands = self.mp_hands.Hands(
            max_num_hands=1,
            min_detection_confidence=0.6,  # Reduced for better responsiveness
            min_tracking_confidence=0.6,
            model_complexity=0
        )
        self.points_history = deque(maxlen=8)  # Reduced for faster response
        self.prev_point = None
        self.lost_tracking_frames = 0
        self.max_lost_frames = 5  # Reduced for quicker recovery
        
        # Movement prediction
        self.velocity = (0, 0)
        self.smooth_factor = 0.5  # Increased for more direct movement
        self.prediction_decay = 0.8  # Slower velocity decay
        
    def process_frame(self, frame):
        # Resize frame for faster processing
        small_frame = cv2.resize(frame, (320, 240))
        rgb_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
        results = self.hands.process(rgb_frame)
        
        # Scale factor for converting coordinates back to original size
        height, width = frame.shape[:2]
        scale_x = width / 320
        scale_y = height / 240
        
        return results, (scale_x, scale_y)
    
    def draw_tracking_info(self, frame, hand_pos, velocity):
        # Create a copy of the frame to avoid modifying the original
        overlay = frame.copy()
        
        # Add semi-transparent overlay for better visibility
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
        
        # Draw tracking boundary
        margin = 50
        cv2.rectangle(frame, 
                     (margin, margin), 
                     (frame.shape[1]-margin, frame.shape[0]-margin), 
                     (0, 255, 0), 2)
        
        if hand_pos is not None and hand_pos[0] is not None and hand_pos[1] is not None:
            x, y = int(hand_pos[0] * frame.shape[1]), int(hand_pos[1] * frame.shape[0])
            
            # Draw hand position with dynamic size based on velocity
            if isinstance(velocity, tuple) and len(velocity) == 2:
                speed = np.sqrt(velocity[0]**2 + velocity[1]**2) * 1000
                radius = int(10 + min(speed * 0.1, 10))  # Dynamic circle size
                
                # Draw outer glow
                cv2.circle(frame, (x, y), radius + 4, (255, 255, 255), 2)
                # Draw inner circle
                cv2.circle(frame, (x, y), radius, (0, 255, 0), -1)
                
                # Draw movement vector
                if abs(velocity[0]) > 0.001 or abs(velocity[1]) > 0.001:
                    end_x = x + int(velocity[0] * 100)  # Increased vector length
                    end_y = y + int(velocity[1] * 100)
                    # Draw arrow with glow effect
                    cv2.arrowedLine(frame, (x, y), (end_x, end_y), (255, 255, 255), 4)
                    cv2.arrowedLine(frame, (x, y), (end_x, end_y), (0, 255, 0), 2)
            
            # Draw tracking area guides
            guide_color = (0, 255, 0)
            cv2.line(frame, (x, margin), (x, frame.shape[0]-margin), guide_color, 1)
            cv2.line(frame, (margin, y), (frame.shape[1]-margin, y), guide_color, 1)
        else:
            # Draw "No Hand Detected" message
            text = "No Hand Detected"
            font = cv2.FONT_HERSHEY_SIMPLEX
            text_size = cv2.getTextSize(text, font, 1, 2)[0]
            text_x = (frame.shape[1] - text_size[0]) // 2
            text_y = frame.shape[0] // 2
            
            # Draw text with glow effect
            cv2.putText(frame, text, (text_x+2, text_y+2), font, 1, (0, 0, 0), 3)
            cv2.putText(frame, text, (text_x, text_y), font, 1, (0, 0, 255), 2)
        
        return frame
    
    def get_hand_position(self, frame):
        results, scale = self.process_frame(frame)
        
        if results.multi_hand_landmarks:
            self.lost_tracking_frames = 0
            hand_landmarks = results.multi_hand_landmarks[0]
            
            # Use palm center for more stable tracking
            palm_points = [0, 5, 9, 13, 17]  # Wrist and finger base points
            x = sum(hand_landmarks.landmark[i].x for i in palm_points) / len(palm_points)
            y = sum(hand_landmarks.landmark[i].y for i in palm_points) / len(palm_points)
            
            # Store point in history
            self.points_history.append((x, y))
            
            # Calculate smooth position using weighted average
            if len(self.points_history) >= 3:
                weights = np.linspace(1, 3, len(self.points_history))
                weights = weights / weights.sum()
                
                smooth_x = sum(p[0] * w for p, w in zip(self.points_history, weights))
                smooth_y = sum(p[1] * w for p, w in zip(self.points_history, weights))
                current_point = (smooth_x, smooth_y)
            else:
                current_point = (x, y)
            
            # Calculate velocity with smoothing
            if self.prev_point:
                dx = (current_point[0] - self.prev_point[0]) * 1.5  # Increased movement range
                dy = (current_point[1] - self.prev_point[1]) * 1.5
                
                # Smooth velocity
                self.velocity = (
                    self.velocity[0] * (1 - self.smooth_factor) + dx * self.smooth_factor,
                    self.velocity[1] * (1 - self.smooth_factor) + dy * self.smooth_factor
                )
                velocity = np.sqrt(self.velocity[0]**2 + self.velocity[1]**2) * 1000
            else:
                velocity = 0
            
            self.prev_point = current_point
            return current_point[0], current_point[1], velocity, self.velocity
        
        # Handle lost tracking with motion prediction
        if self.prev_point and self.lost_tracking_frames < self.max_lost_frames:
            self.lost_tracking_frames += 1
            # Predict next position using last known velocity
            predicted_x = self.prev_point[0] + self.velocity[0]
            predicted_y = self.prev_point[1] + self.velocity[1]
            # Decay velocity during prediction
            self.velocity = (
                self.velocity[0] * self.prediction_decay,
                self.velocity[1] * self.prediction_decay
            )
            return predicted_x, predicted_y, 0, self.velocity
        
        self.prev_point = None
        self.points_history.clear()
        self.velocity = (0, 0)
        return None, None, 0, (0, 0)
    
    def __del__(self):
        self.hands.close()