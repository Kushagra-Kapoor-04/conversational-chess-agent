"""
Player Profile System

Persistent, rule-based long-term player tracking.
Aggregates performance across multiple games to track:
- Estimated rating (Elo-like)
- Recurring strengths and weaknesses
- Phase-wise skill trends
- Style tendencies

Exposes a stable profile to adaptive difficulty and coaching modules.
"""

import json
import os
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any, Set
from pathlib import Path

from .player_stats import PlayerStats, GamePhase


@dataclass
class GameSession:
    """Summary of a single game session."""
    date: str
    result: str  # "win", "loss", "draw"
    accuracy: float
    difficulty_level: int
    moves_played: int
    blunders: int
    mistakes: int
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "GameSession":
        return cls(**data)


class PlayerProfile:
    """
    Long-term player profile aggregating performance across games.
    
    Tracks estimated rating, trends, strengths, and weaknesses.
    Persists data to JSON.
    """
    
    DEFAULT_PROFILE_DIR = ".profiles"
    BASE_RATING = 1000.0
    
    # Weight of most recent game in rating update (0.0 - 1.0)
    RATING_UPDATE_WEIGHT = 0.15
    
    def __init__(self, player_id: str = "default"):
        """Initialize player profile."""
        self.player_id = player_id
        self.rating = self.BASE_RATING
        self.rating_history: List[float] = [self.BASE_RATING]
        
        # Aggregate stats
        self.stats = PlayerStats(player_id)
        self.game_history: List[GameSession] = []
        
        # Tags
        self.strengths: Set[str] = set()
        self.weaknesses: Set[str] = set()
        self.style_tags: Set[str] = set()
        
        self.created_at = datetime.now().isoformat()
        self.last_updated = self.created_at
    
    def update_after_game(
        self,
        result: str,
        accuracy: float,
        difficulty_level: int,
        moves_played: int,
        blunders: int,
        mistakes: int,
        current_game_stats: Optional[PlayerStats] = None
    ) -> None:
        """
        Update profile after a game session.
        
        Args:
            result: Game result ("win", "loss", "draw")
            accuracy: Player accuracy percentage (0-100)
            difficulty_level: Engine difficulty level (1-20)
            moves_played: Number of moves played
            blunders: Number of blunders made
            mistakes: Number of mistakes made
            current_game_stats: Detailed stats from the game (optional)
        """
        # 1. Record session
        session = GameSession(
            date=datetime.now().isoformat(),
            result=result,
            accuracy=accuracy,
            difficulty_level=difficulty_level,
            moves_played=moves_played,
            blunders=blunders,
            mistakes=mistakes
        )
        self.game_history.append(session)
        
        # 2. Update rating
        self._update_rating(result, difficulty_level, accuracy)
        
        # 3. Merge stats if provided
        if current_game_stats:
            self._merge_stats(current_game_stats)
        
        # 4. Analyze trends (strengths/weaknesses)
        self._analyze_patterns()
        
        self.last_updated = datetime.now().isoformat()
    
    def _update_rating(self, result: str, difficulty: int, accuracy: float) -> None:
        """
        Update estimated rating based on performance.
        
        Rating Logic:
        - Base performance = difficulty * 100
        - Win bonus = +200, Loss penalty = -200
        - Accuracy bonus = (accuracy - 50) * 5
        """
        # Performance calculation
        base_perf = difficulty * 100
        
        result_mod = 0
        if result == "win":
            result_mod = 200
        elif result == "loss":
            result_mod = -200
        
        accuracy_mod = (accuracy - 50) * 4
        
        performance_rating = base_perf + result_mod + accuracy_mod
        
        # Weighted update (Exponential Moving Average)
        # However, if it's the first few games, allow faster movement
        weight = self.RATING_UPDATE_WEIGHT
        if len(self.game_history) <= 5:
            weight = 0.5  # Move fast early on
        
        self.rating = (self.rating * (1 - weight)) + (performance_rating * weight)
        self.rating = max(100.0, self.rating)  # Floor at 100
        
        self.rating_history.append(round(self.rating, 1))
    
    def _merge_stats(self, game_stats: PlayerStats) -> None:
        """Merge stats from a single game into aggregate stats."""
        # Simple addition for counters
        self.stats.games_played += 1
        if game_stats.wins: self.stats.wins += 1
        if game_stats.losses: self.stats.losses += 1
        if game_stats.draws: self.stats.draws += 1
        
        # Move quality
        mq = self.stats.move_quality
        gmq = game_stats.move_quality
        mq.total_moves += gmq.total_moves
        mq.blunders += gmq.blunders
        mq.mistakes += gmq.mistakes
        mq.inaccuracies += gmq.inaccuracies
        mq.good_moves += gmq.good_moves
        mq.excellent_moves += gmq.excellent_moves
        mq.book_moves += gmq.book_moves
        
        # Eval loss (weighted average update)
        el = self.stats.eval_loss
        gel = game_stats.eval_loss
        if gel.move_count > 0:
            el.total_centipawn_loss += gel.total_centipawn_loss
            el.move_count += gel.move_count
        
        # Phases
        for phase in ["opening", "middlegame", "endgame"]:
            p = self.stats.phase_stats[phase]
            gp = game_stats.phase_stats[phase]
            p.moves += gp.moves
            p.total_centipawn_loss += gp.total_centipawn_loss
            p.blunders += gp.blunders
            p.mistakes += gp.mistakes
            p.inaccuracies += gp.inaccuracies
            p.good_moves += gp.good_moves
            p.excellent_moves += gp.excellent_moves
        
        # Style (weighted average)
        s = self.stats.style
        gs = game_stats.style
        s.total_moves_evaluated += gs.total_moves_evaluated
        s.total_attacking_moves += gs.total_attacking_moves
        s.risky_moves += gs.risky_moves
        s.safe_moves += gs.safe_moves
        s.active_piece_moves += gs.active_piece_moves
        s.passive_moves += gs.passive_moves
    
    def _analyze_patterns(self) -> None:
        """Analyze aggregated stats to identify strengths, weaknesses, and style."""
        self.strengths.clear()
        self.weaknesses.clear()
        self.style_tags.clear()
        
        # 1. Phase Analysis
        opening_acc = self.stats.get_phase_accuracy("opening")
        mid_acc = self.stats.get_phase_accuracy("middlegame")
        end_acc = self.stats.get_phase_accuracy("endgame")
        overall_acc = self.stats.get_accuracy()
        
        # Thresholds relative to overall accuracy
        if opening_acc > overall_acc + 5:
            self.strengths.add("Opening Specialist")
        elif opening_acc < overall_acc - 10:
            self.weaknesses.add("Weak Openings")
        
        if end_acc > overall_acc + 8:
            self.strengths.add("Endgame Expert")
        elif end_acc < overall_acc - 10:
            self.weaknesses.add("Poor Endgame")
        
        # 2. Tactical Analysis
        er = self.stats.move_quality.error_rate
        if er < 5.0 and self.stats.games_played > 2:
            self.strengths.add("Solid Player")
        elif er > 20.0:
            self.weaknesses.add("Prone to Blunders")
        
        # 3. Style Analysis
        style = self.stats.style
        if style.aggression > 0.6:
            self.style_tags.add("Aggressive")
        elif style.aggression < 0.3:
            self.style_tags.add("Passive")
        
        if style.risk_tolerance > 0.6:
            self.style_tags.add("Gambler")
        elif style.risk_tolerance < 0.3:
            self.style_tags.add("Conservative")
    
    def get_summary(self) -> Dict[str, Any]:
        """Get profile summary."""
        return {
            "player_id": self.player_id,
            "rating": int(self.rating),
            "games_played": len(self.game_history),
            "strengths": list(self.strengths),
            "weaknesses": list(self.weaknesses),
            "style": list(self.style_tags),
            "win_rate": round(self.stats.get_win_rate(), 1)
        }
    
    def save(self, path: Optional[str] = None) -> str:
        """Save profile to JSON."""
        if path is None:
            profile_dir = Path(self.DEFAULT_PROFILE_DIR)
            profile_dir.mkdir(exist_ok=True)
            path = str(profile_dir / f"{self.player_id}_profile.json")
        
        data = {
            "player_id": self.player_id,
            "rating": self.rating,
            "rating_history": self.rating_history,
            "stats": self.stats.to_dict(),
            "game_history": [g.to_dict() for g in self.game_history],
            "strengths": list(self.strengths),
            "weaknesses": list(self.weaknesses),
            "style_tags": list(self.style_tags),
            "created_at": self.created_at,
            "last_updated": self.last_updated
        }
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        
        return path
    
    @classmethod
    def load(cls, path: str) -> "PlayerProfile":
        """Load profile from JSON."""
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        profile = cls(data.get("player_id", "default"))
        profile.rating = data.get("rating", cls.BASE_RATING)
        profile.rating_history = data.get("rating_history", [cls.BASE_RATING])
        
        if "stats" in data:
            profile.stats = PlayerStats.from_dict(data["stats"])
        
        if "game_history" in data:
            profile.game_history = [GameSession.from_dict(g) for g in data["game_history"]]
        
        profile.strengths = set(data.get("strengths", []))
        profile.weaknesses = set(data.get("weaknesses", []))
        profile.style_tags = set(data.get("style_tags", []))
        
        profile.created_at = data.get("created_at", profile.created_at)
        profile.last_updated = data.get("last_updated", profile.last_updated)
        
        return profile

    @classmethod
    def load_or_create(cls, player_id: str) -> "PlayerProfile":
        """Load specific player profile or create new."""
        path = Path(cls.DEFAULT_PROFILE_DIR) / f"{player_id}_profile.json"
        
        if path.exists():
            return cls.load(str(path))
        return cls(player_id)
