"""
Chess Engine Wrapper Module

A clean Python API wrapping the Stockfish engine using python-chess.
Provides legal move validation, AI move generation, and board evaluation.
"""

import os
import chess
import chess.engine
from typing import Optional, List, Tuple
from dataclasses import dataclass


@dataclass
class GameResult:
    """Represents the result of a finished game."""
    is_over: bool
    winner: Optional[str] = None  # "white", "black", or None for draw
    reason: Optional[str] = None  # "checkmate", "stalemate", "insufficient_material", etc.


class ChessEngineError(Exception):
    """Base exception for chess engine errors."""
    pass


class StockfishNotFoundError(ChessEngineError):
    """Raised when Stockfish executable cannot be found."""
    pass


class IllegalMoveError(ChessEngineError):
    """Raised when an illegal move is attempted."""
    pass


class ChessEngine:
    """
    A wrapper around the Stockfish chess engine using python-chess.
    
    Provides a clean API for:
    - Legal move validation
    - AI move generation at variable depths
    - Board evaluation
    - Game state management
    
    Example:
        >>> engine = ChessEngine("path/to/stockfish")
        >>> engine.make_move("e2e4")
        >>> ai_move = engine.get_ai_move(depth=15)
        >>> print(engine.get_board_visual())
    """
    
    # Common Stockfish installation paths
    DEFAULT_PATHS = [
        # Windows
        r"C:\Program Files\Stockfish\stockfish.exe",
        r"C:\Program Files (x86)\Stockfish\stockfish.exe",
        r"C:\stockfish\stockfish.exe",
        r".\stockfish.exe",
        r".\stockfish\stockfish.exe",
        # Linux/Mac
        "/usr/local/bin/stockfish",
        "/usr/bin/stockfish",
        "/opt/homebrew/bin/stockfish",
        "./stockfish",
    ]
    
    def __init__(self, stockfish_path: Optional[str] = None, default_depth: int = 15):
        """
        Initialize the chess engine.
        
        Args:
            stockfish_path: Path to Stockfish executable. If None, attempts auto-detection.
            default_depth: Default search depth for AI moves (1-30).
        
        Raises:
            StockfishNotFoundError: If Stockfish cannot be found at the given path.
        """
        self._board = chess.Board()
        self._default_depth = max(1, min(30, default_depth))
        self._stockfish_path = self._find_stockfish(stockfish_path)
        self._engine: Optional[chess.engine.SimpleEngine] = None
        self._connect_engine()
    
    def _find_stockfish(self, provided_path: Optional[str]) -> str:
        """Find Stockfish executable, checking provided path or common locations."""
        if provided_path:
            if os.path.isfile(provided_path):
                return provided_path
            raise StockfishNotFoundError(
                f"Stockfish not found at: {provided_path}\n"
                "Please provide a valid path to the Stockfish executable."
            )
        
        # Auto-detect from common paths
        for path in self.DEFAULT_PATHS:
            if os.path.isfile(path):
                return path
        
        # Check if 'stockfish' is in PATH
        import shutil
        stockfish_in_path = shutil.which("stockfish")
        if stockfish_in_path:
            return stockfish_in_path
        
        raise StockfishNotFoundError(
            "Stockfish executable not found!\n"
            "Please install Stockfish and provide the path:\n"
            "  - Download from: https://stockfishchess.org/download/\n"
            "  - Or install via package manager (apt, brew, choco)\n"
            f"  - Auto-checked paths: {self.DEFAULT_PATHS[:3]}..."
        )
    
    def _connect_engine(self) -> None:
        """Connect to the Stockfish engine."""
        try:
            self._engine = chess.engine.SimpleEngine.popen_uci(self._stockfish_path)
        except Exception as e:
            raise ChessEngineError(f"Failed to start Stockfish: {e}")
    
    def reset(self) -> None:
        """Reset the board to the starting position."""
        self._board.reset()
    
    def set_position(self, fen: str) -> None:
        """
        Set the board to a specific position using FEN notation.
        
        Args:
            fen: FEN string representing the position.
        
        Raises:
            ValueError: If the FEN string is invalid.
        """
        try:
            self._board.set_fen(fen)
        except ValueError as e:
            raise ValueError(f"Invalid FEN string: {e}")
    
    def get_legal_moves(self) -> List[str]:
        """
        Get all legal moves in the current position.
        
        Returns:
            List of legal moves in UCI format (e.g., ["e2e4", "d2d4", ...])
        """
        return [move.uci() for move in self._board.legal_moves]
    
    def is_legal_move(self, move: str) -> bool:
        """
        Check if a move is legal in the current position.
        
        Args:
            move: Move in UCI format (e.g., "e2e4") or SAN format (e.g., "e4")
        
        Returns:
            True if the move is legal, False otherwise.
        """
        try:
            # Try UCI format first
            chess_move = chess.Move.from_uci(move)
            if chess_move in self._board.legal_moves:
                return True
        except (ValueError, chess.InvalidMoveError):
            pass
        
        try:
            # Try SAN format
            self._board.parse_san(move)
            return True
        except (ValueError, chess.InvalidMoveError, chess.AmbiguousMoveError):
            return False
    
    def make_move(self, move: str) -> str:
        """
        Make a move on the board.
        
        Args:
            move: Move in UCI format (e.g., "e2e4") or SAN format (e.g., "e4")
        
        Returns:
            The move in UCI format.
        
        Raises:
            IllegalMoveError: If the move is not legal.
        """
        chess_move = None
        
        # Try UCI format first
        try:
            chess_move = chess.Move.from_uci(move)
            if chess_move not in self._board.legal_moves:
                chess_move = None
        except (ValueError, chess.InvalidMoveError):
            pass
        
        # Try SAN format if UCI failed
        if chess_move is None:
            try:
                chess_move = self._board.parse_san(move)
            except (ValueError, chess.InvalidMoveError, chess.AmbiguousMoveError):
                raise IllegalMoveError(
                    f"Illegal move: '{move}'\n"
                    f"Legal moves: {', '.join(self.get_legal_moves()[:10])}..."
                )
        
        self._board.push(chess_move)
        return chess_move.uci()
    
    def undo_move(self) -> Optional[str]:
        """
        Undo the last move.
        
        Returns:
            The undone move in UCI format, or None if no moves to undo.
        """
        try:
            move = self._board.pop()
            return move.uci()
        except IndexError:
            return None
    
    def get_ai_move(self, depth: Optional[int] = None, time_limit: Optional[float] = None) -> str:
        """
        Get the best move from Stockfish for the current position.
        
        Args:
            depth: Search depth (1-30). Uses default if not specified.
            time_limit: Time limit in seconds. If specified, overrides depth.
        
        Returns:
            Best move in UCI format.
        
        Raises:
            ChessEngineError: If the engine fails to find a move.
        """
        if self._engine is None:
            raise ChessEngineError("Engine not connected")
        
        if self.is_game_over():
            raise ChessEngineError("Cannot get AI move: game is over")
        
        try:
            if time_limit:
                limit = chess.engine.Limit(time=time_limit)
            else:
                search_depth = depth if depth else self._default_depth
                search_depth = max(1, min(30, search_depth))
                limit = chess.engine.Limit(depth=search_depth)
            
            result = self._engine.play(self._board, limit)
            return result.move.uci()
        except Exception as e:
            raise ChessEngineError(f"Engine error: {e}")
    
    def evaluate_position(self) -> Tuple[float, str]:
        """
        Evaluate the current position.
        
        Returns:
            Tuple of (score, description):
            - score: Evaluation in pawns (positive = white advantage)
            - description: Human-readable evaluation
        
        Raises:
            ChessEngineError: If evaluation fails.
        """
        if self._engine is None:
            raise ChessEngineError("Engine not connected")
        
        try:
            info = self._engine.analyse(self._board, chess.engine.Limit(depth=15))
            score = info["score"].white()
            
            if score.is_mate():
                mate_in = score.mate()
                if mate_in > 0:
                    return (float('inf'), f"White mates in {mate_in}")
                else:
                    return (float('-inf'), f"Black mates in {-mate_in}")
            else:
                cp = score.score() / 100  # Convert centipawns to pawns
                
                if abs(cp) < 0.3:
                    desc = "Equal position"
                elif cp > 0:
                    if cp < 1:
                        desc = "Slight advantage for White"
                    elif cp < 3:
                        desc = "Clear advantage for White"
                    else:
                        desc = "Winning position for White"
                else:
                    if cp > -1:
                        desc = "Slight advantage for Black"
                    elif cp > -3:
                        desc = "Clear advantage for Black"
                    else:
                        desc = "Winning position for Black"
                
                return (cp, desc)
        except Exception as e:
            raise ChessEngineError(f"Evaluation error: {e}")
    
    def get_board_fen(self) -> str:
        """Get the current position in FEN notation."""
        return self._board.fen()
    
    def get_board_visual(self, flip: bool = False) -> str:
        """
        Get an ASCII representation of the board.
        
        Args:
            flip: If True, show board from Black's perspective.
        
        Returns:
            ASCII art of the board with coordinates.
        """
        board_str = str(self._board) if not flip else str(self._board.transform(chess.flip_vertical))
        
        lines = board_str.split('\n')
        ranks = '87654321' if not flip else '12345678'
        
        result = []
        result.append("  ┌───────────────────┐")
        for i, line in enumerate(lines):
            spaced_line = ' '.join(line.split())
            result.append(f"{ranks[i]} │ {spaced_line} │")
        result.append("  └───────────────────┘")
        
        files = "    a   b   c   d   e   f   g   h" if not flip else "    h   g   f   e   d   c   b   a"
        result.append(files)
        
        return '\n'.join(result)
    
    def is_game_over(self) -> bool:
        """Check if the game has ended."""
        return self._board.is_game_over()
    
    def get_game_result(self) -> GameResult:
        """
        Get the result of the game.
        
        Returns:
            GameResult with is_over, winner, and reason.
        """
        if not self._board.is_game_over():
            return GameResult(is_over=False)
        
        outcome = self._board.outcome()
        
        if outcome is None:
            return GameResult(is_over=True, reason="unknown")
        
        winner = None
        if outcome.winner is True:
            winner = "white"
        elif outcome.winner is False:
            winner = "black"
        
        reason_map = {
            chess.Termination.CHECKMATE: "checkmate",
            chess.Termination.STALEMATE: "stalemate",
            chess.Termination.INSUFFICIENT_MATERIAL: "insufficient_material",
            chess.Termination.SEVENTYFIVE_MOVES: "75_move_rule",
            chess.Termination.FIVEFOLD_REPETITION: "fivefold_repetition",
            chess.Termination.FIFTY_MOVES: "50_move_rule",
            chess.Termination.THREEFOLD_REPETITION: "threefold_repetition",
        }
        reason = reason_map.get(outcome.termination, str(outcome.termination))
        
        return GameResult(is_over=True, winner=winner, reason=reason)
    
    def is_check(self) -> bool:
        """Check if the current side to move is in check."""
        return self._board.is_check()
    
    def get_turn(self) -> str:
        """Get whose turn it is to move."""
        return "white" if self._board.turn == chess.WHITE else "black"
    
    def get_move_history(self) -> List[str]:
        """Get the list of moves played in UCI format."""
        return [move.uci() for move in self._board.move_stack]
    
    def get_move_count(self) -> int:
        """Get the full move number (increments after Black moves)."""
        return self._board.fullmove_number
    
    def close(self) -> None:
        """Close the engine connection and cleanup resources."""
        if hasattr(self, '_engine') and self._engine:
            try:
                self._engine.quit()
            except Exception:
                pass
            self._engine = None
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        return False
    
    def __del__(self):
        """Destructor to ensure engine is closed."""
        self.close()
