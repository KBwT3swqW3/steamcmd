from os import path
from time import sleep
from pathlib import Path
from subprocess import run
from os import linesep as ls
from datetime import datetime
from email.utils import parsedate_to_datetime
from jinja2 import Environment, PackageLoader, select_autoescape

import logging
import requests
import platform
import tarfile

LOG = logging.getLogger(__name__)
LOG.addHandler(logging.NullHandler())


class ServerBase:
    # https://steamapi.xpaw.me/#ISteamRemoteStorage/GetCollectionDetails
    # collectioncount, Number of collections being requested
    # publishedfileids[arr], List of collection ids to get the details for
    get_collection_url = "https://api.steampowered.com/ISteamRemoteStorage/GetCollectionDetails/v1/"
    # https://steamapi.xpaw.me/#ISteamRemoteStorage/GetPublishedFileDetails
    # itemcount, Number of items being requested
    # publishedfileids[arr], List of published file id to look up
    get_file_details_url = "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/"

    def __init__(
        self,
        app_id: int,
        steamcmd_path: str = "/usr/games/steamcmd",
        steamcmd_script_path: str = "/home/steam/py-manager-update.script",
        install_base_path: str = "/home/steam/games",
        username: str = None,
        password: str = None,
        server_ref: str = "0",
        install_sourcemod: bool = False,
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
        :param install_sourcemod: If True will install metamod and sourcemod
            onto the server, only works if the server is a source server
        """
        self.app_id = app_id
        self.steamcmd_path = steamcmd_path
        self.steamcmd_script_path = Path(steamcmd_script_path)
        self.install_base_path = install_base_path
        self.username = username
        self.password = password
        self.server_ref = server_ref
        self.install_sourcemod = install_sourcemod
        self.game_path = None
        self.addons_path = None
        self.game_executable_path = None
        self.friendly_name = None
        self.stop_cmd = None

        self.install_path = (
            f"{self.install_base_path}/{self.app_id}/{self.server_ref}"
        )
        self.SOURCE_MOD_GAME = False
        self.j2 = Environment(
            loader=PackageLoader("steamcmd"),
            autoescape=select_autoescape(),
        )

    def install_app(
        self,
        template_name: str = "base_install_app.j2",
        context: dict = {},
    ) -> None:
        """
        This method installs a steam application at a location built based on
        the base install path of the object, the application ID and a server
        reference.

        The idea is if you need custom logic for the application you can wrap
        this function with that logic and call the parents function to perform
        the standard steamcmd installation.

        :param template_name: The name of the Jijna2 template stored in the
            package, this template should be a script that can be understood
            by steamcmd
        :param context: Contains additional data to be passed to the Jinja2
            template, this can be accessed inside the template as context.x
            where x is the key name in the passed dictionary
        """
        LOG.info(
            f"Installing app {self.app_id}, server reference: {self.server_ref}"
        )
        template = self.j2.get_template(template_name)
        data = {
            "username": self.username,
            "password": self.password,
            "app_id": self.app_id,
            "install_path": self.install_path,
            "context": context,
        }
        self.steamcmd_script_path.write_text(template.render(data))

        try:
            if self.steamcmd_script_path.exists():
                result = run(
                    args=[
                        self.steamcmd_path,
                        "+runscript",
                        self.steamcmd_script_path.absolute(),
                    ],
                    capture_output=True,
                )
                if result.returncode != 0:
                    raise Exception(
                        f"Error when installing app: {self.app_id}, server reference: {self.server_ref}, stdout:{ls}{result.stdout}{ls}{ls}stderr:{ls}{result.stderr}"
                    )
        except Exception:
            if self.steamcmd_script_path.exists():
                self.steamcmd_script_path.unlink()
            raise

        if self.steamcmd_script_path.exists():
            self.steamcmd_script_path.unlink()

        LOG.info(
            f"Finished installing app {self.app_id}, server reference: {self.server_ref}"
        )

    def download_collections(
        self, collection_ids: list = [], install_path: str = None
    ) -> None:
        """
        Used as the entrypoint to download collections from the workshop and
        install them into specified install path

        :param collection_ids: A list of collection IDs to look up
        :param install_path: Where to install the files from the workshop
        """
        p = Path(install_path)
        if p.exists():
            if not p.is_dir():
                LOG.exception(f"{p.absolute()} exists but is not a directory")
        else:
            p.mkdir()

        file_ids = self._get_collection_file_ids(collection_ids)
        LOG.debug(f"File Ids: {file_ids}")

        file_details = self._get_steam_file_info(file_ids)
        LOG.debug(file_details)

        for k, details in file_details.items():
            file_path = Path(
                path.join(
                    p.absolute(), f"{k}{Path(details['file_name']).suffix}"
                )
            )
            if file_path.exists():
                if (
                    file_path.stat().st_size == details["file_size"]
                    or file_path.stat().st_mtime > details["time_updated"]
                ):
                    LOG.info(
                        f"Skipping {details['file_name']}, already exists"
                    )
                    continue

            LOG.info(f"Downloading {details['file_name']}")
            self._download_file(details["file_url"], file_path)

    def _download_file(self, file_url: str, file_path: Path):
        """
        Downloads files in chunks and stores them on disk

        :param file_url: The URL to download from
        :param file_path: The path to store the file on disk
        """
        with requests.get(file_url, stream=True) as r:
            r.raise_for_status()
            with open(file_path.absolute(), "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)

    def _get_collection_file_ids(
        self, collection_ids: list, retries: int = 5, retry_seconds: int = 5
    ) -> list:
        """
        Uses the Steam API to lookup the file details from a collection

        :param collection_ids: A list of IDs to lookup

        :return: A list of file IDs
        """
        data = {"collectioncount": str(len(collection_ids))}
        for i, v in enumerate(collection_ids):
            data[f"publishedfileids[{i}]"] = v

        for _ in range(retries):
            resp = requests.post(self.get_collection_url, data=data)
            if resp.status_code == 200:
                break
            sleep(retry_seconds)

        if resp.status_code != 200:
            raise Exception(
                f"Error downloading collection IDs after {retries} retries from {self.get_collection_url}, Response code: {resp.status_code}, Content: {resp.content}"
            )

        collections = resp.json()

        resp = []
        collections = collections["response"]

        for result in collections["collectiondetails"]:
            for collection_detail in result["children"]:
                collection = collection_detail["publishedfileid"]
                if collection not in resp:
                    resp.append(collection)

        return resp

    def _get_steam_file_info(
        self, file_ids: list, retries: int = 5, retry_seconds: int = 5
    ) -> dict:
        """
        Uses the Steam API to lookup and retrieve a limited set of information
        about the file to determine whether or not the files need updating.

        :return: A dictionary of file IDs as keys and file_name file_size,
            time_updated and file_url as responses
        """
        data = {"itemcount": len(file_ids)}
        for i, v in enumerate(file_ids):
            data[f"publishedfileids[{i}]"] = v

        for _ in range(retries):
            resp = requests.post(self.get_file_details_url, data=data)
            if resp.status_code == 200:
                break
            sleep(retry_seconds)

        if resp.status_code != 200:
            raise Exception(
                f"Error downloading file info after {retries} retries from {self.get_collection_url}, Response code: {resp.status_code}, Content: {resp.content}"
            )

        result = {}
        for file_details in resp.json()["response"]["publishedfiledetails"]:
            if file_details["publishedfileid"] not in result:
                result[file_details["publishedfileid"]] = {
                    "file_name": file_details["filename"],
                    "file_size": file_details["file_size"],
                    "time_updated": file_details["time_updated"],
                    "file_url": file_details["file_url"],
                }

        return result

    def _allied_mods_download(
        self,
        install_path: Path,
        url_prefix: str,
        version: str,
        latest_suffix: str,
    ) -> bool:
        """
        Downloads files from the allied mods website used for pulling metamod
        and sourcemod

        :param install_path: Path to download the file to
        :param url_prefix: The prefix of the URL
        :param version: The version of the file to download
        :param latest_suffix: The suffix which holds the filename of the latest
            version of the mod being downloaded

        :return: Returns true on a file download false if nothing changed
        """
        latest_url = f"{url_prefix}/{version}/{latest_suffix}"
        resp = requests.get(latest_url)
        if resp.status_code != 200:
            raise Exception(
                f"Error retrieving latest metamod/sourcemod version: {latest_suffix}"
            )

        download_file = resp.content.decode("UTF-8")
        download_url = f"{url_prefix}/{version}/{download_file}"

        if install_path.is_file():
            resp = requests.head(download_url)
            remote_size = resp.headers["Content-Length"]
            local_size = str(install_path.stat().st_size)

            remote_ts = parsedate_to_datetime(resp.headers["Last-Modified"])
            local_ts = datetime.fromtimestamp(
                install_path.stat().st_mtime,
                datetime.now().astimezone().tzinfo,
            )

            time_diff = remote_ts - local_ts

            if remote_size == local_size and time_diff.days < 0:
                LOG.info(f"{download_file} already installed, skipping")
                return False

        LOG.debug(resp.headers)
        LOG.info(f"Downloading metamod from {download_url}")
        self._download_file(download_url, install_path)
        return True

    def _install_metamod(self, version: str = "1.11") -> None:
        """
        Downloads and installs metamod

        :param version: The major and minor version of metamod to install, the
            latest version will be discovered and installed
        """
        if not self.SOURCE_MOD_GAME:
            LOG.warn("SOURCE_MOD_GAME not set, skipping metamod install")

        file_changed = self._allied_mods_download(
            Path(f"{self.addons_path}/metamod.tar.gz"),
            "https://mms.alliedmods.net/mmsdrop",
            version,
            f"mmsource-latest-{platform.system().lower()}",
        )

        if file_changed:
            tar = tarfile.open(f"{self.addons_path}/metamod.tar.gz", "r:gz")
            tar.extractall(self.game_path)
            tar.close

    def _install_sourcemod(self, version: str = "1.10") -> None:
        """
        Downloads and installs sourcemod

        :param version: The major and minor version of sourcemod to install, the
            latest version will be discovered and installed
        """
        if not self.SOURCE_MOD_GAME:
            LOG.warn("SOURCE_MOD_GAME not set, skipping sourcemod install")

        file_changed = self._allied_mods_download(
            Path(f"{self.addons_path}/sourcemod.tar.gz"),
            "https://sm.alliedmods.net/smdrop",
            version,
            f"sourcemod-latest-{platform.system().lower()}",
        )

        if file_changed:
            tar = tarfile.open(f"{self.addons_path}/sourcemod.tar.gz", "r:gz")
            tar.extractall(self.game_path)
            tar.close

    def create_sourcemod_groups(self, groups: list) -> None:
        """
        Replaces the sourcemod admin_groups.cfg file with content from a template
        filled in by groups passed

        :param groups: A list of groups to create with permissions and immunity
            levels
        """
        group_config_path = Path(
            f"{self.addons_path}/sourcemod/configs/admin_groups.cfg"
        )

        template = self.j2.get_template("sourcemod_admin_groups.cfg.j2")
        rendered_template = template.render({"groups": groups})

        group_config_path.write_text(rendered_template)

    def create_sourcemod_admins(self, admins: list) -> None:
        """
        Replaces the sourcemod admins_simple.ini file with content from a
        template filled in by admins passed

        :param admins: A list of admins to create with associated groups and
            optional passwords
        """
        group_config_path = Path(
            f"{self.addons_path}/sourcemod/configs/admins_simple.ini"
        )

        template = self.j2.get_template("sourcemod_admins_simple.ini.j2")
        rendered_template = template.render({"admins": admins})
        group_config_path.write_text(rendered_template)

    def update_server_cfg_settings(
        self,
        settings: dict,
        exec_configs: list = ["banned_user.cfg", "banned_ip.cfg"],
    ) -> None:
        """
        Reads the server.cfg file and replaces or adds settings as provided.

        :param settings: A set of key pair values of settings to add/replace
            in the server.cfg file
        """
        keys = list(settings.keys())
        infile_path = Path(f"{self.game_path}/cfg/server.cfg")
        outfile_path = Path(f"{infile_path}.new")

        if infile_path.exists():
            with open(infile_path, "r") as infile, open(
                outfile_path, "w"
            ) as outfile:
                for line in infile:
                    if not line[0:2] == "//":
                        setting_key = None
                        splits = line.split()
                        if len(splits) != 0:
                            setting_key = splits[0]
                        if setting_key in keys:
                            keys.remove(setting_key)
                            if isinstance(settings[setting_key], str):
                                line = f'{setting_key} "{settings[setting_key]}"{ls}'
                            elif isinstance(settings[setting_key], int):
                                line = f"{setting_key} {settings[setting_key]}{ls}"

                    outfile.write(line)

        with open(outfile_path, "a") as outfile:
            for key in keys:
                if isinstance(settings[key], str):
                    outfile.write(f'{key} "{settings[key]}"{ls}')
                elif isinstance(settings[key], int):
                    outfile.write(f"{key} {settings[key]}{ls}")

            for config in exec_configs:
                outfile.write(f"exec {config}{ls}")

            outfile.write(f"writeid{ls}")
            outfile.write(f"writeip{ls}")

        outfile_path.rename(infile_path)

    def install_systemd_service(
        self, run_user: str = "steam", run_group: str = "steam"
    ) -> None:
        """
        Installs a systemd service and socket for stdin, allowing a way to
        send commands to the server once launched

        :param run_user: The user who the server should be run as and who has
            ownership of the socket file
        :param run_group: The group which the server should be run as and that
            has access to the socket file
        """
        service_path = Path(
            f"/etc/systemd/system/{self.friendly_name}-{self.server_ref}.service"
        )
        template = self.j2.get_template("systemd.service.j2")
        data = {
            "friendly_name": self.friendly_name,
            "server_ref": self.server_ref,
            "start_cmd": self.game_executable_path,
            "stop_cmd": self.stop_cmd,
            "run_user": run_user,
            "run_group": run_group,
        }
        service_path.write_text(template.render(data))

        socket_path = Path(
            f"/etc/systemd/system/{self.friendly_name}-{self.server_ref}.socket"
        )
        template = self.j2.get_template("systemd.socket.j2")
        socket_path.write_text(template.render(data))
