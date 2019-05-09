from .base import abstract_gen


class case_gen(abstract_gen):

    async def gen(self, word):
        async for case_alteration in self.alterations_of_case(word):
            yield case_alteration

    async def alterations_of_case(self, word):
        """
        TODO
        ----
        Add setting for the maximum length of the word to make the entire
        thing uppercase.
        """
        yield word.lower()
        yield self.capitalize_at_indices(word, 0)
        yield self.capitalize_at_indices(word, 0, 1)
        yield self.capitalize_at_indices(word, 1)
