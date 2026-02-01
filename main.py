#!/usr/bin/env python3
"""
Chess CLI Demo

An interactive command-line chess game demonstrating the ChessEngine wrapper.
Play against Stockfish at configurable difficulty levels.
"""

import sys
import argparse
from engine import GameSupervisor, ChessEngine
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
    print("  status    - Show game status and profiles")
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
    """Main game loop using GameSupervisor."""
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
        help="AI difficulty override (1-20). If not set, adaptive difficulty is used."
    )
    parser.add_argument(
        "--play-as", "-p",
        type=str,
        default="white",
        choices=["white", "black"],
        help="Choose your color (default: white)"
    )
    parser.add_argument(
        "--mode", "-m",
        type=str,
        default="pvc",
        choices=["pvc", "pvp"],
        help="Game mode: 'pvc' (Player vs Computer) or 'pvp' (Player vs Player)"
    )
    
    parser.add_argument(
        "--user", "-u",
        type=str,
        default="Player",
        help="Player username for profile tracking"
    )
    
    args = parser.parse_args()
    
    print_banner()
    
    # Initialize Supervisor
    try:
        supervisor = GameSupervisor(
            stockfish_path=args.stockfish,
            player_name=args.user
        )
        engine = supervisor.engine 
        
        print(f"✓ Stockfish connected.")
        if args.mode == "pvc":
            print(f"✓ Profile loaded for: {args.user}")
            print(f"✓ Rating: {supervisor.profile.rating:.0f}")
            print(f"✓ Difficulty: Level {supervisor.difficulty.get_difficulty_level()} (Adaptive)")
        else:
            print(f"✓ Spectator Mode Active: AI Coach will comment on both players.")
        
    except StockfishNotFoundError as e:
        print(f"\n✗ Error: {e}")
        print("\nPlease provide the Stockfish path:")
        print("  python main.py --stockfish /path/to/stockfish")
        
        # Offer Mock Mode
        print("\n" + "!" * 50)
        print("MISSING ENGINE: Would you like to play in MOCK MODE?")
        print("In Mock Mode, the AI plays RANDOM moves. Useful for testing UI.")
        print("!" * 50)
        choice = input("Enable Mock Mode? (y/n): ").strip().lower()
        
        if choice == 'y':
            try:
                supervisor = GameSupervisor(player_name=args.user, mock_mode=True)
                engine = supervisor.engine
                print(f"✓ Started in MOCK MODE (Random Mover)")
            except Exception as e_mock:
                print(f"✗ Mock initialization failed: {e_mock}")
                sys.exit(1)
        else:
            sys.exit(1)

    except Exception as e:
        print(f"\n✗ Initialization error: {e}")
        sys.exit(1)
    
    # Game state
    flip_board = args.play_as == "black"
    player_color = args.play_as
    
    if args.mode == "pvc":
        print(f"You are playing as: {player_color.upper()}")
        # If player is black, AI moves first
        if player_color == "black":
            print("\n🤖 AI is thinking...")
            fen_before = engine.get_board_fen()
            ai_move = supervisor.play_ai_move()
            print(f"AI plays: {format_move_for_display(ai_move, fen_before)}")
            
    else: # PvP
        print("Player vs Player Mode (White vs Black)")
        print("AI Coach is watching...")
    
    print_help()
    
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
                    print(f"🎉 CHECKMATE! {winner} wins!")
                else:
                    print(f"🤝 DRAW by {result.reason.replace('_', ' ')}")
                
                # Show summary
                # For PvP, we just show generic summary
                summary = supervisor.coach.game_summary(
                    result="draw", # Generic result for summary usage
                    total_moves=supervisor.current_session_stats.move_quality.total_moves,
                    blunders=supervisor.current_session_stats.move_quality.blunders,
                    mistakes=supervisor.current_session_stats.move_quality.mistakes,
                    excellent_moves=supervisor.current_session_stats.move_quality.excellent_moves,
                    accuracy=supervisor.current_session_stats.get_accuracy()
                )
                print("\n" + summary)
                print("=" * 50)
                
                # Ask to play again
                response = input("\nPlay again? (y/n): ").strip().lower()
                if response == 'y':
                    engine.reset()
                    print("\n🔄 New game started!")
                    if args.mode == "pvc" and player_color == "black":
                         print("🤖 AI is thinking...")
                         fen_before = engine.get_board_fen()
                         ai_move = supervisor.play_ai_move()
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
            
            elif cmd == 'status':
                supervisor.print_status()
                continue
            
            elif cmd == 'new':
                engine.reset()
                print("\n🔄 New game started!")
                if args.mode == "pvc" and player_color == "black":
                    print("🤖 AI is thinking...")
                    fen_before = engine.get_board_fen()
                    ai_move = supervisor.play_ai_move()
                    print(f"AI plays: {format_move_for_display(ai_move, fen_before)}")
                continue
            
            elif cmd == 'undo':
                if args.mode == "pvc":
                     # Undo both (Player + AI)
                    undone1 = engine.undo_move()
                    undone2 = engine.undo_move()
                    if undone1 and undone2:
                        print(f"↩️  Undid moves: {undone1}, {undone2}")
                    elif undone1:
                        print(f"↩️  Undid move: {undone1}")
                else:
                    # Undo single move (PvP)
                    undone = engine.undo_move()
                    if undone:
                        print(f"↩️  Undid move: {undone}")
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
                except Exception as e:
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
            
            # Try to process the move via Supervisor
            print("Thinking...")
            result = supervisor.process_player_move(user_input)
            
            if not result.is_legal:
                print(f"❌ {result.error_message}")
                print(f"   Try: {', '.join(engine.get_legal_moves()[:5])}...")
                continue
            
            # Display feedback
            turn_color = "White" if turn == "White" else "Black" # Wait, turn updated AFTER move? 
            # Process move executes the move. 
            # So `turn` variable (captured before move) is correct.
            # But process_player_move already happened.
            
            print(f"✓ {turn} plays: {result.move_san}")
            if result.feedback:
                print(f"\n📢 Coach: {result.feedback}\n")
            
            # Check if game ended after player's move
            if engine.is_game_over():
                continue
            
            # AI Response (Only in PvC)
            if args.mode == "pvc":
                print("🤖 AI is thinking...")
                try:
                    fen_before = engine.get_board_fen()
                    ai_move = supervisor.play_ai_move()
                    print(f"AI plays: {format_move_for_display(ai_move, fen_before)}")
                except Exception as e:
                    print(f"AI error: {e}")

    except KeyboardInterrupt:
        print("\n\nGame interrupted. Goodbye! 👋")
    
    finally:
        supervisor.close()


if __name__ == "__main__":
    main()
