from artsylogger import Format, colors


class Colors:

    GREEN = colors.fg('#28a745')
    LIGHT_GREEN = colors.fg('DarkOliveGreen3')

    RED = colors.fg('#dc3545')
    ALT_RED = colors.fg('Red1')
    LIGHT_RED = colors.fg('IndianRed')

    YELLOW = colors.fg('Gold3')
    LIGHT_YELLOW = colors.fg('LightYellow3')

    BLUE = colors.fg('#007bff')
    DARK_BLUE = colors.fg('#336699')
    TURQOISE = colors.fg('#17a2b8')
    ALT_BLUE = colors.fg('CornflowerBlue')
    ALT_BLUE_2 = colors.fg('RoyalBlue1')

    INDIGO = colors.fg('#6610f2')
    PURPLE = colors.fg('#364652')
    TEAL = colors.fg('#20c997')
    ORANGE = colors.fg('#EDAE49')

    GRAY = colors.fg('#393E41')
    ALT_GRAY = colors.fg('#6c757d')
    MED_GRAY = colors.fg('Grey30')
    LIGHT_GRAY = colors.fg('Grey58')
    EXTRA_LIGHT_GRAY = colors.fg('Grey78')

    BLACK = colors.fg('#232020')
    BROWN = colors.fg('#493B2A')
    HEAVY_BLACK = colors.black


class Icons:

    SKULL = "☠"
    CROSS = "✘"
    CHECK = "✔"
    DONE = "\u25A3"
    TACK = "📌"
    GEAR = "⚙️ "
    CROSSING = "🚧"
    NOTSET = ""


class Formats:

    class Text:

        NORMAL = Format(Colors.BLACK)
        EMPHASIS = Format(Colors.HEAVY_BLACK)

        PRIMARY = Format(Colors.GRAY)
        MEDIUM = Format(Colors.MED_GRAY)
        LIGHT = Format(Colors.LIGHT_GRAY)
        EXTRA_LIGHT = Format(Colors.EXTRA_LIGHT_GRAY)

        FADED = Format(Colors.LIGHT_YELLOW)

        @classmethod
        def get_hierarchal_format(cls, level=1):
            formats = [
                cls.NORMAL,
                cls.PRIMARY,
                cls.MEDIUM,
                cls.LIGHT,
            ]
            try:
                return formats[level - 1]
            except IndexError:
                return cls.Text.LIGHT,

    class State:

        class Icon:

            FAIL = Icons.CROSS
            SUCCESS = Icons.CHECK
            WARNING = Icons.CROSS
            NOTSET = Icons.NOTSET

        class Color:

            FAIL = Colors.RED
            SUCCESS = Colors.GREEN
            WARNING = Colors.YELLOW
            NOTSET = Colors.GRAY

        FAIL = Format(Color.FAIL, icon=Icon.FAIL)
        SUCCESS = Format(Color.SUCCESS, icon=Icon.SUCCESS)
        WARNING = Format(Color.WARNING, icon=Icon.WARNING)
        NOTSET = Format(Color.NOTSET, icon=Icon.NOTSET)

        @classmethod
        def state(cls, *args, success=False, fail=False, warning=False):
            if len(args) == 1:
                return args[0]
            return (success, fail, warning)

        @classmethod
        def get_format_for(cls, *args, **kwargs):
            state = cls.state(*args, **kwargs)
            return cls.FORMATS[state]

        @classmethod
        def get_icon_for(cls, *args, **kwargs):
            state = cls.state(*args, **kwargs)
            return cls.Icon.ICONS[state]

        @classmethod
        def get_color_for(cls, *args, **kwargs):
            state = cls.state(*args, **kwargs)
            return cls.Color.COLORS[state]

    class Pointer:

        POINTER_1 = Format(Colors.BLACK)
        POINTER_2 = Format(Colors.GRAY)
        POINTER_3 = Format(Colors.MED_GRAY)

        @classmethod
        def get_hierarchal_format(cls, level=1):
            formats = [
                cls.POINTER_1,
                cls.POINTER_2,
                cls.POINTER_3,
            ]
            try:
                return formats[level - 1]
            except IndexError:
                return cls.POINTER_3

    class Wrapper:

        INDEX = Format(Colors.BLACK, wrapper="[%s]", format_with_wrapper=False)
