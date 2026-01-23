"""Analysis modules for chess game evaluation."""

from .time_analysis import (
    PlayerTimeStats,
    OpponentTimeStats,
    LongThink,
    analyze_opening_time,
    analyze_opponent_opening_time,
    find_long_thinks,
    analyze_time_pressure,
    print_opening_time_report,
    print_long_thinks_report,
)

from .engine_analysis import (
    MoveEvaluation,
    GameEvaluation,
    create_engine,
    evaluate_position,
    evaluate_move,
    analyze_game,
    analyze_games,
    calculate_accuracy,
)

from .accuracy_analysis import (
    PlayerAccuracyStats,
    ComebackRecord,
    BlownLeadRecord,
    calculate_player_accuracy,
    find_comebacks,
    find_blown_leads,
    print_accuracy_report,
    print_comeback_report,
    print_blown_lead_report,
)

from .evaluation_cache import (
    EvaluationCache,
    CachedEvaluation,
)
