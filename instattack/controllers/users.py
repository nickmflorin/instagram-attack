import asyncio
from cement import ex, Interface
import tortoise

from instattack.lib.utils import start_and_stop

from instattack import settings
from instattack.app.exceptions import UserDoesNotExist, UserExists
from instattack.app.users import User

from .abstract import InstattackController
from .utils import username_command


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

    async def _create_user(self, username):
        try:
            return await User.create(username=username)
        except tortoise.exceptions.IntegrityError:
            raise UserExists(username)

    async def _delete_user(self, username):
        try:
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


class UserController(InstattackController, UserInterface):

    class Meta:
        label = 'users'
        stacked_on = 'base'
        stacked_type = 'nested'

        interfaces = [
            UserInterface,
        ]

    @username_command(help="Create a New User")
    def create(self):
        username = self.app.pargs.username

        loop = asyncio.get_event_loop()
        user = loop.run_until_complete(self._create_user(username))
        attempts = loop.run_until_complete(user.get_attempts())

        data = {'user': {
            'id': user.id,
            'username': user.username,
            'num_attempts': len(attempts),
            'date_created': user.date_created,
            'num_passwords': len(user.get_passwords()),
            'num_numerics': len(user.get_numerics()),
            'num_alterations': len(user.get_alterations())
        }}
        self.app.render(data, 'user.jinja2')

    @username_command(help="Delete a User")
    def delete(self):
        username = self.app.pargs.username

        loop = asyncio.get_event_loop()
        loop.run_until_complete(self._delete_user(username))

        self.success(f"User {username} Successfully Deleted")

    @username_command(help='Display Information for User')
    def get(self):
        username = self.app.pargs.username

        loop = asyncio.get_event_loop()
        user = loop.run_until_complete(self._get_user(username))

        data = {'user': {
            'id': user.id,
            'username': user.username,
            'num_attempts': len(user.get_attempts()),
            'date_created': user.date_created,
            'num_passwords': len(user.get_passwords()),
            'num_numerics': len(user.get_numerics()),
            'num_alterations': len(user.get_alterations())
        }}
        self.app.render(data, 'user.jinja2')

    @ex(help='Display All Users')
    def show(self):
        data = {'users': []}

        loop = asyncio.get_event_loop()
        users = loop.run_until_complete(self._get_users(loop))
        for user in users:
            data['users'].append(user.__dict__)

        self.app.render(data, 'users.jinja2')

    @username_command(help="Show User Base Passwords")
    def show_passwords(self):

        loop = asyncio.get_event_loop()
        user = loop.run_until_complete(self._get_user(self.app.pargs.username))
        passwords = user.get_passwords()

        data = {'title': 'Passwords', 'data': passwords}
        self.app.render(data, 'user_data.jinja2')

    @username_command(help="Show User Base Alterations")
    def show_alterations(self):

        loop = asyncio.get_event_loop()
        user = loop.run_until_complete(self._get_user(self.app.pargs.username))
        alterations = user.get_alterations()

        data = {'title': 'Alterations', 'data': alterations}
        self.app.render(data, 'user_data.jinja2')

    @username_command(help="Show User Numeric Alterations")
    def show_numerics(self):

        loop = asyncio.get_event_loop()
        user = loop.run_until_complete(self._get_user(self.app.pargs.username))
        numerics = user.get_numerics()

        data = {'title': 'User Numeric Alterations', 'data': numerics}
        self.app.render(data, 'user_data.jinja2')

    @username_command(help="Show User Historical Password Atttempts")
    def show_attempts(self):

        loop = asyncio.get_event_loop()
        user = loop.run_until_complete(self._get_user(self.app.pargs.username))
        attempts = loop.run_until_complete(user.get_attempts())

        data = {'title': 'User Attempts', 'data': attempts}
        self.app.render(data, 'user_data.jinja2')

    @ex(help="Clear Historical Password Attempts", arguments=[
        (['username'], {'help': 'Username'}),
    ])
    def clear_attempts(self):

        async def _clear_attempts(loop, user, spinner):
            spinner.write("> Gathering Attempts...")
            attempts = await user.get_attempts()

            if len(attempts) == 0:
                spinner.write("> No Attempts to Clear")

            else:
                spinner.write(f"> Clearing {len(attempts)} Attempts...")
                for attempt in attempts:
                    await attempt.delete()

        loop = asyncio.get_event_loop()
        user = loop.run_until_complete(self._get_user(self.app.pargs.username))

        with start_and_stop(f"Clearing User {self.app.pargs.username} Attempts") as spinner:
            loop.run_until_complete(_clear_attempts(loop, user, spinner))

    @ex(
        help='Clean User Directory for Active and Deleted Users',
        arguments=[(
            ['-s', '--safe'], {'action': 'store_true'}
        )]
    )
    def clean(self):
        """
        First, loops over current users and ensures that their directory
        and files are present.  Then, looks in the user directory for any
        users that do not exist anymore and deletes those files.
        """
        def print_action(action, label=None, directory=None):
            message = f"{action} ({label})" if label else action
            if directory:
                message += f" in Directory {directory}."
            else:
                message += "."
            print(message)

        loop = asyncio.get_event_loop()
        users = loop.run_until_complete(self._get_users(loop))
        for user in users:
            # This really shouldn't happen often, since we do this on save.
            if not user.directory.exists():
                user.initialize_directory()

        directory = settings.USER_PATH
        for user_dir in directory.iterdir():
            if user_dir.is_file():
                print_action(user_dir.name, 'Deleting File')
                print('Deleting File', label=user_dir.name, directory=settings.USER_PATH)
                if not self.app.pargs.safe:
                    user_dir.delete()
            else:
                # Remove Directory if User Does Not Exist
                if user_dir.name not in [user.username for user in users]:
                    print('Deleting Leftover Directory', label=user_dir.name)
                    if not self.app.pargs.safe:
                        user_dir.delete()
                else:
                    user = [usr for usr in users if usr.username == user_dir.name][0]

                    # Make Sure All Files Present if User Exists
                    for file in User.FILES:
                        pt = user.file_path(file)
                        if not pt.exists() or not pt.is_file():
                            print(f'File {pt.name} Missing for User {user.username}')
                            if not self.app.pargs.safe:
                                pt.touch()

                    # Make Sure No Other Files Present
                    for other in user_dir.iterdir():
                        if other.is_file():
                            if other.suffix != '.txt':
                                print_action(
                                    f"Deleting File w Invalid Format {other.suffix}",
                                    label=other.name,
                                    directory=user_dir.name
                                )
                                if not self.app.pargs.safe:
                                    other.delete()
                            else:
                                other_name = other.name.split('.txt')[0]
                                if other_name not in settings.FILES:
                                    print_action(
                                        f"Deleting Invalid File",
                                        label=other.name,
                                        directory=user_dir.name
                                    )
                                    if not self.app.pargs.safe:
                                        other.delete()
                        else:
                            print_action(
                                f'Deleting Invalid Sub-Directory',
                                label=other.name,
                                directory=user_dir.name,
                            )
                            if not self.app.pargs.safe:
                                other.delete()
