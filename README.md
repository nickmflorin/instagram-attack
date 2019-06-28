# Instattack

System for guessing your friend's Instagram passwords by algorithmically generating password combinations based on patterns configured on a username by username basis.  The purpose of this tool is NOT to brute force attack Instagram, nor will it work for that purpose.  Instead, it can be used for password recovery, messing with friends or in general, playing around with Python3's asyncio implementations.

## Installation

```
$ pip install -r requirements.txt
$ pip install setup.py
```

## Development

This project includes a number of helpers in the `Makefile` to streamline common development tasks.

### Environment Setup

The following demonstrates setting up and working with a development environment:

```
### Create a Virtual ENV for Development

$ make virtualenv
$ source env/bin/activate

### Running CLI Application

$ instatttack --help
$ instattack users login <username> <password_attempt>
$ instattack attack username --pwlimit=10
```

## Background

### Password Generation

Password generation is based on algorithmically combining common strings, numeric patterns and alterations (like `a!` at the end of a password) that a given username might use.  If birthdays are provided, it will even include numeric combinations of their birthday.

