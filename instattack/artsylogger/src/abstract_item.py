class AbstractItem(object):
    """
    Used to specify additional properties on both groups of log items or
    individual log items.
    """

    def __init__(
        self,
        formatter=None,
        indent=None,
        line_index=None,
        line_index_formatter=None,
    ):
        self._formatter = formatter
        self._indent = indent

        self._line_index = line_index
        self._line_index_formatter = line_index_formatter

    def indentation(self, record, **kwargs):
        # Component
        if not self._indent:
            return ""
        return " " * self._indent

    def line_index(self, record, **kwargs):
        # Component
        if not self._line_index:
            return ""
        return self._format_component(
            self._line_index,
            formatter=self._line_index_formatter
        )

    def _format_component(self, value, formatter=None):
        if formatter:
            try:
                return formatter(value)
            except TypeError:
                value = "%s" % value
                return formatter(value)
        return value

    def format(self, record):
        created = [comp(record) for comp in self.components if comp(record) is not None]
        formatted = "".join(["%s" % comp for comp in created])
        return formatted

