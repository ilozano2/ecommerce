"""Utilities for end-to-end tests."""


def str2bool(s):
    s = str(s)
    return s.lower() in ('yes', 'true', 't', '1')
