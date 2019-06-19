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
class Dimensions:

    height: int = 0
    width: int = 0

    @classmethod
    def none(cls):
        return Dimensions()


@dataclass
class Coordinates:

    x1: int = 0
    y1: int = 0
    x2: int = 0
    y2: int = 0

    @classmethod
    def none(cls):
        return Coordinates()


@dataclass
class Padding:

    left: int = 0
    right: int = 0
    top: int = 0
    bottom: int = 0
    all: InitVar[int] = 0

    def __post_init__(self, all):
        if all:
            for attr in ['left', 'right', 'top', 'bottom']:
                setattr(self, attr, all)

    @classmethod
    def none(cls):
        return Padding()

    @classmethod
    def constant(cls, val):
        return Padding(all=val)


@dataclass
class Cell:
    """
    [x] Note: Should be `Columns` or `Rows`, but since those are not defined
    yet we cannot reference those types directly.
    """
    padding: Padding = Padding.none()
    coordinates: Coordinates = Coordinates.none()
    dimensions: Dimensions = Dimensions.none()

    def adopt(self, parent=None):
        self.parent = parent
        if self.children:
            for child in self.children:
                child.adopt(self)

    def measure(self):
        self.dimensions = Dimensions(width=self.width, height=self.height)
        for child in self.children:
            child.measure()

    @property
    def siblings(self):
        if not self.parent:
            return []

        return [
            child for child in self.parent.children
            if child.index != self.index
        ]

    def add_indices(self):
        if self.children:
            for i, child in enumerate(self.children):
                child.add_index(i)

    def add_index(self, index=None):
        self.index = index
        self.add_indices()

    @property
    def __dict__(self):
        return {
            'padding': self.padding.__dict__,
            'coordinates': self.coordinates.__dict__,
            'dimensions': self.dimensions.__dict__,
        }


@dataclass
class Column(Cell):
    """
    [x] Note: Should be `Columns` or `Rows`, but since those are not defined
    yet we cannot reference those types directly.
    """
    rw: InitVar[int] = 1
    rows: typing.Optional[typing.List[typing.Any]] = field(default_factory=list)

    parent: typing.Any = field(default=None, repr=False)
    index: int = field(init=False)

    def __post_init__(self, rw):
        self._rw = rw
        self.dimensions = Dimensions(height=self.height, width=self.width)

    @property
    def width(self):
        sibling_ratio = self._rw / (self._rw + sum([sib._rw for sib in self.siblings]))
        return sibling_ratio * self.parent.width

    @property
    def height(self):
        return self.parent.height

    @property
    def children(self):
        return self.rows

    @property
    def __dict__(self):
        data = super(Column, self).__dict__
        data.update(
            index=self.index,
            rows=[row.__dict__ for row in self.rows]
        )
        return data


@dataclass
class Row(Cell):
    """
    [x] Note: Should be `Columns` or `Rows`, but since those are not defined
    yet we cannot reference those types directly.
    """
    rh: InitVar[int] = 1
    columns: typing.Optional[typing.List[typing.Any]] = None

    parent: typing.Any = field(default=None, repr=False)
    index: int = field(init=False)

    def __post_init__(self, rh):
        self._rh = rh

    @property
    def height(self):
        sibling_ratio = self._rh / (self._rh + sum([sib._rh for sib in self.siblings]))
        return sibling_ratio * self.parent.height

    @property
    def width(self):
        return self.parent.width

    @property
    def children(self):
        return self.columns

    @property
    def __dict__(self):
        data = super(Row, self).__dict__
        data.update(
            index=self.index,
            columns=[col.__dict__ for col in self.columns]
        )
        return data


@dataclass
class Grid(Cell):
    """
    [x] TODO:
    --------
    Right now, we are thinking in terms of a traditional HTML table
    where the <tr> elements contain the <td> elements (so the top level
    Cell contains rows, each of which contains columns).

    We should make this more flexible in the future.
    """
    height: InitVar[int] = 0
    width: InitVar[int] = 0
    rows: typing.List[Row] = field(default_factory=list)

    def __post_init__(self, height, width):
        self.dimensions = Dimensions(height=height, width=width)
        self.add_indices()
        self.adopt()
        self.measure()

    @property
    def children(self):
        return self.rows

    @property
    def __dict__(self):
        data = super(Grid, self).__dict__
        data.update(
            dimensions=self.dimensions.__dict__,
            rows=[row.__dict__ for row in self.rows]
        )
        return data


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

