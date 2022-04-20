#!/usr/bin/env python3

import sys
from xml.sax.saxutils import escape
from enum import Enum
from typing import Optional, Tuple, Sequence, Mapping, Union, TypedDict

import yaml


KEY_W = 55
KEY_H = 50
KEY_RX = 6
KEY_RY = 6
INNER_PAD_W = 2
INNER_PAD_H = 2
OUTER_PAD_W = KEY_W / 2
OUTER_PAD_H = KEY_H
KEYSPACE_W = KEY_W + 2 * INNER_PAD_W
KEYSPACE_H = KEY_H + 2 * INNER_PAD_H
LINE_SPACING = 18

STYLE = """
    svg {
        font-family: SFMono-Regular,Consolas,Liberation Mono,Menlo,monospace;
        font-size: 14px;
        font-kerning: normal;
        text-rendering: optimizeLegibility;
        fill: #24292e;
    }

    rect {
        fill: #f6f8fa;
        stroke: #d6d8da;
        stroke-width: 1;
    }

    .held {
        fill: #fdd;
    }

    .combo {
        fill: #cdf;
    }
"""


class KeyType(Enum):
    NORMAL = ""
    HELD = "held"
    COMBO = "combo"


class Key(TypedDict):
    tap: str
    hold: Optional[str]
    type: KeyType


KeySpec = Union[str, Key]
ComboSpec = TypedDict("ComboSpec", {"positions": Sequence[int], "key": KeySpec})
KeyRow = Sequence[KeySpec]
KeyBlock = Sequence[KeyRow]
Layer = TypedDict(
    "Layer",
    {
        "left": KeyBlock,
        "right": KeyBlock,
        "left-thumbs": KeyRow,
        "right-thumbs": KeyRow,
        "combos": Sequence[ComboSpec],
    },
)


class Keymap:
    def __init__(self, split: bool, rows: int, columns: int, thumbs: Optional[int], layers: Mapping[str, Layer]):
        self.split = split
        self.rows = rows
        self.columns = columns
        self.thumbs = thumbs
        self.layers = layers

        assert self.split
        if self.thumbs is not None:
            assert self.thumbs <= self.columns

        self.block_w = self.columns * KEYSPACE_W
        self.block_h = (self.rows + (1 if self.thumbs else 0)) * KEYSPACE_H
        self.layer_w = 2 * self.block_w + OUTER_PAD_W
        self.layer_h = self.block_h
        self.board_w = self.layer_w + 2 * OUTER_PAD_W
        self.board_h = len(layers) * self.layer_h + (len(layers) + 1) * OUTER_PAD_H

    @staticmethod
    def _draw_rect(x: float, y: float, w: float, h: float, cls: str):
        print(f'<rect rx="{KEY_RX}" ry="{KEY_RY}" x="{x}" y="{y}" ' f'width="{w}" height="{h}" class="{cls}" />')

    @staticmethod
    def _draw_text(x: float, y: float, text: str, small=False, bold=False):
        print(f'<text text-anchor="middle" dominant-baseline="middle" x="{x}" y="{y}"')
        if small:
            print(' font-size="80%"')
        if bold:
            print(' font-weight="bold"')
        print(f'>{escape(text)}</text>')

    @staticmethod
    def _keyspec_to_props(key_spec: KeySpec) -> Tuple[str, Optional[str], Optional[str]]:
        if isinstance(key_spec, str):
            key = {"tap": key_spec}
        else:
            key = Key(key_spec)
        return key["tap"], key.get("hold"), key.get("type", KeyType.NORMAL.value)

    def print_key(self, x: float, y: float, key_spec: KeySpec):
        tap, hold, kc = self._keyspec_to_props(key_spec)
        tap_words = tap.split()
        self._draw_rect(x + INNER_PAD_W, y + INNER_PAD_H, KEY_W, KEY_H, kc)

        y_tap = y + (KEYSPACE_H - (len(tap_words) - 1) * LINE_SPACING) / 2
        for word in tap_words:
            self._draw_text(x + KEYSPACE_W / 2, y_tap, word)
            y_tap += LINE_SPACING
        if hold:
            y_hold = y + KEYSPACE_H - LINE_SPACING / 2
            self._draw_text(x + KEYSPACE_W / 2, y_hold, hold, small=True)

    def print_combo(self, x: float, y: float, combo_spec: ComboSpec):
        pos_idx = combo_spec["positions"]

        # no combos with > 2 positions or in thumb keys
        assert (len(pos_idx) == 2 and
                all(pos < self.rows * self.columns * (2 if self.split else 1) for pos in pos_idx))
        cols = [p % ((2 if self.split else 1) * self.columns) for p in pos_idx]
        rows = [p // ((2 if self.split else 1) * self.columns) for p in pos_idx]
        x_pos = [x + c * KEYSPACE_W + (OUTER_PAD_W if self.split and c >= self.columns else 0) for c in cols]
        y_pos = [y + r * KEYSPACE_H for r in rows]
        tap, _, _ = self._keyspec_to_props(combo_spec["key"])

        x_mid, y_mid = sum(x_pos) / len(pos_idx), sum(y_pos) / len(pos_idx)

        self._draw_rect(
            x_mid + INNER_PAD_W + KEY_W / 4, y_mid + INNER_PAD_H + KEY_H / 4, KEY_W / 2, KEY_H / 2, KeyType.COMBO.value
        )
        self._draw_text(x_mid + KEYSPACE_W / 2, y_mid + INNER_PAD_H + KEY_H / 2, tap, small=True)

    def print_row(self, x: float, y: float, row: KeyRow, is_thumbs: bool = False):
        assert len(row) == (self.columns if not is_thumbs else self.thumbs)
        for key_spec in row:
            self.print_key(x, y, key_spec)
            x += KEYSPACE_W

    def print_block(self, x: float, y: float, block: KeyBlock):
        assert len(block) == self.rows
        for row in block:
            self.print_row(x, y, row)
            y += KEYSPACE_H

    def print_layer(self, x: float, y: float, name: str, layer: Layer):
        self._draw_text(KEY_W / 2, y - KEY_H / 2, f"{name}:", bold=True)
        self.print_block(x, y, layer["left"])
        self.print_block(
            x + self.block_w + OUTER_PAD_W,
            y,
            layer["right"],
        )
        if self.thumbs:
            self.print_row(
                x + (self.columns - self.thumbs) * KEYSPACE_W,
                y + self.rows * KEYSPACE_H,
                layer["left-thumbs"],
                is_thumbs=True,
            )
            self.print_row(
                x + self.block_w + OUTER_PAD_W, y + self.rows * KEYSPACE_H, layer["right-thumbs"], is_thumbs=True
            )
        if "combos" in layer:
            for combo_spec in layer["combos"]:
                self.print_combo(x, y, combo_spec)

    def print_board(self):
        print(
            f'<svg width="{self.board_w}" height="{self.board_h}" viewBox="0 0 {self.board_w} {self.board_h}" xmlns="http://www.w3.org/2000/svg">'
        )
        print(f"<style>{STYLE}</style>")

        x, y = OUTER_PAD_W, 0
        for name, layer in self.layers.items():
            y += OUTER_PAD_H
            self.print_layer(x, y, name, layer)
            y += self.layer_h

        print("</svg>")


def main():
    with open(sys.argv[1], "rb") as f:
        data = yaml.safe_load(f)
    km = Keymap(**data["layout"], layers=data["layers"])
    km.print_board()


if __name__ == "__main__":
    main()
