import pytest
from rayforge.models.ops import Command
from rayforge.opstransformer.arcwelder.arcwelder import split_into_segments


def test_split_empty_commands():
    assert split_into_segments([]) == []

def test_split_single_move():
    commands = [Command('move_to', (0, 0))]
    assert split_into_segments(commands) == [[Command('move_to', (0, 0))]]

def test_split_move_and_line():
    commands = [
        Command('move_to', (0, 0)),
        Command('line_to', (1, 0))
    ]
    assert split_into_segments(commands) == [
        [Command('move_to', (0, 0)), Command('line_to', (1, 0))]
    ]

def test_split_move_and_arc():
    commands = [
        Command('move_to', (0, 0)),
        Command('arc_to', (1, 0, 1, 1, False)),
        Command('line_to', (2, 0)),
        Command('line_to', (3, 0)),
    ]
    assert split_into_segments(commands) == [
        [Command('move_to', (0, 0)), Command('arc_to', (1, 0, 1, 1, False))],
        [Command('move_to', (1, 0)), Command('line_to', (2, 0)), Command('line_to', (3, 0))],
    ]

def test_split_state_commands():
    commands = [
        Command('set_power', (1000,)),
        Command('move_to', (0, 0)),
        Command('line_to', (1, 0)),
        Command('disable_air_assist', ())
    ]
    assert split_into_segments(commands) == [
        [Command('set_power', (1000,))],
        [Command('move_to', (0, 0)), Command('line_to', (1, 0))],
        [Command('disable_air_assist', ())]
    ]

def test_split_long_mixed_segment():
    commands = [
        Command('move_to', (0, 0)),
        Command('line_to', (1, 0)),
        Command('line_to', (2, 0)),
        Command('move_to', (3, 0)),
        Command('line_to', (4, 0)),
        Command('arc_to', (5, 0, 1, 1, False)),
        Command('line_to', (6, 0)),
        Command('move_to', (7, 0)),
        Command('arc_to', (8, 0, 1, 1, False)),
        Command('move_to', (7, 0)),
        Command('arc_to', (8, 0, 1, 1, False)),
    ]
    assert split_into_segments(commands) == [
        [Command('move_to', (0, 0)), Command('line_to', (1, 0)), Command('line_to', (2, 0))],
        [Command('move_to', (3, 0)), Command('line_to', (4, 0))],
        [Command('arc_to', (5, 0, 1, 1, False))],
        [Command('move_to', (5, 0)), Command('line_to', (6, 0))],
        [Command('move_to', (7, 0)), Command('arc_to', (8, 0, 1, 1, False))],
        [Command('move_to', (7, 0)), Command('arc_to', (8, 0, 1, 1, False))],
    ]
