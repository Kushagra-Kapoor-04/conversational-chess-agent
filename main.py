#!/usr/bin/env python3
"""
Chess CLI Demo

An interactive command-line chess game demonstrating the ChessEngine wrapper.
Play against Stockfish at configurable difficulty levels.
"""

import sys
import argparse
from engine import ChessEngine
from engine.chess_engine import ChessEngineError, StockfishNotFoundError, IllegalMoveError


def print_banner():
    """Print the game banner."""
    print("\n" + "=" * 50)
    print("  ♔ CHESS vs STOCKFISH ♚")
    print("=" * 50)


def print_help():
    """Print available commands."""
    print("\nCommands:")
    print("  [move]    - Enter move in UCI (e2e4) or SAN (e4) format")
    print("  undo      - Undo your last move and AI's response")
    print("  eval      - Show position evaluation")
    print("  fen       - Show current FEN")
    print("  moves     - Show legal moves")
    print("  flip      - Toggle board orientation")
    print("  new       - Start a new game")
    print("  help      - Show this help")
    print("  quit      - Exit the game\n")


def format_move_for_display(move: str, board_before_fen: str) -> str:
    """Format a UCI move with piece symbol for display."""
    import chess
    board = chess.Board(board_before_fen)
    uci_move = chess.Move.from_uci(move)
    san_move = board.san(uci_move)
    return f"{move} ({san_move})"


def main():
    """Main game loop."""
    parser = argparse.ArgumentParser(description="Play chess against Stockfish")
    parser.add_argument(
        "--stockfish", "-s",
        type=str,
        default=None,
        help="Path to Stockfish executable"
    )
    parser.add_argument(
        "--depth", "-d",
        type=int,
        default=10,
        choices=range(1, 21),
        metavar="1-20",
        help="AI difficulty (search depth, default: 10)"
    )
    parser.add_argument(
        "--play-as", "-p",
        type=str,
        default="white",
        choices=["white", "black"],
        help="Choose your color (default: white)"
    )
    
    args = parser.parse_args()
    
    print_banner()
    
    # Initialize engine
    try:
        engine = ChessEngine(stockfish_path=args.stockfish, default_depth=args.depth)
        print(f"✓ Stockfish connected (depth: {args.depth})")
    except StockfishNotFoundError as e:
        print(f"\n✗ Error: {e}")
        print("\nPlease provide the Stockfish path:")
        print("  python main.py --stockfish /path/to/stockfish")
        sys.exit(1)
    except ChessEngineError as e:
        print(f"\n✗ Engine error: {e}")
        sys.exit(1)
    
    # Game state
    flip_board = args.play_as == "black"
    player_color = args.play_as
    
    print(f"You are playing as: {player_color.upper()}")
    print_help()
    
    # If player is black, AI moves first
    if player_color == "black":
        print("\n🤖 AI is thinking...")
        ai_move = engine.get_ai_move()
        fen_before = engine.get_board_fen()
        engine.make_move(ai_move)
        print(f"AI plays: {format_move_for_display(ai_move, fen_before)}")
    
    # Main game loop
    try:
        while True:
            # Display board
            print("\n" + engine.get_board_visual(flip=flip_board))
            
            # Check game status
            result = engine.get_game_result()
            if result.is_over:
                print("\n" + "=" * 50)
                if result.reason == "checkmate":
                    winner = result.winner.upper() if result.winner else "Nobody"
                    if (result.winner == player_color):
                        print("🎉 CHECKMATE! You win!")
                    else:
                        print(f"💀 CHECKMATE! {winner} wins!")
                else:
                    print(f"🤝 DRAW by {result.reason.replace('_', ' ')}")
                print("=" * 50)
                
                # Ask to play again
                response = input("\nPlay again? (y/n): ").strip().lower()
                if response == 'y':
                    engine.reset()
                    print("\n🔄 New game started!")
                    if player_color == "black":
                        print("🤖 AI is thinking...")
                        ai_move = engine.get_ai_move()
                        fen_before = engine.get_board_fen()
                        engine.make_move(ai_move)
                        print(f"AI plays: {format_move_for_display(ai_move, fen_before)}")
                    continue
                else:
                    break
            
            # Show check status
            if engine.is_check():
                print("⚠️  CHECK!")
            
            # Get player input
            move_num = engine.get_move_count()
            turn = engine.get_turn()
            prompt = f"Move {move_num} ({turn}) > "
            
            try:
                user_input = input(prompt).strip()
            except EOFError:
                break
            
            if not user_input:
                continue
            
            cmd = user_input.lower()
            
            # Handle commands
            if cmd in ('quit', 'exit', 'q'):
                print("\nThanks for playing! Goodbye. 👋")
                break
            
            elif cmd == 'help':
                print_help()
                continue
            
            elif cmd == 'new':
                engine.reset()
                print("\n🔄 New game started!")
                if player_color == "black":
                    print("🤖 AI is thinking...")
                    ai_move = engine.get_ai_move()
                    fen_before = engine.get_board_fen()
                    engine.make_move(ai_move)
                    print(f"AI plays: {format_move_for_display(ai_move, fen_before)}")
                continue
            
            elif cmd == 'undo':
                # Undo both AI move and player move
                undone1 = engine.undo_move()
                undone2 = engine.undo_move()
                if undone1 and undone2:
                    print(f"↩️  Undid moves: {undone1}, {undone2}")
                elif undone1:
                    print(f"↩️  Undid move: {undone1}")
                else:
                    print("Nothing to undo.")
                continue
            
            elif cmd == 'eval':
                try:
                    score, desc = engine.evaluate_position()
                    if score == float('inf'):
                        print(f"📊 Evaluation: {desc}")
                    elif score == float('-inf'):
                        print(f"📊 Evaluation: {desc}")
                    else:
                        sign = "+" if score >= 0 else ""
                        print(f"📊 Evaluation: {sign}{score:.2f} - {desc}")
                except ChessEngineError as e:
                    print(f"Evaluation error: {e}")
                continue
            
            elif cmd == 'fen':
                print(f"FEN: {engine.get_board_fen()}")
                continue
            
            elif cmd == 'moves':
                legal = engine.get_legal_moves()
                print(f"Legal moves ({len(legal)}): {', '.join(legal)}")
                continue
            
            elif cmd == 'flip':
                flip_board = not flip_board
                print(f"Board flipped: viewing from {'Black' if flip_board else 'White'}'s side")
                continue
            
            # Try to make the move
            if not engine.is_legal_move(user_input):
                print(f"❌ Illegal move: '{user_input}'")
                print(f"   Try: {', '.join(engine.get_legal_moves()[:5])}...")
                continue
            
            # Make player's move
            fen_before = engine.get_board_fen()
            move_uci = engine.make_move(user_input)
            print(f"✓ Your move: {format_move_for_display(move_uci, fen_before)}")
            
            # Check if game ended after player's move
            if engine.is_game_over():
                continue
            
            # AI responds
            print("🤖 AI is thinking...")
            try:
                fen_before = engine.get_board_fen()
                ai_move = engine.get_ai_move()
                engine.make_move(ai_move)
                print(f"AI plays: {format_move_for_display(ai_move, fen_before)}")
            except ChessEngineError as e:
                print(f"AI error: {e}")
    
    except KeyboardInterrupt:
        print("\n\nGame interrupted. Goodbye! 👋")
    
    finally:
        engine.close()


if __name__ == "__main__":
    main()
