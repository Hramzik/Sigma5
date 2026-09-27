import unittest

from machine_art import ALGORITHMS, generate_art


class MachineArtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_all_algorithms_create_images(self):
        for algorithm in ALGORITHMS:
            image = generate_art(algorithm.key, 96, seed=123)
            self.assertEqual(image.size().width(), 96)
            self.assertFalse(image.isNull())

    def test_seed_makes_generation_repeatable(self):
        first = generate_art("color_fields", 64, seed=42)
        second = generate_art("color_fields", 64, seed=42)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
