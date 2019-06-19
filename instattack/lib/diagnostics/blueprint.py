from dataclasses import dataclass, InitVar, field
import typing


def width_in_available(w, available, padding_right=None, padding_left=None):
    padding_right = padding_right or 0
    padding_left = padding_left or 0

    if type(w) is float:
        if w <= 1.0:
            theoretical = int(w * available)
            padded = theoretical - 2.0 * (padding_right + padding_left)

            assert padded > 0
            return int(padded)

    padded = theoretical - 2.0 * (padding_right + padding_left)
    assert w < padded


def width_in_parent(w, parent, padding_right=None, padding_left=None):
    padding_right = padding_right or 0
    padding_left = padding_left or 0

    _, leftover = parent.getmaxyx()

    if type(w) is float:
        if w <= 1.0:
            # Width is a Ratio
            theoretical_width = int(w * leftover)
            padded = theoretical_width - 2.0 * (padding_right + padding_left)

            assert padded > 0
            return int(padded)
    return int(w)


def height_in_parent(h, parent, vertical_padding=1):
    leftover, _ = parent.getmaxyx()

    if type(h) is float:
        if h <= 1.0:
            # Height is a Ratio
            theoretical_height = int(h * leftover)
            padded = theoretical_height - 2.0 * vertical_padding

            assert padded > 0
            return int(padded)
    return int(h)


@dataclass
class BluePrint:

    w: InitVar[typing.Union[int, float]]
    width: int = field(init=False)

    h: InitVar[typing.Union[int, float]]
    height: int = field(init=False)

    parent: typing.Any
    x: int = 1
    y: int = 1

    def __post_init__(self, w, h):
        self.height = height_in_parent(h, self.parent, vertical_padding=self.y)
        self.width = width_in_parent(w, self.parent, padding_left=self.x)

    @property
    def y2(self):
        return self.y + self.height

    @property
    def y1(self):
        return self.y

    @property
    def x2(self):
        return self.x + self.width

    @property
    def x1(self):
        return self.x

    @property
    def coordinates(self):
        """
        Represents the coordinates inside the parent's frame.
        """
        return Coordinates(
            x1=self.x1,
            y1=self.y1,
            x2=self.x2,
            y2=self.y2
        )

    @property
    def dimensions(self):
        return Dimensions(
            width=self.width,
            height=self.height
        )

    def duplicate_right(self, w, padding=1):
        """
        Creates a blueprint with the same height to the right of this panel,
        separated by `padding` and extending a total width `w`.
        """
        _, leftover = self.parent.getmaxyx()
        width = width_in_available(w, leftover - self.x2, padding_right=padding)

        bp = BluePrint(
            # This is not going to work properly.
            w=width,
            h=self.height,
            x=self.x2,
            y=self.y,
            parent=self.parent
        )
        return bp

    def draw(self):
        return self.parent.subwin(self.height, self.width, self.y1, self.x1)

    @classmethod
    def generate_grid(cls, grid_array, padding=1):
        """
        Provided an array specifying the relative dimensions of each row and
        column, generates blueprints for panels in the grid with the provided
        padding.

        [x] TODO:
        --------
        We should make the padding applicable on a per cell basis, with the global
        override.

        We should use more of a dictionary structure to specify the cells in
        each column and row.
        """
        # We Might Not Need Top Level `Rows` Attribute...
        grid = Grid(
            height=100,
            width=100,
            padding=Padding(all=1),
            rows=[
                Row(
                    padding=Padding.constant(1),
                    rh=3,
                    columns=[
                        Column(rw=1),
                        Column(rw=1),
                    ]
                ),
                Row(
                    padding=Padding.constant(1),
                    rh=2,
                    columns=[
                        Column(rw=1),
                        Column(rw=1),
                    ]
                ),
                Row(
                    padding=Padding.constant(1),
                    rh=1,
                    columns=[
                        Column(rw=1),
                        Column(rw=1),
                    ]
                )
            ]
        )
        grid.add_indices()
        grid.adopt()

