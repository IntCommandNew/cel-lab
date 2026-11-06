from dataclasses import replace

import numpy as np
import pytest

from cellab.engine import WorldError, simulate
from cellab.presets import load_preset
from cellab.ui.run_logic import (
    CHART_FALLBACK,
    GRID_LINE,
    build_world,
    cell_size,
    chart_colors,
    default_world,
    generations_label,
    render,
    space_time,
)


def preset(preset_id):
    return load_preset(preset_id).automaton


def test_default_worlds():
    assert default_world(preset("game-of-life")) == {
        "kind": "random",
        "probabilities": {"alive": 0.3},
        "seed": 1,
    }
    assert default_world(preset("forest-fire"))["probabilities"] == {"tree": 0.15, "fire": 0.15}
    assert default_world(preset("rule-30")) == {"kind": "centre", "state": "alive"}


def test_build_world_kinds():
    life = preset("game-of-life")
    random = build_world(life, {"kind": "random", "probabilities": {"alive": 0.5}, "seed": 3})
    again = build_world(life, {"kind": "random", "probabilities": {"alive": 0.5}, "seed": 3})
    np.testing.assert_array_equal(random, again)
    centre = build_world(life, {"kind": "centre", "state": "alive"})
    assert np.argwhere(centre).tolist() == [[15, 20]]
    text = build_world(life, {"kind": "text", "text": "###"})
    assert text.sum() == 3 and text.shape == (30, 40)


def test_build_world_errors_are_readable():
    with pytest.raises(WorldError, match="unknown symbols x"):
        build_world(preset("game-of-life"), {"kind": "text", "text": "#x#"})
    with pytest.raises(WorldError, match="more than 1"):
        build_world(
            preset("forest-fire"),
            {"kind": "random", "probabilities": {"tree": 0.8, "fire": 0.5}, "seed": 1},
        )


def test_cell_size_fits_the_image_width():
    assert cell_size(40) == 18
    assert cell_size(10) == 24  # capped
    assert cell_size(1000) == 1


def test_render_uses_state_colours_and_hairlines():
    life = preset("game-of-life")
    grid = np.zeros((2, 3), np.uint8)
    grid[0, 1] = 1
    image = render(life, grid, cell=10)
    assert image.shape == (20, 30, 3) and image.dtype == np.uint8
    assert tuple(image[5, 15]) == (0x2E, 0x2A, 0x5C)  # inside the alive cell
    assert tuple(image[5, 5]) == (0xF3, 0xF5, 0xF8)  # inside a dead cell
    assert tuple(image[0, 5]) == GRID_LINE and tuple(image[5, 10]) == GRID_LINE


def test_small_cells_have_no_hairlines():
    life = preset("game-of-life")
    image = render(life, np.ones((4, 4), np.uint8), cell=2)
    assert (image == (0x2E, 0x2A, 0x5C)).all()


def test_space_time_stacks_generations():
    rule30 = preset("rule-30")
    rule30 = replace(rule30, grid=replace(rule30.grid, width=9))
    run = simulate(rule30, build_world(rule30, default_world(rule30)), 3)
    picture = space_time(run, 3)
    assert picture.shape == (4, 9)
    assert ["".join(map(str, row)) for row in picture] == [
        "000010000",
        "000111000",
        "001100100",
        "011011110",
    ]


def test_pale_state_colours_are_replaced_in_charts():
    assert chart_colors(preset("game-of-life")) == [CHART_FALLBACK, "#2E2A5C"]


def test_generations_label():
    assert generations_label(1) == "1 generation"
    assert generations_label(50) == "50 generations"


def test_next_view_during_playback():
    from cellab.ui.run_logic import next_view

    assert next_view([0, 1, 2, 3], 0) == (1, False)
    assert next_view([0, 1, 2, 3], 2) == (3, True)
    assert next_view([0, 1, 2, 3], 3) == (3, True)
    assert next_view([0, 10, 20, 25], 10) == (20, False)  # only stored generations


def test_neighbour_view_stays_in_range():
    from cellab.ui.run_logic import neighbour_view

    assert neighbour_view([0, 1, 2], 1, -1) == 0
    assert neighbour_view([0, 1, 2], 0, -1) == 0
    assert neighbour_view([0, 1, 2], 2, +1) == 2
    assert neighbour_view([0, 10, 20], 10, +1) == 20


def test_png_data_uri_round_trips():
    import base64
    import io

    from PIL import Image

    from cellab.ui.run_logic import png_data_uri

    image = render(preset("game-of-life"), np.eye(4, dtype=np.uint8), cell=10)
    uri = png_data_uri(image)
    assert uri.startswith("data:image/png;base64,")
    decoded = np.array(Image.open(io.BytesIO(base64.b64decode(uri.split(",", 1)[1]))))
    np.testing.assert_array_equal(decoded, image)


def test_fastest_playback_is_0_2_seconds():
    from cellab.ui.run_logic import DEFAULT_PLAY_DELAY, PLAY_DELAYS

    assert min(PLAY_DELAYS) == 0.2 and DEFAULT_PLAY_DELAY in PLAY_DELAYS


def test_friendly_date():
    from cellab.ui.run_logic import friendly_date

    assert friendly_date("2026-11-06T01:32:29") == "6 Nov 2026, 01:32"
    assert friendly_date("") == ""
    assert friendly_date("yesterday") == "yesterday"


def test_run_label_is_the_same_everywhere():
    from cellab.ui.run_logic import run_label

    assert (
        run_label("Rule 30", 1, "2026-11-06T02:27:54") == "Rule 30, 1 generation, 6 Nov 2026, 02:27"
    )
