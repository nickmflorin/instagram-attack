from instattack.config import fields


__all__ = ('LOGIN', )


GENERATOR = fields.SetField(
    # TODO: Add validation to make sure all elements of nested lists are
    # integers.
    CAPITALIZE_AT_INDICES=fields.ListField(
        default=[0, 1, [0, 1]],
        type=(int, list),
    ),
    COMMON_CHAR_REPLACEMENTS=fields.DictField({
        'i': ('1', '!'),
        'p': ('3', '@'),
    }),
    GENERATOR=fields.SetField(
        BEFORE=fields.BooleanField(default=False),
        AFTER=fields.BooleanField(default=False),
    ),
    NUMERICS=fields.SetField(
        BEFORE=fields.BooleanField(default=False),
        AFTER=fields.BooleanField(default=False),
        BIRTHDAY=fields.SetField(
            PROVIDED=fields.BooleanField(default=True),
            ALL=fields.BooleanField(default=False),
            START_YEAR=fields.YearField(default=1991),
            END_YEAR=fields.YearField(default=2000)

        )
    )
)

LOGIN = fields.SetField(
    PASSWORDS=fields.SetField(
        BATCH_SIZE=fields.PositiveIntField(
            default=10,
            max=50,
            help="The number of concurrent passwords to try at the same time."
        ),
        GENERATOR=GENERATOR,
    ),
    ATTEMPTS=fields.SetField(
        BATCH_SIZE=fields.PositiveIntField(
            default=10,
            max=50,
            help="The number of concurrent requests to make for each password."
        ),
        SAVE_METHOD=fields.ConstantField('end')
    )
)
