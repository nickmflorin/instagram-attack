"""
This module is only for developer environments.

Creating a sub-module where we can store test code, duplicate and modified versions
of existing code and explore programming possibilities is a crucial part of
this project.

It is in this module where we play around with certain packages, code and
ideas, not being in the Cement app framework but still having access to the
components that make up the instattack app.
"""
from instattack import settings

from instattack.lib.diagnostics.cells import Grid
from instattack.config.fields import *


def find_optimal_size(grid):
    # For now, we will limit how many levels deep we go to avoid complication,
    # but eventually might want to make this recursive.
    def get_for_obj(obj):
        rh_values = []
        for row in obj.rows:
            if not row.columns:
                rh_values.append((row._rh, ))
            else:
                div_by = []
                for col in row.columns:
                    if col.rows:
                        div_by.extend(get_for_obj(col))
                        # for row2 in col.rows:
                        #     div_by.append(row2._rh)

                # All Columns Have No Rows
                if len(div_by) == 0:
                    rh_values.append((row._rh, ))
                else:
                    rh_values.append((row._rh, div_by))
        return rh_values


    return get_for_obj(grid)


def playground():
    from termx import settings as settt
    print(settt.colors.green('test'))
