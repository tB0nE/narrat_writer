import os
import unittest
from unittest.mock import patch, mock_open

from src.server.utils import update_env_lines

class TestSecurityFix(unittest.TestCase):
    def test_newline_injection_sanitization(self):
        env_lines = ["EXISTING_VAR=existing_value\n"]
        key = "API_KEY"
        vulnerable_value = "somekey\nINJECTED_VAR=injected_value"

        new_lines, sanitized_value = update_env_lines(env_lines, key, vulnerable_value)

        # Check that the sanitized value does not contain newlines
        self.assertNotIn("\n", sanitized_value)
        self.assertNotIn("\r", sanitized_value)

        # Check that no new lines were added to env_lines other than the intended one
        # Expected env_lines: ["EXISTING_VAR=existing_value\n", "API_KEY=somekeyINJECTED_VAR=injected_value\n"]
        self.assertEqual(len(new_lines), 2)
        self.assertEqual(new_lines[1], "API_KEY=somekeyINJECTED_VAR=injected_value\n")

    def test_carriage_return_injection_sanitization(self):
        env_lines = []
        key = "EDITOR"
        vulnerable_value = "vim\rOTHER_VAR=other_value"

        new_lines, sanitized_value = update_env_lines(env_lines, key, vulnerable_value)

        self.assertNotIn("\r", sanitized_value)
        self.assertEqual(new_lines[0], "EDITOR=vimOTHER_VAR=other_value\n")

    def test_update_existing_variable_with_injection(self):
        env_lines = ["API_KEY=oldkey\n", "OTHER=value\n"]
        key = "API_KEY"
        vulnerable_value = "newkey\nINJECTED=true"

        new_lines, sanitized_value = update_env_lines(env_lines, key, vulnerable_value)

        self.assertEqual(len(new_lines), 2)
        self.assertEqual(new_lines[0], "API_KEY=newkeyINJECTED=true\n")

if __name__ == "__main__":
    unittest.main()
