from .base import ServerBase
from .enums import AppIds

from sys import executable as python_bin


class Left4Dead2Server(ServerBase):
    def __init__(
        self,
        app_id: int = AppIds.L4D2,
        steamcmd_path: str = "/usr/games/steamcmd",
        steamcmd_script_path: str = "/home/steam/py-manager-update.script",
        install_base_path: str = "/home/steam/games",
        username: str = None,
        password: str = None,
        server_ref: str = "0",
        install_sourcemod: bool = True,
    ) -> None:
        """
        This class is designed to help simplify installing applications using
        steamcmd and provide an interface for configuring them.

        :param app_id: The application ID to install IDs can be found at
            https://steamdb.info/apps/
        :param steamcmd_path: The path to the steamcmd binary
        :param steamcmd_script_path: Location of a temporary file that will be
            used for creating the steamcmd scripts in
        :param install_base_path: The base directory to store installed
            applications in
        :param username: If the application you're trying to install requires
            authentication to download, this is how to provide the username
        :param password: If the application you're trying to install requires
            authentication to download, this is how to provide the password
        :param server_ref: A reference for the server, gets appended to the
            install path
        """
        super().__init__(
            app_id=app_id,
            steamcmd_path=steamcmd_path,
            steamcmd_script_path=steamcmd_script_path,
            install_base_path=install_base_path,
            username=username,
            password=password,
            server_ref=server_ref,
            install_sourcemod=install_sourcemod,
        )
        self.SOURCE_MOD_GAME = True
        self.game_path = f"{self.install_path}/left4dead2"
        self.addons_path = f"{self.install_path}/left4dead2/addons"
        self.game_executable_path = f"{self.install_path}/srcds_run"
        self.friendly_name = "left4dead2"
        self.stop_cmd = f"{python_bin} -m {__name__.split('.')[0]}.systemd $MAINPID --cmd 'say Server shutting down in 10 seconds' --cmd 'quit' --cmd-delay 10"

    def install_app(
        self,
        template_name: str = "base_install_app.j2",
        context: dict = {},
        collection_ids=[],
    ) -> None:
        """
        This method installs a steam application at a location built based on
        the base install path of the object, the application ID and a server
        reference.

        This instance is designed specifically for Left 4 Dead 2 servers and
        allows you to provide a list of collection IDs, if provided once
        installed the collections will be downloaded and added to the Left
        4 Dead 2 addons folder ready for use.

        :param template_name: The name of the Jijna2 template stored in the
            package, this template should be a script that can be understood
            by steamcmd
        :param context: Contains additional data to be passed to the Jinja2
            template, this can be accessed inside the template as context.x
            where x is the key name in the passed dictionary
        :param collection_ids: A list of collections from the steam store to
            install onto the server
        """
        super().install_app(
            template_name=template_name,
            context=context,
        )

        if len(collection_ids) > 0:
            self.download_collections(
                collection_ids,
                self.addons_path,
            )

        if self.install_sourcemod:
            self._install_metamod()
            self._install_sourcemod()
