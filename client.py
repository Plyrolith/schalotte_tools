from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bpy.types import Context
    from typing import Any

import datetime
import functools
import json
import pprint
import requests  # type: ignore
import shutil
import urllib

import addon_utils
from bpy.props import BoolProperty, StringProperty

from . import catalog, exceptions, logger


log = logger.get_logger(__name__)


class CustomJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles dates in ISO format"""

    def default(self, o: Any) -> Any:
        """
        Check if an object is a datetime instance and convert into ISO format if so.

        Args:
            o (Any): Object to be checked and converted

        Returns:
            Any: Unchanged or converted object
        """
        if isinstance(o, datetime.datetime):
            return o.isoformat()

        return json.JSONEncoder.default(self=self, o=o)


# Monkey patch JSON decoder to manage dates in ISO format
requests.models.complexjson.dumps = functools.partial(  # type: ignore
    json.dumps,
    cls=CustomJSONEncoder,
)

CACHE: dict[str, requests.Response] = {}
SESSION = requests.Session()
USER: dict | None = None
VERSION: str | None = None


@catalog.bpy_preferences
class Client(catalog.PreferencesModule):
    """Kitsu REST client methods and properties"""

    module: str = "client"

    def update_host(self, context: Context | None = None):
        """
        Set the correct URLs for the client.
        """
        url = self.host.rstrip("/").replace("/api", "")
        if self.event_host != url:
            self.event_host = url
        host = url + "/api"
        if self.host != host:
            self.host = host

    def clear_cache(self, context: Context | None = None):
        """
        Clear the cache.
        """
        log.info("Clearing cache.")
        CACHE.clear()

    # Bool
    is_logged_in: BoolProperty(name="Logged In")
    use_cache: BoolProperty(name="Use Cache", default=True, update=clear_cache)
    use_tokens: BoolProperty(name="Keep me signed in", default=True)

    # String
    access_token: StringProperty(name="Access Token", subtype="PASSWORD")
    event_host: StringProperty(
        name="Event Host",
        default="https://schalotte.trickstudio.de",
    )
    host: StringProperty(
        name="Host",
        default="https://schalotte.trickstudio.de/api",
        update=update_host,
    )
    login_date: StringProperty(name="Login Date")
    password: StringProperty(name="Password", subtype="PASSWORD")
    refresh_token: StringProperty(name="Refresh Token", subtype="PASSWORD")
    username: StringProperty(name="Login")

    if TYPE_CHECKING:
        is_logged_in: bool
        use_cache: bool
        use_tokens: bool
        access_token: str
        event_host: str
        host: str
        login_date: str
        password: str
        refresh_token: str
        username: str

    @property
    def session(self) -> requests.Session:
        return SESSION

    @property
    def user(self) -> dict | None:
        return USER

    @user.setter
    def user(self, user: dict | None = None):
        global USER
        USER = user

    @property
    def version(self) -> str:
        global VERSION
        if not VERSION:
            for module in addon_utils.modules():  # type: ignore
                if module.__name__ == __package__:
                    version = module.bl_info.get("version", (0, 0, 0))
                    VERSION = ".".join(str(v) for v in version)
                    break
            else:
                VERSION = "0.0.0"

        return VERSION

    @staticmethod
    def _build_file_dict(file_path: str, extra_files: list[str] = []) -> dict:
        """
        Build a request compatible dictionary from a base file path and an additional
        file list.

        Args:
            file_path (str): Base file path for the first file
            extra_files (list[str]): Additional files

        Returns:
            dict: File request dictionary
        """
        files = {"file": open(file_path, "rb")}
        for i, file_path in enumerate(extra_files, start=2):
            files[f"file-{i}"] = open(file_path, "rb")

        return files

    @staticmethod
    def build_path_with_params(path: str, params: dict | None) -> str:
        """
        Add parameters to a path using urllib encoding.

        Args:
            path (str): The URL base path
            params (dict | None): The parameters to add as a dict

        Returns:
            str: New path with parameters
        """
        if not params:
            return path

        if hasattr(urllib, "urlencode"):
            return f"{path}?{urllib.urlencode(params)}"  # type: ignore

        return f"{path}?{urllib.parse.urlencode(params)}"  # type: ignore

    def check_status(self, request, path: str) -> int:
        """
        Raise an exception related to status code, if the status code does not
        match a success code. Print error message when it's relevant.

        Args:
            request (Request): The request to validate

        Returns:
            int: Status code

        Raises:
            ParameterException: when 400 response occurs
            NotAuthenticatedException: when 401 response occurs
            RouteNotFoundException: when 404 response occurs
            NotAllowedException: when 403 response occurs
            MethodNotAllowedException: when 405 response occurs
            TooBigFileException: when 413 response occurs
            ServerErrorException: when 500 response occurs
        """
        status_code = request.status_code
        match status_code:
            case 404:
                raise exceptions.RouteNotFoundException(path)
            case 403:
                raise exceptions.NotAllowedException(path)
            case 400:
                text = request.json().get("message", "No additional information")
                raise exceptions.ParameterException(path, text)
            case 405:
                raise exceptions.MethodNotAllowedException(path)
            case 413:
                raise exceptions.FileTooBigException(
                    f"{path}: The file you sent is too big. "
                    "Change your proxy configuration to allow bigger files."
                )
            case (401, 422):
                try:
                    if (
                        self.refresh_token
                        and request.json()["message"] == "Signature has expired"
                    ):
                        self.refresh_access_token()
                        return status_code  # type: ignore
                    else:
                        self.log_out()
                        raise exceptions.NotAuthenticatedException(path)
                except exceptions.NotAuthenticatedException:
                    self.log_out()
                    raise
            case (500, 502):
                try:
                    stacktrace = request.json().get(
                        "stacktrace",
                        "No stacktrace sent by the server",
                    )
                    message = request.json().get(
                        "message",
                        "No message sent by the server",
                    )
                    log.warning("A server error occured!\n")
                    log.warning(f"Server stacktrace:\n{stacktrace}")
                    log.warning(f"Error message:\n{message}\n")
                except Exception:
                    log.exception(request.text)
                raise exceptions.ServerErrorException(path)

        return status_code

    def create(self, path: str, data: dict) -> dict:
        """
        Create an entry for given model and data.

        Args:
            path (str): The model type involved
            data (dict): The data used for creation

        Returns:
            dict: Created entry
        """
        return self.post(self.join_url_path("data", path), data)

    def delete(self, path: str, params: dict | None = None) -> str:
        """
        Run a get request toward given path for this host.

        Args:
            path (str): Path to the resource
            params (dict | None): Optional parameters

        Returns:
            str: The response text
        """
        path = self.build_path_with_params(path, params)
        url = self.get_full_url(path)
        log.debug(f"DELETE {url}")
        response = self.session.delete(url, headers=self.make_auth_header())
        self.check_status(response, path)

        return response.text

    def download(
        self,
        path: str,
        file_path: str,
        params: dict | None = None,
    ) -> Any:
        """
        Download the file located at URL to given path.

        Args:
            path (str): The URL path to download file from
            file_path (str): The location to store the file on

        Returns:
            Any: Request response object

        """
        path = self.build_path_with_params(path, params)
        url = self.get_full_url(path)
        log.debug(f"GET {url}")
        with self.session.get(
            url,
            headers=self.make_auth_header(),
            stream=True,
        ) as response:
            with open(file=file_path, mode="wb") as file_destination:
                shutil.copyfileobj(fsrc=response.raw, fdst=file_destination)

            return response

    def fetch_list(self, path: str, params: dict | None = None) -> list[dict]:
        """
        Fetch a list of entries from given path. Use parameters for filters or add them
        using the URL schema like this: 'tasks?project_id=project-id'

        Args:
            path (str): Path to the resource
            params (dict | None): Optional parameters

        Returns:
            list[dict]: All entries stored in database for a given model
        """
        return self.get(self.join_url_path("data", path), params)

    def fetch(self, path: str, id: str):
        """
        Function dedicated at targeting routes that returns a single mode instance.

        Args:
            path (str): Path to the resource
            id (str): Model instance ID

        Returns:
            dict: The model instance matching id and model name.
        """
        return self.get(self.join_url_path("data", path, id))

    def get(  # type: ignore
        self,
        path: str,
        params: dict | None = None,
        json_response: bool = True,
    ) -> Any:
        """
        Run a get request toward given path for this host.

        Args:
            path (str): Path to the resource
            params (dict | None): Optional parameters
            json_response (bool): Request JSON data instead of raw text

        Returns:
            Any: The request result
        """
        global CACHE
        path = self.build_path_with_params(path, params)
        if self.use_cache:
            response = CACHE.get(path)
            if response:
                # log.debug(f"CACHED {path}")
                if json_response:
                    return response.json()
                return response.text

        url = self.get_full_url(path)
        log.debug(f"GET {url}")
        response = self.session.get(url, headers=self.make_auth_header())
        self.check_status(response, path)

        if self.use_cache:
            CACHE[path] = response

        if json_response:
            return response.json()
        return response.text

    def get_api_version(self) -> str:
        """
        Return the current server API version.

        Returns:
            str: Current version of the API
        """
        return self.get(path="")["version"]

    def get_current_user(self) -> dict | None:
        """
        Return the current user.

        Returns:
            dict | None: Current user dict
        """
        user = self.get(path="auth/authenticated").get("user", None)
        if user:
            self.user = user
        else:
            self.set_tokens()
        return user

    def get_event_host(self) -> str:
        """
        Returns:
            str: Host on which to listen for events
        """
        return self.event_host or self.host

    def get_file_data_from_url(self, url: str, full: bool = False) -> str | bytes:
        """
        Return data found at given URL.

        Args:
            url (str): The URL path to request data from
            full (bool): Get full data bytes stream instead of text

        Returns:
            str | bytes: Content as string or bytes
        """
        if not full:
            url = self.get_full_url(path=url)
        response = requests.get(
            url=url,
            stream=True,
            headers=self.make_auth_header(),
        )
        self.check_status(response, path=url)

        return response.content

    def get_full_url(self, path: str) -> str:
        """
        Args:
            path (str): The path to be based on the host URL

        Returns:
            str: The result of joining configured host URL with given path
        """
        return self.join_url_path(self.host, path)

    def get_host_url(self) -> str:
        """
        Return the host URL for this client, removing the API ending.

        Returns:
            str: The host URL without API ending
        """
        return self.host[:-4]

    def host_is_up(self) -> bool:
        """
        Check if the host is up.

        Returns:
            bool: True if the host is up
        """
        try:
            response = self.session.head(self.host)
        except Exception:
            return False

        return response.status_code == 200

    def host_is_valid(self) -> bool:
        """
        Check if the host is valid by simulating a fake login.

        Returns:
            bool: True if the host is valid
        """
        if not self.host_is_up():
            return False

        try:
            self.post("auth/login", {"email": "", "password": ""})
            return True
        except Exception as exception:
            return type(exception) == exceptions.ParameterException

    def import_data(self, path: str, data: dict) -> Any:
        """
        Import a dictionary into Kitsu, creating a new entry for given model.

        Args:
            path (str): The data model to import
            data (dict): The data to import

        Returns:
            Any: The request result
        """
        return self.post(path=f"/import/kitsu/{path}", data=data)

    @staticmethod
    def join_url_path(*items) -> str:
        """
        Make it easier to build URL path by joining arguments with a '/' character.

        Args:
            items (list[str]): Path elements

        Returns:
            str: Joined URL string
        """
        return "/".join([item.lstrip("/").rstrip("/") for item in items])

    def log_in(self) -> dict | None:
        """
        Log in to the server using given password.

        Returns:
            dict | None: The session's tokens
        """
        self.clear_cache()
        tokens = {}
        try:
            tokens = self.post(
                path="auth/login",
                data={"email": self.username, "password": self.password},
            )
        except (
            exceptions.NotAuthenticatedException,
            exceptions.ParameterException,
        ) as _:
            pass

        if not tokens or not tokens.get("login"):
            raise exceptions.AuthFailedException
        else:
            self.password = ""
            self.set_tokens(tokens)
            self.login_date = datetime.datetime.now().isoformat()
            return tokens

    def log_out(self):
        """
        Log out.
        """
        self.clear_cache()
        self.set_tokens()
        self.login_date = ""

    def make_auth_header(self) -> dict[str, str]:
        """
        Creates the authentication header.

        Returns:
            dict[str, str]: Headers required to authenticate.
        """
        headers = {"User-Agent": f"Blender {self.version}"}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    def post(self, path: str, data: dict | list[tuple] | bytes) -> Any:
        """
        Run a post request toward given path for this host.

        Args:
            path (str): Path to post to
            data (dict | list[tuple] | bytes): Object to include in the request

        Returns:
            Any: The request result
        """
        url = self.get_full_url(path)
        log.debug(f"POST {url}")
        response = self.session.post(url, json=data, headers=self.make_auth_header())
        self.check_status(response, path)

        try:
            result = response.json()
        except json.JSONDecodeError:
            log.warning(response.text)
            raise

        return result

    def put(self, path: str, data: dict | list[tuple] | bytes) -> Any:
        """
        Run a put request toward given path for this host.

        Args:
            path (str): Path to post to
            data (dict | list[tuple] | bytes): Object to include in the request

        Returns:
            Any: The request result
        """
        url = self.get_full_url(path)
        log.debug(f"PUT {url}")
        response = self.session.put(url, json=data, headers=self.make_auth_header())
        self.check_status(response, path)

        return response.json()

    def refresh_access_token(self) -> dict:
        """
        Refresh access token for the client.

        Returns:
            dict: The new tokens.
        """
        path = "auth/refresh-token"
        url = self.get_full_url(path)
        log.debug(f"GET {url}")
        headers = {"User-Agent": f"Blender {self.version}"}
        if self.refresh_token:
            headers["Authorization"] = f"Bearer {self.refresh_token}"

        response = self.session.get(url, headers=headers)
        self.check_status(response, path)

        tokens = response.json()
        self.set_tokens(tokens)
        return tokens

    def set_certificate(
        self,
        cert: str | tuple[str] | None = None,
        ssl_verify: bool = True,
    ):
        """
        Set up an SSL certificate for this client.

        Args:
            ssl_verify (bool): Whether the SSL certificate should be verified
            cert (str | tuple | None): The certificate as path string to the file or
              'cert' & 'key' pair tuple
        """
        if cert is not None:
            if isinstance(cert, str):
                self.session.cert = cert
            else:
                self.session.cert = cert[0]
        self.session.verify = ssl_verify

    def set_tokens(self, tokens: dict = {}):
        """
        Store authentication tokens to use for all requests.

        Args:
            tokens (dict): The tokens to store, consisting of these keys/values
                - access_token (str): The access token
                - refresh_token (str): The refresh token
                - login (bool): Login success status (optional)
                - user (dict): The user's person item dictionary (optional)
        """
        self.access_token = tokens.get("access_token", "")
        self.refresh_token = tokens.get("refresh_token", "")
        self.is_logged_in = tokens.get("login", False)
        self.user = tokens.get("user", None)

    def update(self, path: str, id: str, data: dict) -> dict:
        """
        Update an entry for given model, id and data.

        Args:
            path (str): The model type involved
            id (str): The target model id
            data (dict): The data to update

        Returns:
            dict: Updated entry
        """
        return self.put(self.join_url_path("data", path, id), data)

    def upload(
        self,
        path: str,
        file_path: str,
        data: dict = {},
        extra_files: list[str] = [],
    ) -> Any:
        """
        Upload a file to given URL.

        Args:
            path (str): The URL path to upload the file to
            file_path (str): The file location on the hard drive

        Returns:
            Any: Request response object
        """
        url = self.get_full_url(path)
        log.debug(f"POST {url}")
        files = self._build_file_dict(file_path=file_path, extra_files=extra_files)
        log.debug(f"FILES {pprint.pformat(files)}")
        response = self.session.post(
            url,
            data,
            headers=self.make_auth_header(),
            files=files,
        )
        self.check_status(response, path)

        try:
            result = response.json()
        except json.JSONDecodeError:
            log.exception(response.text)
            raise

        if "message" in result:
            raise exceptions.UploadFailedException(result["message"])

        return result
