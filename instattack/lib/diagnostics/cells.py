from dataclasses import dataclass, InitVar, field, asdict, fields
import math
import typing


def simple_descriptor(obj_class):

    class Descriptor(object):

        def __get__(self, obj, objtype):
            return obj_class

    return Descriptor()


def raise_invalid_value(attr):
    """
    [x] TODO:
    --------
    This should be more of a runtime error, but we might want to raise this
    as an exception built into the app if we ever exposure this as an API.
    """
    raise ValueError('Invalid value specified for %s.' % attr)


def round_value(value):

    decimal = float(value) % 1
    if decimal != 0.0:
        if decimal < 0.5:
            return int(value)
        else:
            return math.ceil(value)
    else:
        return int(value)


def find_optimal_size(screen, grid):
    """
    Since we use relative integer values to specify the relative width of
    columns to their siblings and relative height of rows to their siblings,
    the larger interval sizes of the terminal (rows, columns) are not small
    like pixels, and rounding float results of calculating widths and heights
    based on the relative ratio can sometimes lead to results that draw outside
    the screen bounds by very minimal amounts, but still enough to cause an error.

    In order to alleviate that, we want to find the largest optimal size that
    is not greater than the screen size that accomodates the relative size
    ratios with the least amount of rounding.

    Given Screen with Size (height=H, width=W)

    Consider (3) rows with values rh as follows:
        >>> [1, 2, 3]

    Then, the row heights will be:
        >>> [ (1/6) H, (2/6) H, (3/6) H ]

    To avoid any rounding, we would want to find the largest value H` such that
    H` <= H and H` % 6 == 0.

    This becomes more complicated for nesting...

    Consider a Tree Like the Following:

        R1: rh = 1
        R2: rh = 2
            C1: rw = 2
            C2: rw = 2
        R3: rh = 4
            C1: rw = 1
            C2: rw = 3
                R1: rh = 5
                R2: rh = 1


    To ensure we have integer results for the relative row heights, we would
    need to find the largest H` such that H` is can be divided into integer
    value heights for all rows and their sub-rows.

    First, we have the top level:
        >>> [(1/7), (2/7), (4/7)]

    However, the last Row, R3 (4/7) is split into [(1/6), (5/6)], which we also want
    to divide evenly. The easiest way find this value is to find the value H`
    such that H` < H and H` is divisible by both 7 and 6*7 = 42, or just 42.

    [x] NOTE:
    --------
    For the above, there maybe numbers H that are divisble by 7 where (4/7) * H
    is also divisible by 6, but H is not divisible by 42.  This might lead to
    better results, but would be complicated to find, so we will stick to the simpler
    solution.

    [!] IMPORTANT:
    -------------
    Also, ideally we want numbers to be even, so that padding values of 1 and 2
    which would be common would work.

    Again, this is not a perfect solution, but will be OK for the time being.
    It is still important to avoid using relative sizes that are complicated
    or narrow/small.
    """

    # For now, we will limit how many levels deep we go to avoid complication,
    # but eventually might want to make this recursive.
    def get_for_obj(obj):
        rh_values = []
        for row in obj.rows:
            rh_values.append(row._rh)

            if row.columns:
                for col in row.columns:
                    nested_rh_values = get_for_obj(col)
                    rh_values.append(nested_rh_values)
        return rh_values


    return get_for_obj(grid)


@dataclass
class IntegeredMixin:

    all: InitVar[int] = None

    @classmethod
    def none(cls):
        """
        Verbose method for returning an instance of the dataclass with all
        0 values.
        """
        return cls()

    @classmethod
    def zero(cls):
        return cls()

    @classmethod
    def constant(cls, val):
        """
        Verbose method for returning an instance of the dataclass with all values
        set to a constant.
        """
        return Padding(all=val)

    def __post_init__(self, all):
        """
        IntegeredMixin is primarily used for the __post_init__ functionality,
        which does the following:

            (1) Force type cases to integers for safety, raising exceptions where
            invalid values supplied.
            (2) Allows `all` to be specified as a parameter which sets all values
                to the constant value specified by `all`.

        For curses, all dimensions, coordinates and distances need to be specified
        in terms of the number of columns or rows, which requires integer
        coercion.

        To be safe, for objects with all integer properties that default to 0
        (which will be common for this) this mixin will force the values to be
        integers on initialization so we don't have to always explicitly typecast.
        """
        if all is not None:
            for fld in fields(self):
                if fld.init:
                    setattr(self, fld.name, all)

        for fld in fields(self):
            val = getattr(self, fld.name)
            if val is None:
                raise_invalid_value(fld.name)

            try:
                # val = round_value(val)
                val = round_value(val)
            except ValueError:
                raise_invalid_value(fld.name)
            else:
                setattr(self, fld.name, val)


@dataclass
class Dimensions(IntegeredMixin):

    height: int = 0
    width: int = 0


@dataclass
class Coordinates(IntegeredMixin):

    x1: int = 0
    y1: int = 0
    x2: int = 0
    y2: int = 0


@dataclass
class Padding(IntegeredMixin):

    left: int = 0
    right: int = 0
    top: int = 0
    bottom: int = 0

    v: InitVar[int] = None
    h: InitVar[int] = None

    def __post_init__(self, all, v, h):
        if v:
            self.top = self.bottom = v
        if h:
            self.left = self.right = h
        super(Padding, self).__post_init__(all)


@dataclass
class Cell:
    """
    [x] Note: Should be `Columns` or `Rows`, but since those are not defined
    yet we cannot reference those types directly.
    """
    padding: Padding = Padding.none()
    coordinates: Coordinates = Coordinates.none()
    absolute_coordinates: Coordinates = Coordinates.none()
    dimensions: Dimensions = Dimensions.none()

    def _adopt_children(self):

        def get_siblings(child):
            return [
                other_child for other_child in self.children
                if other_child != child
            ]

        children = self.children()

        [setattr(child, 'parent', self) for child in children]
        [setattr(child, 'index', i) for i, child in enumerate(children)]

        for child in children:
            siblings = children[:]
            siblings = [ch for ch in siblings if ch.index != child.index]
            setattr(child, 'siblings', siblings)

    def measure(self):
        self.dimensions = Dimensions(width=self.width, height=self.height)

        children = self.children()
        for child in children:
            child.measure()

    @property
    def __dict__(self):
        return {
            'padding': self.padding.__dict__,
            'coordinates': self.coordinates.__dict__,
            'dimensions': self.dimensions.__dict__,
        }

    def children_windows(self, window, border=None):
        windows = []
        children = self.children()
        if children:
            for child in children:
                win = child.draw(window, border=border)
                # win.refresh()
                windows.append(win)
        return windows

    def draw(self, window, border=None):
        windows = []

        base_window = window.subwin(
            self.dimensions.height,
            self.dimensions.width,
            self.coordinates.y1,
            self.coordinates.x1
        )
        base_window.addstr(2, 2, f"{self.__class__.__name__}: {self.index}")

        if border:
            base_window.attron(border)
            base_window.box()
            base_window.attroff(border)

        base_window.refresh()

        windows = [base_window]
        windows += [self.children_windows(base_window, border=border)]
        return windows


@dataclass
class Column(Cell):
    """
    [x] Note: Should be `Columns` or `Rows`, but since those are not defined
    yet we cannot reference those types directly.
    """
    rw: InitVar[int] = 1
    rows: typing.Optional[typing.List[typing.Any]] = field(default_factory=list)
    siblings: typing.Optional[typing.List[typing.Any]] = field(default_factory=list)

    parent: typing.Any = field(default=None, repr=False)
    index: int = field(init=False, repr=False)

    def __post_init__(self, rw):
        self._rw = rw
        self._adopt_children()

    @property
    def _width_ratio(self):
        """
        When specifying the children of a specific Row or Column, we specify
        an integer number that reflects the relative height or width compared
        to the siblings.

        Ex:
            >>> [sibling._rw for sibling in siblings]
            >>> [1, 2, 5]

        Ratios: [0.125, 0.25, 0.375]
        """
        width_ratio = self._rw / (self._rw + sum([sib._rw for sib in self.siblings]))
        return width_ratio
        # We are going to do more rounding earlier rather than later to minimize
        # the offsetting effect of large increments (rows/columns) being used
        # instead of something like pixels.
        width_ratio = 100.0 * width_ratio
        width_ratio = round_value(width_ratio)
        return width_ratio / 100.0

    def _measure(self):
        """
        [x] TODO:
        --------
        Have properties for coordinates that are both relative to parent and
        relative to the top level grid.

        [x] TODO:
        --------
        We have to add a spacing property to parents to allow them to space
        out the children more easily.  Maybe even margins instead?

        [!] Temporarily using spacing of 2.0
        """
        SPACING = 1  # Hard Code For Now

        total_spacing = SPACING * (len(self.siblings) - 1)

        available_width = (
            self.parent.dimensions.width
            - self.parent.padding.left
            - self.parent.padding.right
            - total_spacing)

        available_height = (
            self.parent.dimensions.height
            - self.parent.padding.top
            - self.parent.padding.bottom)

        self.dimensions = Dimensions(
            width=self._width_ratio * available_width - 1.0,
            height=available_height,
        )

        initial_x = self.parent.padding.left + self.parent.coordinates.x1
        initial_y = self.parent.padding.top + self.parent.coordinates.y1

        if self.index != 0:

            # REVIEW
            # THIS IS GOING TO CAUSE PROBLEMS (I THINK)
            # THINK ABOUT NESTED NESTED CHILDREN AND SPACING OF PARENT ELEMENTS
            cum_sibling_width = sum([sibling.dimensions.width
                for sibling in self.siblings[:self.index]])

            initial_x = self.siblings[self.index - 1].coordinates.x1
            initial_x += self.siblings[self.index - 1].dimensions.width
            initial_x += SPACING
            """
            [x] Review: Not sure why this is having an effect, but we get better
            results when doing:
            >>> cum_spacing = spacing
                    vs.
            >>> cum_spacing = spacing * self.index

            [x] Review: Not sure why this is having an effect, but we get better
            results when doing:
            >>> initial_y += cum_spacing + cum_sibling_height - self.parent.padding.left
                    vs.
            >>> initial_y += cum_spacing + cum_sibling_height

            Subtracting the padding at the left doesn't make a lot of sense.
            """
            # cum_spacing = SPACING
            # initial_x += cum_spacing + cum_sibling_width

        self.coordinates = Coordinates(
            x1=initial_x,
            x2=initial_x + available_width,
            y1=initial_y,
            y2=initial_y + available_height,
        )

        self._measure_children()

    def _measure_children(self):
        children = self.children()
        for child in children:
            child._measure()

    def children(self):
        return self.rows

    @property
    def __dict__(self):
        data = super(Column, self).__dict__
        children = self.children()
        data.update(
            rows=[row.__dict__ for row in children]
        )
        return data


@dataclass
class Row(Cell):
    """
    [x] Note: Should be `Columns` or `Rows`, but since those are not defined
    yet we cannot reference those types directly.
    """
    rh: InitVar[int] = 1
    columns: typing.Optional[typing.List[typing.Any]] = field(default_factory=list)
    siblings: typing.Optional[typing.List[typing.Any]] = field(default_factory=list)

    parent: typing.Any = field(default=None, repr=False)
    index: int = field(init=False, repr=False)

    def __post_init__(self, rh):
        self._rh = rh
        self._adopt_children()

    @property
    def _height_ratio(self):
        """
        When specifying the children of a specific Row or Column, we specify
        an integer number that reflects the relative height or width compared
        to the siblings.

        Ex:
            >>> [sibling._rh for sibling in siblings]
            >>> [1, 2, 5]

        Ratios: [0.125, 0.25, 0.375]
        """
        height_ratio = self._rh / (self._rh + sum([sib._rh for sib in self.siblings]))

        # We are going to do more rounding earlier rather than later to minimize
        # the offsetting effect of large increments (rows/columns) being used
        # instead of something like pixels.
        height_ratio = 100.0 * height_ratio
        height_ratio = round_value(height_ratio)
        return height_ratio / 100.0

    def _measure(self):
        """
        [x] TODO:
        --------
        Have properties for coordinates that are both relative to parent and
        relative to the top level grid.

        [x] TODO:
        --------
        We have to add a spacing property to parents to allow them to space
        out the children more easily.  Maybe even margins instead?

        [!] Temporarily using spacing of 2.0
        """
        SPACING = 1  # Hard Code For Now

        total_spacing = SPACING * (len(self.siblings) - 1)

        available_width = round_value(
            self.parent.dimensions.width
            - self.parent.padding.left
            - self.parent.padding.right)

        available_height = round_value(
            self.parent.dimensions.height
            - self.parent.padding.top
            - self.parent.padding.bottom
            - total_spacing)

        self.dimensions = Dimensions(
            width=available_width,
            height=self._height_ratio * available_height
        )

        initial_x = self.parent.padding.left + self.parent.coordinates.x1
        initial_y = self.parent.padding.top + self.parent.coordinates.y1

        if self.index != 0:
            cum_sibling_height = sum([sibling.dimensions.height
                for sibling in self.siblings[:self.index]])

            """
            [x] Review: Not sure why this is having an effect, but we get better
            results when doing:
            >>> cum_spacing = spacing
                    vs.
            >>> cum_spacing = spacing * self.index

            [x] Review: Not sure why this is having an effect, but we get better
            results when doing:
            >>> initial_y += cum_spacing + cum_sibling_height - self.parent.padding.top
                    vs.
            >>> initial_y += cum_spacing + cum_sibling_height

            Subtracting the padding at the top doesn't make a lot of sense.
            """
            cum_spacing = SPACING
            initial_y += cum_spacing + cum_sibling_height - self.parent.padding.top

        self.coordinates = Coordinates(
            x1=initial_x,
            x2=initial_x + available_width,
            y1=initial_y,
            y2=initial_y + available_height,
        )

        self._measure_children()

    def _measure_children(self):
        children = self.children()
        for child in children:
            child._measure()

    def children(self):
        return self.columns

    @property
    def __dict__(self):
        data = super(Row, self).__dict__
        children = self.children()
        data.update(
            columns=[col.__dict__ for col in children]
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

    # We use descriptors for these so we can do things like:
    # >>> Grid.Padding.constant(2)
    # This will hopefully make for a smoother API if we ever want to treat it
    # that way.
    Padding = simple_descriptor(Padding)
    Dimensions = simple_descriptor(Dimensions)
    Row = simple_descriptor(Row)
    Column = simple_descriptor(Column)

    def __post_init__(self, height, width):
        """
        [x] NOTE:
        --------
        We cannot perform any measurement methods on the individual Row and Cell
        objects in __post_init__ because the recursion has to work back up the
        tree to the top level grid where those elements are assigned the Grid
        as their parent.

        The Grid object's post_init is called after all of the Row and Column
        post inits.

        This means that the Grid is necessary to contain Row and Column objects
        for now, because it has the top level height and width, unless we start
        allowing things like:

        row = Row(
            height=100,
            width=100,
            children=[...]
        )

        In essence, __post_init__ works at the bottom of the tree up towards
        the top (Grid):

        __post_init__:

        column, column, column, column, (Each Row Broken in 2 Columns)
        row, row (Grid Broken in 2 Rows)
        Grid

        Then, we work from the top back down to calculate measurements:

        dimensions:

        Grid -> Measure Rows
            row -> Measure Cols
                column
                column
            row -> Measure Cols
                column
                column
        """
        self.dimensions = Dimensions(height=height, width=width)
        self._adopt_children()
        self._measure()

    def _measure(self):
        self.coordinates = Coordinates.none()
        # self.absolute_coordinates = Coordinates.none()
        self._measure_children()

    def _measure_children(self):
        children = self.children()
        for child in children:
            child._measure()

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

    @classmethod
    def from_screen(cls, screen, **kwargs):
        height, width = screen.getmaxyx()
        return cls(height=height, width=width, **kwargs)

    def children_windows(self, window, border=None):
        windows = []
        for child in self.children():
            win = child.draw(window, border=border)
            # win.refresh()
            windows.append(win)
        return windows

    def draw(self, window, border=None):
        windows = []

        base_window = window.subwin(
            self.dimensions.height,
            self.dimensions.width,
            self.coordinates.y1,
            self.coordinates.x1
        )

        if border:
            base_window.attron(border)
            base_window.box()
            base_window.attroff(border)

        base_window.refresh()

        windows = [base_window]
        windows += [self.children_windows(base_window, border=border)]
        return windows
