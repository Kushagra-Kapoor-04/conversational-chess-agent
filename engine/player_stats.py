"""
Player Skill Modeling Module

Persistent tracking of human player performance across games.
Tracks move quality, evaluation loss, phase-wise performance, and style indicators.
Data is stored and updated incrementally using JSON.
"""

import json
import os
from datetime import datetime
from typing import Dict, Optional, Any
from dataclasses import dataclass, field, asdict
from pathlib import Path

from .game_state import MoveQuality, GamePhase


@dataclass
class MoveQualityStats:
    """Statistics for move quality classification."""
    total_moves: int = 0
    blunders: int = 0
    mistakes: int = 0
    inaccuracies: int = 0
    good_moves: int = 0
    excellent_moves: int = 0
    book_moves: int = 0
    
    def record(self, quality: MoveQuality) -> None:
        """Record a move with the given quality."""
        self.total_moves += 1
        if quality == MoveQuality.BLUNDER:
            self.blunders += 1
        elif quality == MoveQuality.MISTAKE:
            self.mistakes += 1
        elif quality == MoveQuality.INACCURACY:
            self.inaccuracies += 1
        elif quality == MoveQuality.GOOD:
            self.good_moves += 1
        elif quality == MoveQuality.EXCELLENT:
            self.excellent_moves += 1
        elif quality == MoveQuality.BOOK:
            self.book_moves += 1
    
    @property
    def accuracy(self) -> float:
        """Calculate accuracy as percentage of good/excellent/book moves."""
        if self.total_moves == 0:
            return 0.0
        good = self.good_moves + self.excellent_moves + self.book_moves
        return (good / self.total_moves) * 100
    
    @property
    def error_rate(self) -> float:
        """Calculate error rate (blunders + mistakes + inaccuracies)."""
        if self.total_moves == 0:
            return 0.0
        errors = self.blunders + self.mistakes + self.inaccuracies
        return (errors / self.total_moves) * 100
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "MoveQualityStats":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class EvalLossStats:
    """Statistics for evaluation loss tracking."""
    total_centipawn_loss: float = 0.0
    move_count: int = 0
    
    def record(self, centipawn_loss: float) -> None:
        """Record centipawn loss for a move."""
        # Only count positive losses (negative would be improvement)
        if centipawn_loss > 0:
            self.total_centipawn_loss += centipawn_loss
        self.move_count += 1
    
    @property
    def average_loss(self) -> float:
        """Calculate average centipawn loss per move."""
        if self.move_count == 0:
            return 0.0
        return self.total_centipawn_loss / self.move_count
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "total_centipawn_loss": self.total_centipawn_loss,
            "move_count": self.move_count,
            "average_loss": self.average_loss
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "EvalLossStats":
        """Create from dictionary."""
        return cls(
            total_centipawn_loss=data.get("total_centipawn_loss", 0.0),
            move_count=data.get("move_count", 0)
        )


@dataclass
class PhaseStats:
    """Statistics for a specific game phase."""
    moves: int = 0
    total_centipawn_loss: float = 0.0
    blunders: int = 0
    mistakes: int = 0
    inaccuracies: int = 0
    good_moves: int = 0
    excellent_moves: int = 0
    
    def record(self, quality: MoveQuality, centipawn_loss: float) -> None:
        """Record a move in this phase."""
        self.moves += 1
        if centipawn_loss > 0:
            self.total_centipawn_loss += centipawn_loss
        
        if quality == MoveQuality.BLUNDER:
            self.blunders += 1
        elif quality == MoveQuality.MISTAKE:
            self.mistakes += 1
        elif quality == MoveQuality.INACCURACY:
            self.inaccuracies += 1
        elif quality == MoveQuality.GOOD:
            self.good_moves += 1
        elif quality == MoveQuality.EXCELLENT:
            self.excellent_moves += 1
    
    @property
    def average_loss(self) -> float:
        """Average centipawn loss in this phase."""
        if self.moves == 0:
            return 0.0
        return self.total_centipawn_loss / self.moves
    
    @property
    def accuracy(self) -> float:
        """Accuracy percentage in this phase."""
        if self.moves == 0:
            return 0.0
        good = self.good_moves + self.excellent_moves
        return (good / self.moves) * 100
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "moves": self.moves,
            "total_centipawn_loss": self.total_centipawn_loss,
            "average_loss": self.average_loss,
            "accuracy": self.accuracy,
            "blunders": self.blunders,
            "mistakes": self.mistakes,
            "inaccuracies": self.inaccuracies,
            "good_moves": self.good_moves,
            "excellent_moves": self.excellent_moves
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "PhaseStats":
        """Create from dictionary."""
        return cls(
            moves=data.get("moves", 0),
            total_centipawn_loss=data.get("total_centipawn_loss", 0.0),
            blunders=data.get("blunders", 0),
            mistakes=data.get("mistakes", 0),
            inaccuracies=data.get("inaccuracies", 0),
            good_moves=data.get("good_moves", 0),
            excellent_moves=data.get("excellent_moves", 0)
        )


@dataclass
class StyleIndicators:
    """
    Player style indicators derived from gameplay patterns.
    Values range from 0.0 to 1.0.
    """
    # Aggression: tendency to attack, push pawns, create threats
    total_attacking_moves: int = 0
    total_moves_evaluated: int = 0
    
    # Risk tolerance: willingness to sacrifice material or enter complications
    risky_moves: int = 0
    safe_moves: int = 0
    
    # Piece activity: preference for active piece play
    active_piece_moves: int = 0
    passive_moves: int = 0
    
    def record_move(
        self,
        is_attacking: bool = False,
        is_risky: bool = False,
        is_active: bool = False
    ) -> None:
        """Record style indicators for a move."""
        self.total_moves_evaluated += 1
        
        if is_attacking:
            self.total_attacking_moves += 1
        
        if is_risky:
            self.risky_moves += 1
        else:
            self.safe_moves += 1
        
        if is_active:
            self.active_piece_moves += 1
        else:
            self.passive_moves += 1
    
    @property
    def aggression(self) -> float:
        """Aggression score (0.0 - 1.0)."""
        if self.total_moves_evaluated == 0:
            return 0.5
        return self.total_attacking_moves / self.total_moves_evaluated
    
    @property
    def risk_tolerance(self) -> float:
        """Risk tolerance score (0.0 - 1.0)."""
        total = self.risky_moves + self.safe_moves
        if total == 0:
            return 0.5
        return self.risky_moves / total
    
    @property
    def piece_activity(self) -> float:
        """Piece activity score (0.0 - 1.0)."""
        total = self.active_piece_moves + self.passive_moves
        if total == 0:
            return 0.5
        return self.active_piece_moves / total
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "aggression": round(self.aggression, 3),
            "risk_tolerance": round(self.risk_tolerance, 3),
            "piece_activity": round(self.piece_activity, 3),
            "raw_data": {
                "total_attacking_moves": self.total_attacking_moves,
                "total_moves_evaluated": self.total_moves_evaluated,
                "risky_moves": self.risky_moves,
                "safe_moves": self.safe_moves,
                "active_piece_moves": self.active_piece_moves,
                "passive_moves": self.passive_moves
            }
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "StyleIndicators":
        """Create from dictionary."""
        raw = data.get("raw_data", {})
        return cls(
            total_attacking_moves=raw.get("total_attacking_moves", 0),
            total_moves_evaluated=raw.get("total_moves_evaluated", 0),
            risky_moves=raw.get("risky_moves", 0),
            safe_moves=raw.get("safe_moves", 0),
            active_piece_moves=raw.get("active_piece_moves", 0),
            passive_moves=raw.get("passive_moves", 0)
        )


class PlayerStats:
    """
    Persistent player skill tracking across games.
    
    Tracks move quality, evaluation loss, phase-wise performance,
    and style indicators. Data is stored in JSON format.
    
    Example:
        >>> stats = PlayerStats(player_id="player1")
        >>> stats.record_move(MoveQuality.GOOD, 15.0, GamePhase.OPENING)
        >>> stats.record_game_result("win")
        >>> stats.save("player_stats.json")
    """
    
    DEFAULT_STATS_DIR = ".player_stats"
    
    def __init__(self, player_id: str = "default"):
        """
        Initialize player stats.
        
        Args:
            player_id: Unique identifier for the player.
        """
        self.player_id = player_id
        self.games_played = 0
        self.wins = 0
        self.losses = 0
        self.draws = 0
        
        self.move_quality = MoveQualityStats()
        self.eval_loss = EvalLossStats()
        
        self.phase_stats = {
            "opening": PhaseStats(),
            "middlegame": PhaseStats(),
            "endgame": PhaseStats()
        }
        
        self.style = StyleIndicators()
        
        self.created_at = datetime.now().isoformat()
        self.last_updated = self.created_at
    
    def record_move(
        self,
        quality: MoveQuality,
        centipawn_loss: float,
        phase: GamePhase,
        is_attacking: bool = False,
        is_risky: bool = False,
        is_active: bool = False
    ) -> None:
        """
        Record statistics for a single move.
        
        Args:
            quality: The quality classification of the move.
            centipawn_loss: Centipawn loss for this move.
            phase: The game phase (opening/middlegame/endgame).
            is_attacking: Whether the move is an attacking move.
            is_risky: Whether the move involves risk/sacrifice.
            is_active: Whether the move improves piece activity.
        """
        # Update overall move quality
        self.move_quality.record(quality)
        
        # Update evaluation loss
        self.eval_loss.record(centipawn_loss)
        
        # Update phase-specific stats
        phase_key = phase.value if isinstance(phase, GamePhase) else phase
        if phase_key in self.phase_stats:
            self.phase_stats[phase_key].record(quality, centipawn_loss)
        
        # Update style indicators
        self.style.record_move(is_attacking, is_risky, is_active)
        
        # Update timestamp
        self.last_updated = datetime.now().isoformat()
    
    def record_game_result(self, result: str) -> None:
        """
        Record the result of a game.
        
        Args:
            result: "win", "loss", or "draw"
        """
        self.games_played += 1
        result_lower = result.lower()
        
        if result_lower == "win":
            self.wins += 1
        elif result_lower == "loss":
            self.losses += 1
        elif result_lower == "draw":
            self.draws += 1
        
        self.last_updated = datetime.now().isoformat()
    
    def get_accuracy(self) -> float:
        """Get overall move accuracy percentage."""
        return self.move_quality.accuracy
    
    def get_phase_accuracy(self, phase: str) -> float:
        """Get accuracy for a specific phase."""
        if phase in self.phase_stats:
            return self.phase_stats[phase].accuracy
        return 0.0
    
    def get_win_rate(self) -> float:
        """Get win rate as percentage."""
        if self.games_played == 0:
            return 0.0
        return (self.wins / self.games_played) * 100
    
    def get_style_profile(self) -> Dict[str, float]:
        """Get player style indicators."""
        return {
            "aggression": self.style.aggression,
            "risk_tolerance": self.style.risk_tolerance,
            "piece_activity": self.style.piece_activity
        }
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of player statistics."""
        return {
            "player_id": self.player_id,
            "games_played": self.games_played,
            "win_rate": round(self.get_win_rate(), 1),
            "overall_accuracy": round(self.get_accuracy(), 1),
            "average_eval_loss": round(self.eval_loss.average_loss, 1),
            "strongest_phase": self._get_strongest_phase(),
            "weakest_phase": self._get_weakest_phase(),
            "style": self.get_style_profile()
        }
    
    def _get_strongest_phase(self) -> str:
        """Get the phase with highest accuracy."""
        best_phase = "opening"
        best_accuracy = 0.0
        
        for phase, stats in self.phase_stats.items():
            if stats.moves > 0 and stats.accuracy > best_accuracy:
                best_accuracy = stats.accuracy
                best_phase = phase
        
        return best_phase
    
    def _get_weakest_phase(self) -> str:
        """Get the phase with lowest accuracy."""
        worst_phase = "opening"
        worst_accuracy = 100.0
        
        for phase, stats in self.phase_stats.items():
            if stats.moves > 0 and stats.accuracy < worst_accuracy:
                worst_accuracy = stats.accuracy
                worst_phase = phase
        
        return worst_phase
    
    def reset(self) -> None:
        """Reset all statistics to zero."""
        self.__init__(player_id=self.player_id)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "player_id": self.player_id,
            "games_played": self.games_played,
            "wins": self.wins,
            "losses": self.losses,
            "draws": self.draws,
            "move_quality": self.move_quality.to_dict(),
            "eval_loss": self.eval_loss.to_dict(),
            "phase_stats": {
                phase: stats.to_dict() 
                for phase, stats in self.phase_stats.items()
            },
            "style": self.style.to_dict(),
            "created_at": self.created_at,
            "last_updated": self.last_updated
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlayerStats":
        """Create PlayerStats from dictionary."""
        stats = cls(player_id=data.get("player_id", "default"))
        
        stats.games_played = data.get("games_played", 0)
        stats.wins = data.get("wins", 0)
        stats.losses = data.get("losses", 0)
        stats.draws = data.get("draws", 0)
        
        if "move_quality" in data:
            stats.move_quality = MoveQualityStats.from_dict(data["move_quality"])
        
        if "eval_loss" in data:
            stats.eval_loss = EvalLossStats.from_dict(data["eval_loss"])
        
        if "phase_stats" in data:
            for phase, phase_data in data["phase_stats"].items():
                if phase in stats.phase_stats:
                    stats.phase_stats[phase] = PhaseStats.from_dict(phase_data)
        
        if "style" in data:
            stats.style = StyleIndicators.from_dict(data["style"])
        
        stats.created_at = data.get("created_at", stats.created_at)
        stats.last_updated = data.get("last_updated", stats.last_updated)
        
        return stats
    
    def save(self, path: Optional[str] = None) -> str:
        """
        Save statistics to a JSON file.
        
        Args:
            path: Path to save the file. If None, uses default location.
        
        Returns:
            The path where the file was saved.
        """
        if path is None:
            # Create default directory if needed
            stats_dir = Path(self.DEFAULT_STATS_DIR)
            stats_dir.mkdir(exist_ok=True)
            path = str(stats_dir / f"{self.player_id}.json")
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        
        return path
    
    @classmethod
    def load(cls, path: str) -> "PlayerStats":
        """
        Load statistics from a JSON file.
        
        Args:
            path: Path to the JSON file.
        
        Returns:
            PlayerStats instance with loaded data.
        
        Raises:
            FileNotFoundError: If the file doesn't exist.
        """
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls.from_dict(data)
    
    @classmethod
    def load_or_create(cls, player_id: str, stats_dir: Optional[str] = None) -> "PlayerStats":
        """
        Load existing stats or create new ones if not found.
        
        Args:
            player_id: The player identifier.
            stats_dir: Directory for stats files. Uses default if None.
        
        Returns:
            PlayerStats instance (loaded or new).
        """
        if stats_dir is None:
            stats_dir = cls.DEFAULT_STATS_DIR
        
        path = Path(stats_dir) / f"{player_id}.json"
        
        if path.exists():
            return cls.load(str(path))
        else:
            return cls(player_id=player_id)
