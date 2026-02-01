"""
Game Supervisor Module

Central orchestration layer that coordinates the chess engine,
game analysis, player profiling, adaptive difficulty, emotion inference,
and coaching modules.
"""

import time
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass

from .chess_engine import ChessEngine
from .game_state import GameStateAnalyzer, MoveQuality, GamePhase, MoveAnalysis
from .player_stats import PlayerStats
from .player_profile import PlayerProfile
from .adaptive_difficulty import AdaptiveDifficulty
from .emotion import EmotionModel, EmotionState
from .coach import Coach, MoveContext


@dataclass
class MoveResult:
    """Result of processing a player move."""
    is_legal: bool
    move_san: str = ""
    feedback: str = ""
    error_message: str = ""
    is_game_over: bool = False
    game_result: str = ""  # "win", "loss", "draw", or ""
    move_quality: Optional[MoveQuality] = None
    
    @property
    def success(self) -> bool:
        return self.is_legal


class GameSupervisor:
    """
    Orchestrates the entire chess game lifecycle and subsystem coordination.
    
    Manages:
    - Chess Engine (Rules & AI)
    - Game State Analysis
    - Player Profiling & Stats
    - Adaptive Difficulty
    - Emotion & Engagement Inference
    - Coaching Feedback
    """
    
    def __init__(
        self,
        stockfish_path: Optional[str] = None,
        player_name: str = "Player",
        time_limit: float = 0.5,
        mock_mode: bool = False
    ):
        """
        Initialize the Game Supervisor and all subsystems.
        
        Args:
            stockfish_path: Path to Stockfish executable.
            player_name: Name of the player (for profile loading).
            time_limit: Time limit for AI moves in seconds.
            mock_mode: If True, run without Stockfish.
        """
        self.player_name = player_name
        self.ai_time_limit = time_limit
        self._mock_mode = mock_mode
        
        # 1. Core Engine
        self.engine = ChessEngine(stockfish_path, mock_mode=mock_mode)
        
        # 2. Player Profile & Stats
        self.profile = PlayerProfile.load_or_create(player_name)
        # We start with a fresh stats object for the current session
        self.current_session_stats = PlayerStats(player_name)
        
        # 3. Analysis
        if not mock_mode:
            self.analyzer = GameStateAnalyzer(engine=self.engine)
        else:
            # Fallback for mock mode (Board only)
            import chess
            self.analyzer = GameStateAnalyzer(board=self.engine._board)
        
        # 4. Adaptive Difficulty
        # Initialize with profile for long-term rating awareness
        self.difficulty = AdaptiveDifficulty(
            player_stats=self.current_session_stats,
            player_profile=self.profile
        )
        
        # 5. Emotion & Engagement
        self.emotion_model = EmotionModel()
        
        # 6. Coach
        self.coach = Coach(emotion_model=self.emotion_model)
        
        # State tracking
        self.last_move_time = time.time()
        self.move_history: list = []
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        
    def close(self):
        """Clean up resources."""
        if self.engine:
            self.engine.close()
            
    def process_player_move(self, move_str: str) -> MoveResult:
        """
        Process a player's move through the entire pipeline.
        
        Steps:
        1. Validate & Execute
        2. Analyze (Quality, Phase, etc.)
        3. Update Stats & Profile
        4. Infer Emotion
        5. Adjust Difficulty
        6. Generate Feedback
        """
        start_time = time.time()
        time_taken = start_time - self.last_move_time
        
        # 1. Validate & Execute
        if not self.engine.is_legal_move(move_str):
            return MoveResult(is_legal=False, error_message=f"Illegal move: {move_str}")
        
        # Get board state BEFORE move for analysis (if needed) or just rely on engine analysis
        # Actually analyzer needs board before move for some things, but after for others.
        # The analyzer.evaluate_move_quality usually takes the move and does the analysis.
        
        # We need to run analysis BEFORE pushing the move to the board to get the evaluation
        # But ChessEngine.evaluate_move_quality handles this internally usually?
        # Let's check GameStateAnalyzer. It expects the move to be analyzed from current position.
        
        try:
            # Analyze move quality (this does not push the move yet usually, checking impl)
            # The analyzer implementation we looked at earlier takes `move` and `board`
            # Wait, `evaluate_move_quality` in `game_state.py` usually expects the board 
            # to be in the state *before* the move.
            
            analysis = self.analyzer.evaluate_move_quality(move_str)
            
            # Execute move
            self.engine.make_move(move_str)
            
            # Check game over state immediately
            is_game_over = self.engine.is_game_over()
            game_result = ""
            if is_game_over:
                res = self.engine.get_game_result()
                if res.winner_color is True: game_result = "win" # AI Won (Player lost) - wait, engine is AI? 
                # Usuaiiy `winner_color`: True=White, False=Black.
                # If Player is White (default assumptions usually), and winner is White, Player won.
                # Let's assume Player is White for now or check turn.
                # Actually `get_game_result` usually returns standard chess outcome.
                
                # Let's refine win/loss detection logic later or assume Player=White
                # For simplicity:
                if res.winner_color == self.engine.player_color: # If we tracked player color
                     # We need to know who the player is. usually user is white vs engine.
                     pass 
                
                # Simplified result string for now
                if res.is_draw: game_result = "draw"
                elif self.engine.board.turn: # If it's White's turn now (meaning Black just moved), and game over...
                     # If checkmate and it is White's turn, White lost.
                     # But we just made a move (Player). So it's AI's turn.
                     # If game over now, Player delivered checkmate/stalemate.
                     if res.winner_color == (not self.engine.board.turn): # Winner is side that moved?
                         game_result = "win"
                     else:
                         game_result = "loss"
            
            # 2. Update Stats (Session)
            self.current_session_stats.record_move(
                quality=analysis.quality,
                centipawn_loss=analysis.centipawn_loss,
                phase=analysis.phase
            )
            
            # 3. Infer Emotion
            is_blunder = analysis.quality == MoveQuality.BLUNDER
            is_good = analysis.quality in (MoveQuality.GOOD, MoveQuality.EXCELLENT)
            self.emotion_model.record_move(is_blunder, time_taken, is_good)
            
            # 4. Adjust Difficulty
            self.difficulty.record_move(analysis.quality)
            if game_result:
                self.difficulty.adjust_for_game_result(game_result)
            
            # 5. Generate Feedback
            # Context for coach
            ctx = MoveContext(
                move=move_str,
                quality=analysis.quality,
                phase=analysis.phase,
                centipawn_loss=analysis.centipawn_loss,
                material_change=analysis.material_change,
                is_capture=self.engine.board.is_capture(self.engine.parse_move(move_str)), # Approximate check
                is_check=self.engine.board.is_check(),
                best_move=analysis.best_move_san
            )
            
            feedback = self.coach.comment_on_move(ctx)
            
            # 6. Update Profile (if game over)
            if is_game_over:
                self._finalize_game(game_result)
                summary = self.coach.game_summary(
                    result=game_result,
                    total_moves=self.current_session_stats.move_quality.total_moves,
                    blunders=self.current_session_stats.move_quality.blunders,
                    mistakes=self.current_session_stats.move_quality.mistakes,
                    excellent_moves=self.current_session_stats.move_quality.excellent_moves,
                    accuracy=self.current_session_stats.get_accuracy()
                )
                feedback += f"\n\n{summary}"
            
            self.last_move_time = time.time()
            
            return MoveResult(
                is_legal=True,
                move_san=move_str, # In reality we might want actual SAN from engine
                feedback=feedback,
                is_game_over=is_game_over,
                game_result=game_result,
                move_quality=analysis.quality
            )
            
        except Exception as e:
            # Fallback if analysis fails
            return MoveResult(is_legal=False, error_message=f"Error processing move: {str(e)}")

    def play_ai_move(self) -> str:
        """
        Generate and execute AI move using adaptive limits.
        """
        # 1. Get parameters
        params = self.difficulty.get_engine_params()
        
        # 2. Get AI move
        try:
            # We don't implement 'randomness' in engine yet directly, usually handled by 
            # 'multipv' and selecting sub-optimal, or skill level UCI options.
            # ChessEngine.get_ai_move might accept depth/time.
            # Stockfish 'Skill Level' option is handled if we passed it.
            
            # For now, we trust get_ai_move limits.
            # If we wanted to implement move_randomness (0-1), we would get top N moves
            # and pick one. But ChessEngine.get_ai_move is simple.
            # We will use the 'depth' parameter.
            
            # Apply UCI options for skill level if possible
            if self.engine._engine: # Access internal engine for options
                try:
                    self.engine._engine.configure({"Skill Level": params.skill_level})
                except:
                    pass
            
            # Get move
            move = self.engine.get_ai_move(
                time_limit=self.ai_time_limit,
                depth=params.depth
            )
            
            if move:
                self.engine.make_move(move)
                return move
            return ""
            
        except Exception as e:
            print(f"AI Error: {e}")
            return ""

    def _finalize_game(self, result: str):
        """Update persistent profile after game end."""
        self.profile.update_after_game(
            result=result,
            accuracy=self.current_session_stats.get_accuracy(),
            difficulty_level=self.difficulty.get_difficulty_level(),
            moves_played=self.current_session_stats.move_quality.total_moves,
            blunders=self.current_session_stats.move_quality.blunders,
            mistakes=self.current_session_stats.move_quality.mistakes,
            current_game_stats=self.current_session_stats
        )
        self.profile.save()
        self.emotion_model.record_game_result(result)
    
    def get_coach_tip(self) -> str:
        """Get a standalone coaching tip."""
        # Mix of profile-based and phase-based
        if self.engine.is_game_over():
            return ""
            
        phase = self.analyzer.get_game_phase()
        
        # 50/50 chance of profile tip vs phase tip
        import random
        if random.random() > 0.5:
            return self.coach.profile_tip(
                list(self.profile.strengths),
                list(self.profile.weaknesses)
            )
        else:
            return self.coach.get_phase_tip(phase)

    def print_status(self):
        """Print debug status of all modules."""
        print(f"\n--- Status for {self.player_name} ---")
        print(f"Rating: {self.profile.rating:.0f}")
        print(f"Diff Level: {self.difficulty.get_difficulty_level()}")
        print(f"Emotion: {self.emotion_model.current_state.value}")
        print(f"Personality: {self.emotion_model.get_personality().value}")
