from __future__ import absolute_import


class ProxyException(Exception):
    pass


class InvalidFileLine(ProxyException):
    def __init__(self, line):
        self.line = line

    def __str__(self):
        return f"The following line is invalid: \n {self.line}"
