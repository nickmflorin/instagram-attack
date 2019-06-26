from termx import settings


class ConfigSchemaError(Exception):
    """
    [!] Temporarily Deprecated
    ----------------------
    We are not currently using Cerberus schema validation.

    Used to convert Cerberus schema validation errors into more human readable
    series of errors, each designated on a separate line.
    """

    def __init__(self, errors):
        self.errors = errors

    def __str__(self):
        return "\n" + "\n" + self.humanize_errors(self.errors) + "\n"

    def humanize_error_list(self, error_list, prev_key=None):
        errs = []

        for err in error_list:
            if not isinstance(err, str):
                errs.extend(self.convert_errors(err, prev_key=prev_key))
            else:
                errs.append(err)
        return errs

    def convert_errors(self, error_dict, prev_key=None):
        errors = []
        prev_key = prev_key or ""

        for key, value in error_dict.items():
            if prev_key:
                new_key = f"{prev_key}.{key}"
            else:
                new_key = key

            if len(value) == 1 and type(value[0]) is str:
                errors.append((new_key, value[0]))
            else:
                errs = self.humanize_error_list(value, prev_key=new_key)
                errors.extend(errs)
        return errors

    def humanize_errors(self, errors):
        tuples = self.convert_errors(errors)

        humanized = []
        for error in tuples:

            label_formatter = settings.Colors.MED_GRAY
            formatted_attr = settings.Colors.BLACK.format(bold=True)(error[0])
            formatted_error = settings.Colors.ALT_RED.format(bold=True)(error[1].title())

            humanize = (
                f"{label_formatter('Attr')}: {formatted_attr} "
                f"{label_formatter('Error')}: {formatted_error}"
            )
            humanized.append(humanize)
        return "\n".join(humanized)
