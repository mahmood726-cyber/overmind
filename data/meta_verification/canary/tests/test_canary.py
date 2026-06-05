import unittest

from canary_module import VALUE, identity

class CanaryTests(unittest.TestCase):
    def test_value_is_42(self):
        self.assertEqual(VALUE, 42)

    def test_identity(self):
        self.assertEqual(identity(7), 7)

if __name__ == '__main__':
    unittest.main()
