from .base import mutation_gen


class case_gen(mutation_gen):

    def __call__(self):
        for case_alteration in self.alterations_of_case():
            yield case_alteration

    def alterations_of_case(self):
        """
        TODO
        ----
        Add setting for the maximum length of the word to make the entire
        thing uppercase.
        """
        yield self.base.lower()
        yield self.capitalize_at_indices(0)
        yield self.capitalize_at_indices(0, 1)
        yield self.capitalize_at_indices(1)
