import asyncio
from plumbum import cli

from lib import log_handling

from instattack.models import User

from .base import Instattack, BaseApplication


@Instattack.subcommand('users')
class UsersApplication(BaseApplication):
    pass


@UsersApplication.subcommand('add')
class AddUserApplication(UsersApplication):

    @log_handling('self')
    def main(self, username):
        print('Adding user')
