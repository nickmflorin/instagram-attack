from cement import shell
from datetime import datetime

from instattack.app.exceptions import InstattackError
from .abstract import PrintableMixin


class CustomPrompt(shell.Prompt, PrintableMixin):

    def _validate(self):
        if self.input is None:
            return False
        elif self._meta.options is not None:
            if self._meta.numbered:
                try:
                    self.input = self._meta.options[int(self.input) - 1]
                except (IndexError, ValueError):
                    self.input = None
                    return False
        else:
            if self._meta.case_insensitive is True:
                lower_options = [x.lower() for x in self._meta.options]
                if not self.input.lower() in lower_options:
                    self.input = None
                    return False
            else:
                if self.input not in self._meta.options:
                    self.input = None
                    return False
        return True

    def prompt(self):
        """
        Prompt the user, and store their input as ``self.input``.
        """
        attempt = 0
        while self.input is None:
            if attempt >= int(self._meta.max_attempts):
                if self._meta.max_attempts_exception is True:
                    raise InstattackError(
                        "Maximum attempts exceeded getting valid user input")
                else:
                    return self.input

            attempt += 1

            self._prompt()
            valid = self._validate()
            if not valid:
                self.failure("Invalid Response\n")
            else:
                break

        self.process_input()
        return self.input


class BirthdayPrompt(CustomPrompt):

    class Meta:
        text = "What is the users birthday? (MM/DD/YYYY) (optional)"
        clear = False
        max_attempts = 99
        auto = False

    def _validate(self):
        if self.input is None:
            return True
        try:
            self.input = datetime.strptime(self.input, "%m/%d/%Y")
        except ValueError:
            self.input = None
            return False
        else:
            return True
