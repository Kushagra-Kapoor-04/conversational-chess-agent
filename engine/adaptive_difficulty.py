"""
Adaptive Difficulty Module

Rule-based dynamic adjustment of chess engine playing strength.
Uses player skill metrics and recent move quality to control:
- Search depth
- Move selection randomness
- Skill level (Stockfish's built-in limiter)

Ensures gradual, bounded difficulty changes without emotion detection.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum

from .game_state import MoveQuality
from .player_stats import PlayerStats


class DifficultyTrend(Enum):
    """Direction of difficulty adjustment."""
    INCREASING = "increasing"
    DECREASING = "decreasing"
    STABLE = "stable"


@dataclass
class EngineParams:
    """Parameters to control engine playing strength."""
    depth: int = 10
    skill_level: int = 10  # Stockfish's UCI_LimitStrength (0-20)
    move_randomness: float = 0.0  # 0.0 = best move, 1.0 = random among top moves
    time_limit: Optional[float] = None  # Optional time limit in seconds
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "depth": self.depth,
            "skill_level": self.skill_level,
            "move_randomness": self.move_randomness,
            "time_limit": self.time_limit
        }


@dataclass
class RecentPerformance:
    """Tracks recent move quality for short-term adjustments."""
    window_size: int = 10
    moves: List[MoveQuality] = field(default_factory=list)
    
    def record(self, quality: MoveQuality) -> None:
        """Record a move quality."""
        self.moves.append(quality)
        if len(self.moves) > self.window_size:
            self.moves.pop(0)
    
    @property
    def blunder_rate(self) -> float:
        """Recent blunder rate (0.0 - 1.0)."""
        if not self.moves:
            return 0.0
        blunders = sum(1 for m in self.moves if m == MoveQuality.BLUNDER)
        return blunders / len(self.moves)
    
    @property
    def excellent_rate(self) -> float:
        """Recent excellent move rate (0.0 - 1.0)."""
        if not self.moves:
            return 0.0
        excellent = sum(1 for m in self.moves if m == MoveQuality.EXCELLENT)
        return excellent / len(self.moves)
    
    @property
    def accuracy(self) -> float:
        """Recent accuracy (good + excellent moves)."""
        if not self.moves:
            return 0.5
        good = sum(1 for m in self.moves 
                   if m in (MoveQuality.GOOD, MoveQuality.EXCELLENT, MoveQuality.BOOK))
        return good / len(self.moves)
    
    def clear(self) -> None:
        """Clear recent moves."""
        self.moves.clear()


class AdaptiveDifficulty:
    """
    Rule-based adaptive difficulty controller for chess engine.
    
    Dynamically adjusts engine strength based on:
    - Player's historical skill metrics (from PlayerStats)
    - Recent move quality in current game
    - Win/loss streaks
    
    Ensures gradual changes with configurable bounds.
    
    Example:
        >>> stats = PlayerStats.load_or_create("player1")
        >>> difficulty = AdaptiveDifficulty(stats)
        >>> params = difficulty.get_engine_params()
        >>> ai_move = engine.get_ai_move(depth=params.depth)
    """
    
    # Difficulty level bounds
    MIN_LEVEL = 1
    MAX_LEVEL = 20
    DEFAULT_LEVEL = 10
    
    # Maximum change per adjustment
    MAX_CHANGE_PER_GAME = 2
    MAX_CHANGE_PER_MOVE = 0.5
    
    # Smoothing factor for exponential moving average (0-1, higher = more responsive)
    SMOOTHING_FACTOR = 0.3
    
    def __init__(
        self,
        player_stats: Optional[PlayerStats] = None,
        player_profile: Optional['PlayerProfile'] = None,
        initial_level: Optional[float] = None,
        min_level: int = MIN_LEVEL,
        max_level: int = MAX_LEVEL
    ):
        """
        Initialize adaptive difficulty controller.
        
        Args:
            player_stats: Optional PlayerStats for skill-based initialization (legacy).
            player_profile: Optional PlayerProfile for long-term skill initialization (preferred).
            initial_level: Starting difficulty level (1-20). Auto-calculated if None.
            min_level: Minimum allowed difficulty.
            max_level: Maximum allowed difficulty.
        """
        self._player_stats = player_stats
        self._player_profile = player_profile
        self._min_level = max(self.MIN_LEVEL, min_level)
        self._max_level = min(self.MAX_LEVEL, max_level)
        
        # Current difficulty (float for smooth transitions)
        if initial_level is not None:
            self._current_level = float(initial_level)
        elif player_profile and player_profile.rating:
            self._current_level = self._calculate_from_rating(player_profile.rating)
        elif player_stats and player_stats.games_played > 0:
            self._current_level = self._calculate_initial_level(player_stats)
        else:
            self._current_level = float(self.DEFAULT_LEVEL)
        
        # Clamp to bounds
        self._current_level = self._clamp(self._current_level)
        
        # Track recent performance for within-game adjustments
        self._recent_performance = RecentPerformance()
        
        # Track streaks
        self._consecutive_wins = 0
        self._consecutive_losses = 0
        
        # Level at start of current game (for bounding changes)
        self._game_start_level = self._current_level
        
        # Track adjustment trend
        self._trend = DifficultyTrend.STABLE
    
    def _clamp(self, level: float) -> float:
        """Clamp level to configured bounds."""
        return max(self._min_level, min(self._max_level, level))
    
    def _calculate_from_rating(self, rating: float) -> float:
        """Calculate difficulty level (1-20) from rating (100-3000)."""
        # Map 100-3000 Elo to 1-20 levels roughly
        # 400 = Level 1
        # 1000 = Level 5
        # 1500 = Level 10
        # 2000 = Level 15
        # 2500+ = Level 20
        
        if rating <= 400:
            return 1.0
        
        # Linear scale roughly
        level = (rating - 400) / 110 + 1
        return self._clamp(level)
    
    def _calculate_initial_level(self, stats: PlayerStats) -> float:
        """Calculate initial difficulty from player stats."""
        # Base level from accuracy (0-100% maps to levels 5-15)
        accuracy = stats.get_accuracy()
        accuracy_component = 5 + (accuracy / 100) * 10
        
        # Adjust for win rate
        win_rate = stats.get_win_rate()
        win_component = (win_rate - 50) / 50 * 3  # -3 to +3
        
        # Adjust for average eval loss (lower is better)
        avg_loss = stats.eval_loss.average_loss
        if avg_loss < 20:
            loss_component = 2  # Very accurate player
        elif avg_loss < 50:
            loss_component = 1
        elif avg_loss > 100:
            loss_component = -2  # Makes many errors
        elif avg_loss > 70:
            loss_component = -1
        else:
            loss_component = 0
        
        initial = accuracy_component + win_component + loss_component
        return self._clamp(initial)
    
    def record_move(self, quality: MoveQuality) -> None:
        """
        Record a player move for real-time difficulty adjustment.
        
        Args:
            quality: The quality classification of the player's move.
        """
        self._recent_performance.record(quality)
        
        # Calculate adjustment based on recent performance
        adjustment = self._calculate_move_adjustment(quality)
        
        # Apply with smoothing
        new_level = self._current_level + adjustment * self.SMOOTHING_FACTOR
        
        # Bound change relative to game start
        max_change = self.MAX_CHANGE_PER_GAME
        new_level = max(self._game_start_level - max_change,
                       min(self._game_start_level + max_change, new_level))
        
        # Clamp to global bounds
        self._current_level = self._clamp(new_level)
        
        # Update trend
        if adjustment > 0.1:
            self._trend = DifficultyTrend.INCREASING
        elif adjustment < -0.1:
            self._trend = DifficultyTrend.DECREASING
        else:
            self._trend = DifficultyTrend.STABLE
    
    def _calculate_move_adjustment(self, quality: MoveQuality) -> float:
        """Calculate difficulty adjustment for a single move."""
        # Base adjustment by move quality
        quality_adjustments = {
            MoveQuality.BLUNDER: -0.5,
            MoveQuality.MISTAKE: -0.3,
            MoveQuality.INACCURACY: -0.1,
            MoveQuality.GOOD: 0.1,
            MoveQuality.EXCELLENT: 0.3,
            MoveQuality.BOOK: 0.2,
        }
        base = quality_adjustments.get(quality, 0.0)
        
        # Amplify if there's a pattern
        if quality == MoveQuality.BLUNDER and self._recent_performance.blunder_rate > 0.3:
            base -= 0.3  # Player is struggling
        elif quality == MoveQuality.EXCELLENT and self._recent_performance.excellent_rate > 0.3:
            base += 0.3  # Player is dominating
        
        # Clamp individual move adjustment
        return max(-self.MAX_CHANGE_PER_MOVE, min(self.MAX_CHANGE_PER_MOVE, base))
    
    def adjust_for_game_result(self, result: str) -> None:
        """
        Adjust difficulty after a game ends.
        
        Args:
            result: "win", "loss", or "draw"
        """
        result_lower = result.lower()
        
        # Update streaks
        if result_lower == "win":
            self._consecutive_wins += 1
            self._consecutive_losses = 0
        elif result_lower == "loss":
            self._consecutive_losses += 1
            self._consecutive_wins = 0
        else:  # draw
            self._consecutive_wins = 0
            self._consecutive_losses = 0
        
        # Calculate adjustment
        adjustment = 0.0
        
        if result_lower == "win":
            # Increase difficulty on win
            adjustment = 1.0
            # Extra increase for win streak
            if self._consecutive_wins >= 3:
                adjustment += 0.5
            if self._consecutive_wins >= 5:
                adjustment += 0.5
        elif result_lower == "loss":
            # Decrease difficulty on loss
            adjustment = -1.0
            # Extra decrease for loss streak
            if self._consecutive_losses >= 3:
                adjustment -= 0.5
            if self._consecutive_losses >= 5:
                adjustment -= 0.5
        else:  # draw
            # Slight adjustment based on trend during game
            if self._trend == DifficultyTrend.INCREASING:
                adjustment = 0.3
            elif self._trend == DifficultyTrend.DECREASING:
                adjustment = -0.3
        
        # Apply adjustment with bounds
        new_level = self._current_level + adjustment
        self._current_level = self._clamp(new_level)
        
        # Reset for next game
        self._game_start_level = self._current_level
        self._recent_performance.clear()
        self._trend = DifficultyTrend.STABLE
    
    def get_difficulty_level(self) -> int:
        """Get current difficulty level (1-20)."""
        return round(self._current_level)
    
    def get_precise_level(self) -> float:
        """Get current difficulty level with decimal precision."""
        return round(self._current_level, 2)
    
    def get_engine_params(self) -> EngineParams:
        """
        Get engine parameters for current difficulty level.
        
        Returns:
            EngineParams with depth, skill_level, and move_randomness.
        """
        level = self._current_level
        
        # Map difficulty level to search depth (1-20 → 1-20)
        # Lower levels use shallower search
        depth = max(1, min(20, round(level)))
        
        # Map to Stockfish skill level (1-20 → 0-20)
        skill_level = max(0, min(20, round(level)))
        
        # Map to move randomness (higher at lower difficulties)
        # Level 1-5: high randomness (0.3-0.5)
        # Level 6-10: moderate randomness (0.1-0.3)
        # Level 11-15: low randomness (0.05-0.1)
        # Level 16-20: minimal randomness (0-0.05)
        if level <= 5:
            randomness = 0.5 - (level - 1) * 0.05
        elif level <= 10:
            randomness = 0.3 - (level - 6) * 0.04
        elif level <= 15:
            randomness = 0.1 - (level - 11) * 0.01
        else:
            randomness = 0.05 - (level - 16) * 0.01
        
        randomness = max(0.0, min(1.0, randomness))
        
        return EngineParams(
            depth=depth,
            skill_level=skill_level,
            move_randomness=randomness
        )
    
    def set_difficulty_bounds(self, min_level: int, max_level: int) -> None:
        """
        Set allowed difficulty range.
        
        Args:
            min_level: Minimum difficulty (1-20).
            max_level: Maximum difficulty (1-20).
        """
        self._min_level = max(self.MIN_LEVEL, min(min_level, max_level))
        self._max_level = min(self.MAX_LEVEL, max(min_level, max_level))
        self._current_level = self._clamp(self._current_level)
    
    def set_level(self, level: float) -> None:
        """
        Manually set difficulty level.
        
        Args:
            level: Difficulty level (1-20).
        """
        self._current_level = self._clamp(float(level))
        self._game_start_level = self._current_level
    
    def reset(self) -> None:
        """Reset to default state."""
        self._current_level = float(self.DEFAULT_LEVEL)
        self._game_start_level = self._current_level
        self._recent_performance.clear()
        self._consecutive_wins = 0
        self._consecutive_losses = 0
        self._trend = DifficultyTrend.STABLE
    
    def get_status(self) -> Dict[str, Any]:
        """Get current difficulty status."""
        return {
            "level": self.get_difficulty_level(),
            "precise_level": self.get_precise_level(),
            "trend": self._trend.value,
            "consecutive_wins": self._consecutive_wins,
            "consecutive_losses": self._consecutive_losses,
            "recent_accuracy": round(self._recent_performance.accuracy * 100, 1),
            "bounds": {"min": self._min_level, "max": self._max_level}
        }
