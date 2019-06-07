import asyncio
from cement import ex

from instattack.lib.utils import start_and_stop

from instattack.config import constants, config

from instattack.app.models import User
from instattack.app.handlers import LoginHandler

from .abstract import InstattackController
from .prompts import BirthdayPrompt
from .utils import user_command, existing_user_command
from .interfaces import UserInterface

LEVEL_ARGUMENT = (
    ['-lv', '--level'],
    {
        'action': 'store',
        'help': 'Override the Logging Level'
    }
)


class UserController(InstattackController, UserInterface):

    class Meta:
        label = 'users'
        stacked_on = 'base'
        stacked_type = 'nested'

        interfaces = [
            UserInterface,
        ]

    @ex(help='Display All Users')
    def show(self):
        data = {'users': []}

        users = self.get_users()
        for user in users:
            data['users'].append(user.__dict__)

        self.app.render(data, 'users.jinja2')

    @user_command(help="Create a New User")
    def create(self, username):

        prompt = BirthdayPrompt()
        birthday = prompt.prompt()

        with start_and_stop('Creating New User') as spinner:
            self.create_user(username, birthday=birthday)
            spinner.write('Successfully Created User %s' % username)

    @user_command(help="Create a New User")
    def add(self, username):
        """
        Same thing as the .create() method, just for convenience and the fact that
        I am always using both of them interchangeably.
        """
        with start_and_stop('Creating New User') as spinner:
            self.create_user(username)
            spinner.write('Successfully Created User %s' % username)

    @existing_user_command(help="Delete a User")
    def delete(self, user):
        with start_and_stop('Deleting User') as spinner:
            self.delete_user(user=user)
            spinner.write(f"User {user.username} Successfully Deleted")
            spinner.finished_break()

    @existing_user_command(help="Edit an Existing User")
    def edit(self, user):
        """
        Right now, we only have the ability to edit the birthday.  There are
        no other editable attributes on the user.
        """
        prompt = BirthdayPrompt()
        birthday = prompt.prompt()

        with start_and_stop('Editing User') as spinner:
            self.edit_user(user, birthday=birthday)
            spinner.write('Successfully Edited User %s' % user.username)

    @existing_user_command(help="Display Information for User")
    def get(self, user):
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

    @existing_user_command(help="Show User Base Passwords")
    def show_passwords(self, user):
        passwords = user.get_passwords()
        data = {'title': 'Passwords', 'data': passwords}
        self.app.render(data, 'user_data.jinja2')

    @existing_user_command(help="Show User Base Alterations")
    def show_alterations(self, user):
        alterations = user.get_alterations()
        data = {'title': 'Alterations', 'data': alterations}
        self.app.render(data, 'user_data.jinja2')

    @existing_user_command(help="Show User Numeric Alterations")
    def show_numerics(self, user):
        numerics = user.get_numerics()
        data = {'title': 'User Numeric Alterations', 'data': numerics}
        self.app.render(data, 'user_data.jinja2')

    @existing_user_command(help="Show User Historical Password Atttempts")
    def show_attempts(self, user):
        attempts = self.loop.run_until_complete(user.get_attempts())
        data = {
            'title': 'User Attempts',
            'data': [attempt.password for attempt in attempts]
        }
        self.app.render(data, 'user_data.jinja2')

    @ex(
        help='Generate Potential Password Atttempts',
        arguments=[
            (['username'], {'help': 'Username'}),
            (['-l', '--limit'], {'default': None, 'type': int})
        ]
    )
    @existing_user_command(help="Generate Potential Password Atttempts")
    def generate_attempts(self, user):
        attempts = self.loop.run_until_complete(
            user.get_new_attempts(self.loop, limit=self.app.pargs.limit)
        )
        if len(attempts) == 0:
            self.failure('No Attempts to Generate')
            return

        data = {
            'title': 'Potential User Attempts',
            'data': attempts
        }
        self.app.render(data, 'user_data.jinja2')

    @existing_user_command(help="Clear Historical Password Attempts")
    def clear_attempts(self, user):

        async def _clear_attempts():

            attempts = await user.get_attempts()
            if len(attempts) == 0:
                self.failure("No Attempts to Clear")

            else:
                proceed = self.proceed(f"About to Clear {len(attempts)} Attempts")
                if proceed:
                    with start_and_stop(
                        f"Clearing {len(attempts)} Attempts "
                        f" for User {user.username} Attempts"
                    ):
                        await user.clear_attempts(attempts=attempts)

        self.loop.run_until_complete(_clear_attempts())

    @existing_user_command(
        help="Single Login Attempt",
        arguments=[
            (['password'], {'help': 'Password'})
        ]
    )
    def login(self, user):
        """
        [x] TODO:
        --------
        Set collect flag to default to False unless specified for login and
        attack modes.
        """
        message = None
        if self.authenticated_with_password(user, self.app.pargs.password):
            message = "User Already Authenticated with Password %s" % self.app.pargs.password
        elif self.authenticated(user):
            message = "User Already Authenticated"
        elif self.attempted(user, self.app.pargs.password):
            message = "Password Already Attempted"

        if message:
            if not self.proceed(message):
                return

        login = LoginHandler(self.loop)
        result = self.loop.run_until_complete(login.login(self.app.pargs.password))

        if result.authorized:
            self.success('Authenticated!')
        else:
            self.failure('Not Authenticated')

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

        directory = constants.USER_PATH
        for user_dir in directory.iterdir():
            if user_dir.is_file():
                print_action(user_dir.name, 'Deleting File')
                print('Deleting File', label=user_dir.name, directory=constants.USER_PATH)
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
                                if other_name not in constants.FILES:
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
