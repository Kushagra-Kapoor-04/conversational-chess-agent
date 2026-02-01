# Python Chess Engine Wrapper

A lightweight Python module wrapping the Stockfish engine using `python-chess`. It provides a clean API for chess game state management, legal move validation, AI move generation, and position evaluation.

## 🚀 Features

- **Clean API**: Manage chess games with simple methods.
- **Legal Move Validation**: Supports both UCI and SAN notation.
- **AI Integration**: Interface with Stockfish for best-move generation at variable depths.
- **Evaluation**: Get centipawn evaluation or mate detection.
- **CLI Demo**: Includes an interactive command-line interface to play against the AI.

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
python main.py --stockfish "path/to/stockfish.exe" --depth 12
```

### CLI Commands
- `e2e4` / `e4` : Make a move
- `undo` : Undo the last move pair
- `eval` : Show engine evaluation
- `moves` : Show all legal moves
- `new` : Reset the game
- `quit` : Exit the program

## 💻 API Usage

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

## ⚖️ License
MIT
