#!/usr/bin/env python3
"""Compatibility test runner forwarding to tests/test_drawing.py"""
import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tests.test_drawing import *

if __name__ == "__main__":
    unittest.main()
