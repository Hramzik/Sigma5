import unittest

from puzzle import Puzzle


class PuzzleTests(unittest.TestCase):
    def test_only_adjacent_moves_are_allowed(self):
        game = Puzzle(3)
        self.assertTrue(game.move(5))
        self.assertFalse(game.move(0))

    def test_shuffle_stays_solvable_and_not_solved(self):
        for size in range(2, 7):
            game = Puzzle(size)
            game.shuffle(steps=80)
            self.assertEqual(sorted(game.tiles), list(range(size * size)))
            self.assertFalse(game.is_solved())

    def test_move_back_restores_solved_state(self):
        game = Puzzle(3)
        self.assertTrue(game.move(5))
        self.assertTrue(game.move(8))
        self.assertTrue(game.is_solved())

    def test_size_validation(self):
        with self.assertRaises(ValueError):
            Puzzle(1)
        with self.assertRaises(ValueError):
            Puzzle(9)


if __name__ == "__main__":
    unittest.main()
