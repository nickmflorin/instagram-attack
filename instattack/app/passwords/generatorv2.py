from dataclasses import dataclass
from dacite import from_dict
from typing import List

from instattack.config import config

from .generator import abstract_password_gen
from .mutatorsv2 import character_mutator_v2, additive_mutator_v2


@dataclass
class AlterationSpec:

    base: str
    numerics: List[int]
    alphas: List[str]

    alterations_before: List[str]
    alterations_after: List[str]
    mutations: List[str]

    def generate(self, user):
        self.include_character_alterations(user)
        self.include_numeric_alterations(user)
        self.include_alpha_alterations(user)

    def after(self, value):
        self.alterations_after.append(value)

    def before(self, value):
        self.alterations_before.append(value)

    def include_alpha_alterations(self, user):
        alpha_gen = additive_mutator_v2(mode='alterations')
        for alteration in self.alphas:
            alpha_gen(self, alteration)

    def include_numeric_alterations(self, user):
        if config['passwords']['generator']['numerics']['birthday']['provided']:
            if user.birthday:
                autogenerate_birthdays(user, self.numerics)

        alpha_gen = additive_mutator_v2(mode='alterations')
        numeric_gen = additive_mutator_v2(mode='numerics')

        # Have to include numerics with alterations before and after in combo
        for numeric in self.numerics:
            generate_numerics(self, numeric)
            for numeric in self.numerics:
                generate_numerics(self, numeric, base='xxx')

    def include_character_alterations(self, user):
        generate_character_alterations = character_mutator_v2(self)
        generate_character_alterations()


class password_gen_v2(abstract_password_gen):

    def __call__(self):
        """
        IMPORTANT
        --------
        What we should really do is separatate the alterations into components
        in an iterable, [Caitlin, 083801331, Blue], and then just apply the
        custom alterations to the primary component, and use combinatorics to
        generate passwords.
        """
        def base_generator():
            for password in self.passwords:
                spec = AlterationSpec(
                    base=password,
                    numerics=self.numerics,
                    alphas=self.alterations,
                    alterations_before=[],
                    alterations_after=[],
                    mutations=[],
                )
                yield from spec.generate(self.user)

        yield from self.safe_yield(base_generator())
        print(
            f'There Were {len(self.duplicates)} '
            'Duplicates Removed from Generated Passwords'
        )
