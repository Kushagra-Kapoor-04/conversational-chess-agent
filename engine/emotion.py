"""
Emotion and Engagement Inference Module.

Infers player emotional state (Calm, Frustrated, Confident, Disengaged)
from in-game signals (move timing, blunders, streaks) and determines
the appropriate coaching personality.
"""

import time
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional, Deque, Dict
from collections import deque

class EmotionState(Enum):
    """Inferred emotional state of the player."""
    CALM = "calm"                 # Default state, balanced
    FRUSTRATED = "frustrated"     # "Tilt" - rapid blunders, quick retries
    CONFIDENT = "confident"       # "Flow" - winning streak, fast good moves
    DISENGAGED = "disengaged"     # Long delays, lack of interaction

class Personality(Enum):
    """Coaching personality based on player state."""
    SUPPORTIVE = "supportive"     # For Calm state (Default)
    EMPATHETIC = "empathetic"     # For Frustrated state (De-escalation)
    ENTHUSIASTIC = "enthusiastic" # For Confident state (Hype)
    ENGAGING = "engaging"         # For Disengaged state (Re-engagement)

@dataclass
class EmotionSignal:
    """A single signal event."""
    timestamp: float
    signal_type: str
    value: float

class EmotionModel:
    """
    Rule-based inference engine for player emotion.
    
    Tracks recent signals and determines the current state and
    corresponding coaching personality.
    """
    
    # Thresholds
    FAST_MOVE_THRESHOLD = 2.0  # seconds
    SLOW_MOVE_THRESHOLD = 30.0 # seconds
    VERY_SLOW_MOVE_THRESHOLD = 120.0 # seconds
    
    TILT_BLUNDER_STREAK = 2
    FLOW_WIN_STREAK = 2
    
    def __init__(self):
        """Initialize emotion model."""
        self.current_state = EmotionState.CALM
        self.current_personality = Personality.SUPPORTIVE
        
        # History tracks
        self.recent_move_times: Deque[float] = deque(maxlen=5)
        self.recent_blunders = 0
        self.recent_wins = 0
        self.last_interaction_time = time.time()
        
        # State tracking
        self.consecutive_fast_blunders = 0
        self.consecutive_good_fast_moves = 0
    
    def record_move(self, is_blunder: bool, time_taken: float, is_good: bool = False) -> None:
        """
        Record a move for emotion inference.
        
        Args:
            is_blunder: Whether the move was a blunder.
            time_taken: Time taken to make the move in seconds.
            is_good: Whether the move was good/excellent.
        """
        self.last_interaction_time = time.time()
        self.recent_move_times.append(time_taken)
        
        # Tilt detection (Frustration)
        if is_blunder:
            self.recent_blunders += 1
            if time_taken < self.FAST_MOVE_THRESHOLD:
                self.consecutive_fast_blunders += 1
            else:
                self.consecutive_fast_blunders = 0
        else:
            self.recent_blunders = 0
            self.consecutive_fast_blunders = 0
            
        # Flow detection (Confidence)
        if is_good:
            if time_taken < 10.0: # reasonably fast, not necessarily blitz
                self.consecutive_good_fast_moves += 1
        else:
            self.consecutive_good_fast_moves = 0
            
        # Update state
        self._update_state(time_taken)
    
    def record_game_result(self, result: str) -> None:
        """Record game result."""
        self.last_interaction_time = time.time()
        if result == "win":
            self.recent_wins += 1
        else:
            self.recent_wins = 0
            
        self._update_state()
            
    def record_interaction(self) -> None:
        """Record generic user interaction (commands, etc)."""
        self.last_interaction_time = time.time()
        # Interaction wakes up from disengagement
        if self.current_state == EmotionState.DISENGAGED:
            self.current_state = EmotionState.CALM
            self._update_personality()

    def check_engagement(self) -> None:
        """Check for disengagement due to time."""
        if time.time() - self.last_interaction_time > self.VERY_SLOW_MOVE_THRESHOLD:
            if self.current_state != EmotionState.DISENGAGED:
                self.current_state = EmotionState.DISENGAGED
                self._update_personality()

    def _update_state(self, last_move_time: float = 0.0) -> None:
        """Update inferred state based on current signals."""
        previous_state = self.current_state
        
        # 1. Check for Disengagement (Time based)
        # Note: This is usually checked externally via check_engagement loop, 
        # but huge move times also trigger it.
        if last_move_time > self.VERY_SLOW_MOVE_THRESHOLD:
            self.current_state = EmotionState.DISENGAGED
            
        # 2. Check for Frustration (Tilt)
        # Criteria: Consecutive fast blunders OR frequent recent blunders
        elif self.consecutive_fast_blunders >= 2 or (self.recent_blunders >= 3):
            self.current_state = EmotionState.FRUSTRATED
            
        # 3. Check for Confidence (Flow)
        # Criteria: Winning streak OR streak of fast good moves
        elif self.recent_wins >= self.FLOW_WIN_STREAK or self.consecutive_good_fast_moves >= 3:
            self.current_state = EmotionState.CONFIDENT
            
        # 4. Default to Calm
        # If we were frustrated but played a decent move slowly, calm down
        elif self.current_state == EmotionState.FRUSTRATED:
             # Recovery condition: Play 1 good move or slow down significantly
             if self.recent_blunders == 0 or last_move_time > 5.0:
                 self.current_state = EmotionState.CALM
        
        elif self.current_state == EmotionState.CONFIDENT:
            # Drop confidence if we blunder
            if self.recent_blunders > 0:
                 self.current_state = EmotionState.CALM
                 
        elif self.current_state == EmotionState.DISENGAGED:
            # Wake up if we made a move
            self.current_state = EmotionState.CALM

        # If no strong signals, strictly stay CALM only if we aren't in another state
        # (This logic preserves state persistence slightly)
        
        self._update_personality()
        
    def _update_personality(self) -> None:
        """Map specific emotion state to personality."""
        mapping = {
            EmotionState.CALM: Personality.SUPPORTIVE,
            EmotionState.FRUSTRATED: Personality.EMPATHETIC,
            EmotionState.CONFIDENT: Personality.ENTHUSIASTIC,
            EmotionState.DISENGAGED: Personality.ENGAGING
        }
        self.current_personality = mapping.get(self.current_state, Personality.SUPPORTIVE)

    def get_personality(self) -> Personality:
        """Get current personality."""
        return self.current_personality
        
    def get_status(self) -> Dict[str, str]:
        """Get debug status."""
        return {
            "state": self.current_state.value,
            "personality": self.current_personality.value,
            "recent_blunders": str(self.recent_blunders),
            "fast_blunders": str(self.consecutive_fast_blunders),
            "wins": str(self.recent_wins)
        }
