# Python Chess Engine Wrapper

A lightweight Python module wrapping the Stockfish engine using `python-chess`. It provides a clean API for chess game state management, legal move validation, AI move generation, and position evaluation.

## 🚀 Features

- **Robust Wrapper**: Handles engine initialization, move validation, and cleanup.
- **Game State Analysis**: Tracks material, detects game phases (Opening/Middlegame/Endgame), and evaluates move quality.
- **Adaptive Difficulty**: AI adjusts strength based on your performance.
- **Player Profiling**: Tracks rating, strengths (e.g., "Endgame Expert"), and weaknesses (e.g., "Prone to Tilt").
- **AI Coach**: Provides natural language feedback, move explanations, and tips.
- **Emotion & Flow**: Detects user frustration ("Tilt") or confidence ("Flow") and adapts coaching style.
- **Game Modes**:
  - **PvC**: Player vs Computer (Adaptive).
  - **PvP**: Player vs Player with AI Spectator commentary.
- **CLI Interface**: Interactive command-line interface.

## 🛠️ Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/Chess_agent.git
   cd Chess_agent
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Install Stockfish:**
   Download the Stockfish binary for your OS from [stockfishchess.org](https://stockfishchess.org/download/).

## 🎮 How to Play

Run the interactive CLI:

```bash
# Auto-detects Stockfish in common paths
python main.py

# Or specify your Stockfish path
python main.py --stockfish "path/to/stockfish.exe"

# Player vs Player (AI Spectator)
python main.py --mode pvp

# Play as Black
python main.py --play-as black
```

### CLI Commands
- `e2e4` / `e4`: Make a move
- `status`: Show your rating, emotion state, and difficulty level
- `eval`: Show engine evaluation
- `undo`: Undo the last move pair
- `moves`: Show all legal moves
- `new`: Reset the game
- `quit`: Exit the program

## 💻 API Usage

### Supervisor (Recommended)
```python
from engine import GameSupervisor

# Initialize
sup = GameSupervisor(stockfish_path="path/to/stockfish")

# Process Player Move
result = sup.process_player_move("e4")
print(result.feedback)  # "Good move! Controlling the center..."

# Get AI Move (Adaptive)
ai_move = sup.play_ai_move()
```

### Basic Engine Usage
```python
from engine import ChessEngine

# Initialize
with ChessEngine(stockfish_path="path/to/stockfish") as engine:
    # Make a move
    engine.make_move("e4")
    
    # Get AI response
    ai_move = engine.get_ai_move(depth=15)
    engine.make_move(ai_move)
    
    # Check evaluation
    score, description = engine.evaluate_position()
    print(f"Eval: {score} ({description})")
    
    # Show board
    print(engine.get_board_visual())
```


