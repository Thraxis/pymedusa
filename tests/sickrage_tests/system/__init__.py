# coding=utf-8
"""
Tests for SickRage system
"""

from __future__ import print_function

import unittest

from restart_tests import RestartTests
from shutdown_tests import ShutdownTests

if __name__ == '__main__':
    print('=====> Running all test in "sickrage_tests.system" <=====')

    TEST_CLASSES = [
        RestartTests,
        ShutdownTests,
    ]

    for test_class in TEST_CLASSES:
        SUITE = unittest.TestLoader().loadTestsFromTestCase(test_class)
        unittest.TextTestRunner(verbosity=2).run(SUITE)
