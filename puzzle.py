from __future__ import annotations

import random
from typing import Iterable


class Puzzle:
    """State and rules for an N x N sliding puzzle."""

    def __init__(self, size: int = 4) -> None:
        self.size = self._validate_size(size)
        self.tiles = list(range(1, self.size * self.size)) + [0]

    @staticmethod
    def _validate_size(size: int) -> int:
        if not 2 <= size <= 8:
            raise ValueError("Размер поля должен быть от 2 до 8")
        return size

    @property
    def empty(self) -> int:
        return self.tiles.index(0)

    def is_solved(self) -> bool:
        return self.tiles == list(range(1, self.size * self.size)) + [0]

    def move(self, index: int) -> bool:
        if not 0 <= index < len(self.tiles):
            return False
        empty = self.empty
        if abs(index // self.size - empty // self.size) + abs(index % self.size - empty % self.size) != 1:
            return False
        self.tiles[empty], self.tiles[index] = self.tiles[index], self.tiles[empty]
        return True

    def shuffle(self, steps: int | None = None) -> None:
        """Shuffle via legal moves, guaranteeing a solvable board."""
        count = steps or self.size * self.size * 30
        self.tiles = list(range(1, self.size * self.size)) + [0]
        previous_empty = -1
        for _ in range(count):
            empty = self.empty
            candidates = self.neighbors(empty)
            if previous_empty in candidates and len(candidates) > 1:
                candidates.remove(previous_empty)
            chosen = random.choice(candidates)
            self.tiles[empty], self.tiles[chosen] = self.tiles[chosen], self.tiles[empty]
            previous_empty = empty
        if self.is_solved():
            self.move(self.neighbors(self.empty)[0])

    def neighbors(self, index: int) -> list[int]:
        row, col = divmod(index, self.size)
        result = []
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            r, c = row + dr, col + dc
            if 0 <= r < self.size and 0 <= c < self.size:
                result.append(r * self.size + c)
        return result

    def set_size(self, size: int) -> None:
        self.size = self._validate_size(size)
        self.tiles = list(range(1, size * size)) + [0]
