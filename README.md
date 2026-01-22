# Chess Analysis Project

Analyzing professional chess tournaments from PGN files, with a focus on time management, preparation detection, and performance metrics. Built to analyze the 2026 FIDE Candidates Tournament in real-time.

## Project Goals

- **Daily Analysis**: Generate insights and visualizations after each round of play
- **TikTok Content**: Create engaging, mobile-optimized charts for social media
- **Time Analysis**: Track opening time, long thinks, and time pressure
- **Prep Detection**: Identify when players leave preparation
- **Accuracy Metrics**: Use Stockfish to measure player performance

## Project Structure

```
chess_analysis/
├── data/
│   ├── raw/              # Downloaded PGN files
│   ├── processed/        # Parsed game data (CSV/JSON)
│   └── cache/            # Stockfish evaluation cache
├── src/
│   ├── parsers/
│   │   ├── pgn_parser.py        # PGN parsing utilities
│   │   └── clock_parser.py      # Time control handling
│   ├── analysis/
│   │   ├── time_analysis.py     # Opening time, long thinks
│   │   ├── prep_detection.py    # Detect when players leave prep
│   │   ├── engine_analysis.py   # Stockfish integration
│   │   └── performance.py       # Win rates, accuracy
│   ├── visualization/
│   │   ├── templates.py         # TikTok-optimized charts
│   │   ├── time_viz.py          # Time visualizations
│   │   └── accuracy_viz.py      # Engine analysis viz
│   └── utils/
│       ├── config.py             # Configuration loader
│       └── helpers.py            # Common utilities
├── scripts/
│   ├── daily_analysis.py         # Main workflow
│   └── tournament_setup.py       # Initialize tournament
├── outputs/
│   ├── graphs/                   # Generated visualizations
│   └── reports/                  # Summary statistics
├── tests/                        # Unit tests
├── config.yaml                   # Tournament & analysis settings
└── requirements.txt
```

## Setup

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure tournament settings**:
   Edit `config.yaml` to set your active tournament and time control format.

3. **Add PGN files**:
   Place PGN files in `data/raw/`

## Configuration

The `config.yaml` file handles different tournament formats and time controls. Key sections:

### Time Controls

Different tournaments use different time controls. Define them in the `time_controls` section:

```yaml
time_controls:
  candidates_2024:
    base_time: 7200              # 120 minutes in seconds
    increment_type: "delay_bonus" # fischer/delay_bonus/bronstein/none
    increment_start_move: 41      # When increment starts
    increment_seconds: 30
    bonus_time: 1800             # Added after move 40
```

**Increment Types:**
- `fischer`: Increment added immediately after each move (from move 1 or specified start)
- `delay_bonus`: Increment added only after a specific move (e.g., move 40)
- `bronstein`: Delay before clock starts (uncommon in top-level play)
- `none`: No increment

### Active Tournament

Set which tournament you're analyzing:

```yaml
active_tournament:
  time_control: "candidates_2024"
  pgn_file: "2024-fide-candidates-chess-tournament.pgn"
```

### Analysis Thresholds

Customize what counts as "long think", "prep exit", etc.:

```yaml
analysis:
  time_thresholds:
    opening_moves: 10
    long_think_minutes: 20

  prep_detection:
    method: "hybrid"
    percentage_threshold: 0.05  # 5% of remaining time
    absolute_threshold_minutes: 10
```

## Usage

### Basic Time Analysis

```python
from pathlib import Path
from src.utils.config import get_config
from src.parsers.pgn_parser import read_pgn_file
from src.analysis.time_analysis import (
    analyze_opening_time,
    find_long_thinks,
    print_opening_time_report
)

# Load config
config = get_config()

# Parse games
pgn_path = config.data_raw_path / config.active_pgn_file
time_control = config.active_time_control
games = list(read_pgn_file(pgn_path, time_control))

# Analyze opening time
stats = analyze_opening_time(games, opening_moves=config.opening_moves)
print_opening_time_report(stats)

# Find long thinks
counts, thinks = find_long_thinks(games, config.long_think_seconds)
```

### Handling Different Time Controls

The system automatically handles different time control formats. Just update `config.yaml`:

**Example: Switching to World Cup format**
```yaml
active_tournament:
  time_control: "world_cup_classical"  # 90 min + 30 sec after move 40
  pgn_file: "2025-fide-world-cup.pgn"
```

**Example: Adding a new tournament**
```yaml
time_controls:
  my_tournament:
    base_time: 6000              # 100 minutes
    increment_type: "fischer"
    increment_start_move: 1
    increment_seconds: 30
    bonus_time: 0
```

## Key Modules

### `src/parsers/clock_parser.py`
- `parse_clock_time()`: Convert PGN clock strings to seconds
- `calculate_time_spent()`: Handle increments/bonuses correctly
- `TimeTracker`: Track time throughout a game

### `src/parsers/pgn_parser.py`
- `read_pgn_file()`: Parse PGN files into structured data
- `ParsedGame`: Dataclass with metadata and moves
- `MoveData`: Individual move with clock times

### `src/analysis/time_analysis.py`
- `analyze_opening_time()`: Time spent in first N moves
- `analyze_opponent_opening_time()`: Who forces opponents to think?
- `find_long_thinks()`: Detect 20+ minute thinks
- `analyze_time_pressure()`: Track low-clock situations

### `src/utils/config.py`
- `Config`: Load and access settings from `config.yaml`
- `get_config()`: Get global config instance

## Roadmap

- [x] Project structure
- [x] PGN parsing with time controls
- [x] Opening time analysis
- [x] Long think detection
- [ ] Prep detection algorithm
- [ ] Stockfish integration
- [ ] Accuracy calculations
- [ ] Comeback/blown lead detection
- [ ] Visualization templates
- [ ] Daily workflow automation

## Data Sources

PGN files can be downloaded from:
- [Chess.com](https://www.chess.com/games) - Tournament archives
- [Lichess](https://lichess.org/broadcast) - Live broadcasts
- [FIDE](https://www.fide.com/) - Official tournament games

## License

MIT

## Contributing

This is a personal project for analyzing the 2026 Candidates Tournament, but feel free to fork and adapt for your own chess analysis needs.
