"""
Game State Intelligence Layer

Provides analysis capabilities for chess game state including:
- Game phase detection (opening/middlegame/endgame)
- Material balance tracking
- Move quality evaluation (blunder/mistake/inaccuracy/good/excellent)
- Key event detection (check, checkmate, draw conditions)
"""

import chess
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class GamePhase(Enum):
    """Enum representing the phase of a chess game."""
    OPENING = "opening"
    MIDDLEGAME = "middlegame"
    ENDGAME = "endgame"


class MoveQuality(Enum):
    """Enum representing the quality of a move based on evaluation delta."""
    BLUNDER = "blunder"        # >= 200 centipawn loss
    MISTAKE = "mistake"        # >= 100 centipawn loss
    INACCURACY = "inaccuracy"  # >= 50 centipawn loss
    GOOD = "good"              # < 50 centipawn loss
    EXCELLENT = "excellent"    # Best move or improvement
    BOOK = "book"              # Known opening theory


class PositionEvent(Enum):
    """Enum representing significant position events."""
    CHECK = "check"
    CHECKMATE = "checkmate"
    STALEMATE = "stalemate"
    DRAW_INSUFFICIENT = "draw_insufficient_material"
    DRAW_FIFTY_MOVES = "draw_fifty_move_rule"
    DRAW_THREEFOLD = "draw_threefold_repetition"
    DRAW_FIVEFOLD = "draw_fivefold_repetition"
    DRAW_SEVENTY_FIVE = "draw_seventy_five_moves"


@dataclass
class MaterialBalance:
    """Represents the material balance on the board."""
    white_pawns: int
    white_knights: int
    white_bishops: int
    white_rooks: int
    white_queens: int
    black_pawns: int
    black_knights: int
    black_bishops: int
    black_rooks: int
    black_queens: int
    
    @property
    def white_total(self) -> int:
        """Total material value for White (P=1, N/B=3, R=5, Q=9)."""
        return (self.white_pawns * 1 +
                self.white_knights * 3 +
                self.white_bishops * 3 +
                self.white_rooks * 5 +
                self.white_queens * 9)
    
    @property
    def black_total(self) -> int:
        """Total material value for Black."""
        return (self.black_pawns * 1 +
                self.black_knights * 3 +
                self.black_bishops * 3 +
                self.black_rooks * 5 +
                self.black_queens * 9)
    
    @property
    def net_balance(self) -> int:
        """Net material advantage (positive = White ahead)."""
        return self.white_total - self.black_total
    
    @property
    def total_pieces(self) -> int:
        """Total number of non-pawn pieces on the board."""
        return (self.white_knights + self.white_bishops + 
                self.white_rooks + self.white_queens +
                self.black_knights + self.black_bishops +
                self.black_rooks + self.black_queens)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary representation."""
        return {
            "white": {
                "pawns": self.white_pawns,
                "knights": self.white_knights,
                "bishops": self.white_bishops,
                "rooks": self.white_rooks,
                "queens": self.white_queens,
                "total": self.white_total
            },
            "black": {
                "pawns": self.black_pawns,
                "knights": self.black_knights,
                "bishops": self.black_bishops,
                "rooks": self.black_rooks,
                "queens": self.black_queens,
                "total": self.black_total
            },
            "net_balance": self.net_balance,
            "total_material": self.white_total + self.black_total
        }


@dataclass
class MoveAnalysis:
    """Result of analyzing a move's quality."""
    move: str
    quality: MoveQuality
    eval_before: float
    eval_after: float
    centipawn_loss: float
    is_best_move: bool
    best_move: Optional[str] = None


class GameStateAnalyzer:
    """
    Analyzes chess game state for intelligent insights.
    
    Works with a chess.Board instance or ChessEngine to provide:
    - Game phase detection
    - Material balance calculation
    - Move quality evaluation
    - Position event detection
    
    Example:
        >>> from engine import ChessEngine, GameStateAnalyzer
        >>> engine = ChessEngine()
        >>> analyzer = GameStateAnalyzer(engine)
        >>> print(analyzer.get_game_phase())
        GamePhase.OPENING
    """
    
    # Material thresholds for endgame detection
    ENDGAME_MATERIAL_THRESHOLD = 13  # Total material per side
    
    # Move quality thresholds (in centipawns)
    BLUNDER_THRESHOLD = 200
    MISTAKE_THRESHOLD = 100
    INACCURACY_THRESHOLD = 50
    
    def __init__(self, engine=None, board: Optional[chess.Board] = None):
        """
        Initialize the analyzer.
        
        Args:
            engine: A ChessEngine instance (preferred for evaluation features)
            board: A chess.Board instance (fallback, no evaluation support)
        
        At least one of engine or board must be provided.
        """
        self._engine = engine
        self._board = board if board else (engine._board if engine else None)
        
        if self._board is None:
            raise ValueError("Must provide either engine or board")
    
    def get_game_phase(self) -> GamePhase:
        """
        Detect the current game phase.
        
        Returns:
            GamePhase enum value (OPENING, MIDDLEGAME, or ENDGAME)
        
        Logic:
        - Opening: ≤10 moves AND most minor pieces on starting squares
        - Endgame: No queens OR total material ≤ threshold
        - Middlegame: Everything else
        """
        material = self.get_material_balance()
        move_count = self._board.fullmove_number
        
        # Check for endgame conditions
        queens_off = material.white_queens == 0 and material.black_queens == 0
        low_material = (material.white_total <= self.ENDGAME_MATERIAL_THRESHOLD and
                       material.black_total <= self.ENDGAME_MATERIAL_THRESHOLD)
        
        if queens_off or low_material:
            return GamePhase.ENDGAME
        
        # Check for opening conditions
        if move_count <= 10:
            # Count pieces still on starting squares
            starting_minors = self._count_starting_minor_pieces()
            if starting_minors >= 4:  # At least 4 of 8 minor pieces undeveloped
                return GamePhase.OPENING
        
        return GamePhase.MIDDLEGAME
    
    def _count_starting_minor_pieces(self) -> int:
        """Count minor pieces still on their starting squares."""
        count = 0
        starting_squares = {
            # White knights and bishops
            chess.B1: chess.KNIGHT, chess.G1: chess.KNIGHT,
            chess.C1: chess.BISHOP, chess.F1: chess.BISHOP,
            # Black knights and bishops
            chess.B8: chess.KNIGHT, chess.G8: chess.KNIGHT,
            chess.C8: chess.BISHOP, chess.F8: chess.BISHOP,
        }
        
        for square, piece_type in starting_squares.items():
            piece = self._board.piece_at(square)
            if piece and piece.piece_type == piece_type:
                count += 1
        
        return count
    
    def get_material_balance(self) -> MaterialBalance:
        """
        Calculate the current material balance.
        
        Returns:
            MaterialBalance dataclass with piece counts and totals.
        """
        return MaterialBalance(
            white_pawns=len(self._board.pieces(chess.PAWN, chess.WHITE)),
            white_knights=len(self._board.pieces(chess.KNIGHT, chess.WHITE)),
            white_bishops=len(self._board.pieces(chess.BISHOP, chess.WHITE)),
            white_rooks=len(self._board.pieces(chess.ROOK, chess.WHITE)),
            white_queens=len(self._board.pieces(chess.QUEEN, chess.WHITE)),
            black_pawns=len(self._board.pieces(chess.PAWN, chess.BLACK)),
            black_knights=len(self._board.pieces(chess.KNIGHT, chess.BLACK)),
            black_bishops=len(self._board.pieces(chess.BISHOP, chess.BLACK)),
            black_rooks=len(self._board.pieces(chess.ROOK, chess.BLACK)),
            black_queens=len(self._board.pieces(chess.QUEEN, chess.BLACK)),
        )
    
    def evaluate_move_quality(
        self, 
        move: str,
        eval_before: Optional[float] = None,
        depth: int = 15
    ) -> MoveAnalysis:
        """
        Evaluate the quality of a move based on evaluation delta.
        
        Args:
            move: The move to evaluate in UCI format
            eval_before: Evaluation before the move (will be calculated if not provided)
            depth: Search depth for evaluation
        
        Returns:
            MoveAnalysis with quality classification and details.
        
        Raises:
            ValueError: If no engine is available for evaluation
        """
        if self._engine is None:
            raise ValueError("Engine required for move quality evaluation")
        
        # Get evaluation before move
        if eval_before is None:
            eval_before, _ = self._engine.evaluate_position()
        
        # Get the best move
        best_move = self._engine.get_ai_move(depth=depth)
        is_best = move.lower() == best_move.lower()
        
        # Make the move temporarily
        original_fen = self._board.fen()
        self._engine.make_move(move)
        
        # Get evaluation after move (from opponent's perspective, so negate)
        eval_after_raw, _ = self._engine.evaluate_position()
        eval_after = -eval_after_raw  # Flip sign for same-side comparison
        
        # Restore position
        self._engine.set_position(original_fen)
        
        # Handle infinite (mate) scores
        if eval_before == float('inf') or eval_before == float('-inf'):
            eval_before_cp = 10000 if eval_before > 0 else -10000
        else:
            eval_before_cp = eval_before * 100
            
        if eval_after == float('inf') or eval_after == float('-inf'):
            eval_after_cp = 10000 if eval_after > 0 else -10000
        else:
            eval_after_cp = eval_after * 100
        
        # Calculate centipawn loss (positive = loss for moving side)
        cp_loss = eval_before_cp - eval_after_cp
        
        # Classify move quality
        if is_best:
            quality = MoveQuality.EXCELLENT
        elif cp_loss >= self.BLUNDER_THRESHOLD:
            quality = MoveQuality.BLUNDER
        elif cp_loss >= self.MISTAKE_THRESHOLD:
            quality = MoveQuality.MISTAKE
        elif cp_loss >= self.INACCURACY_THRESHOLD:
            quality = MoveQuality.INACCURACY
        else:
            quality = MoveQuality.GOOD
        
        return MoveAnalysis(
            move=move,
            quality=quality,
            eval_before=eval_before,
            eval_after=eval_after,
            centipawn_loss=cp_loss,
            is_best_move=is_best,
            best_move=best_move if not is_best else None
        )
    
    def get_position_events(self) -> List[PositionEvent]:
        """
        Detect significant events in the current position.
        
        Returns:
            List of PositionEvent enums for the current position.
        """
        events = []
        
        # Check for check
        if self._board.is_check():
            events.append(PositionEvent.CHECK)
        
        # Check for game-ending conditions
        if self._board.is_checkmate():
            events.append(PositionEvent.CHECKMATE)
        
        if self._board.is_stalemate():
            events.append(PositionEvent.STALEMATE)
        
        if self._board.is_insufficient_material():
            events.append(PositionEvent.DRAW_INSUFFICIENT)
        
        if self._board.can_claim_fifty_moves():
            events.append(PositionEvent.DRAW_FIFTY_MOVES)
        
        if self._board.can_claim_threefold_repetition():
            events.append(PositionEvent.DRAW_THREEFOLD)
        
        if self._board.is_fivefold_repetition():
            events.append(PositionEvent.DRAW_FIVEFOLD)
        
        if self._board.is_seventyfive_moves():
            events.append(PositionEvent.DRAW_SEVENTY_FIVE)
        
        return events
    
    def is_in_check(self) -> bool:
        """Check if the side to move is in check."""
        return self._board.is_check()
    
    def is_checkmate(self) -> bool:
        """Check if the position is checkmate."""
        return self._board.is_checkmate()
    
    def is_stalemate(self) -> bool:
        """Check if the position is stalemate."""
        return self._board.is_stalemate()
    
    def is_draw(self) -> bool:
        """Check if the position is a draw."""
        return (self._board.is_stalemate() or
                self._board.is_insufficient_material() or
                self._board.is_fivefold_repetition() or
                self._board.is_seventyfive_moves())
    
    def can_claim_draw(self) -> bool:
        """Check if a draw can be claimed."""
        return (self._board.can_claim_fifty_moves() or
                self._board.can_claim_threefold_repetition())
    
    def get_position_summary(self) -> Dict:
        """
        Get a comprehensive summary of the current position.
        
        Returns:
            Dictionary with phase, material, events, and turn info.
        """
        material = self.get_material_balance()
        events = self.get_position_events()
        
        return {
            "phase": self.get_game_phase().value,
            "turn": "white" if self._board.turn else "black",
            "move_number": self._board.fullmove_number,
            "material": material.to_dict(),
            "events": [e.value for e in events],
            "is_game_over": self._board.is_game_over(),
        }
