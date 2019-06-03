import asyncio
from cement import Interface
import tortoise

from instattack.app.exceptions import UserDoesNotExist, UserExists
from instattack.app.users import User
from instattack.app.attack.handlers import AttackHandler, ProxyHandler


class UserInterface(Interface):

    class Meta:
        interface = 'user'

    async def _get_users(self, loop):
        return await User.all()

    async def _check_if_user_exists(self, username):
        try:
            user = await User.get(username=username)
        except tortoise.exceptions.DoesNotExist:
            return None
        else:
            return user

    async def _create_user(self, username, **kwargs):
        try:
            return await User.create(
                username=username,
                **kwargs
            )
        except tortoise.exceptions.IntegrityError:
            raise UserExists(username)

    async def _edit_user(self, user, **kwargs):
        for key, val in kwargs.items():
            setattr(user, key, val)
        await user.save()

    async def _delete_user(self, username=None, user=None):
        try:
            if not user:
                user = await User.get(username=username)
        except tortoise.exceptions.DoesNotExist:
            raise UserDoesNotExist(username)
        else:
            await user.delete()

    async def _get_user(self, username):
        try:
            return await User.get(username=username)
        except tortoise.exceptions.DoesNotExist:
            raise UserDoesNotExist(username)

    def get_users(self):
        return self.loop.run_until_complete(self._get_users())

    def edit_user(self, user, **kwargs):
        return self.loop.run_until_complete(self._edit_user(user, **kwargs))

    def get_user(self):
        return self.loop.run_until_complete(self._get_user(self.app.pargs.username))

    def create_user(self, username, **kwargs):
        return self.loop.run_until_complete(self._create_user(username, **kwargs))

    def delete_user(self, user=None, username=None):
        return self.loop.run_until_complete(self._delete_user(user=user, username=username))

    def authenticated(self, user):
        if isinstance(user, str):
            user = self.get_user(user)
        return self.loop.run_until_complete(user.was_authenticated())

    def attempted(self, user, password):
        if isinstance(user, str):
            user = self.get_user(user)
        attempts = self.loop.run_until_complete(user.get_attempts())
        attempt = [att for att in attempts if att.password == password]
        if attempt:
            return attempt[0]
        return None

    def authenticated_with_password(self, user, password):
        if isinstance(user, str):
            user = self.get_user(user)
        return self.loop.run_until_complete(user.was_authenticated_with_password(password))


class AttackInterface(Interface):

    class Meta:
        interface = 'attack'

    def _attack_handlers(self):

        start_event = asyncio.Event()
        auth_result_found = asyncio.Event()

        proxy_handler = ProxyHandler(
            self.loop,
            start_event=start_event,
            stop_event=auth_result_found,
        )

        password_handler = AttackHandler(
            self.loop,
            proxy_handler,
            start_event=start_event,
            stop_event=auth_result_found,
        )
        return proxy_handler, password_handler
