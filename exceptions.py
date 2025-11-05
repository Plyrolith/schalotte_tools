class AuthFailedException(Exception):
    """Error raised when user credentials are wrong"""


class DownloadFileException(Exception):
    """Error raised when a file can't be downloaded"""


class FileTooBigException(Exception):
    """Error raised when a 413 error (payload too big error) is sent by the API"""


class HostException(Exception):
    """Error raised when host is not valid"""


class MethodNotAllowedException(Exception):
    """Error raised when a 405 error (method not handled) is sent by the API"""


class NotAllowedException(Exception):
    """Error raised when a 403 error (not authorized) is sent by the API"""


class NotAuthenticatedException(Exception):
    """Error raised when a 401 error (not authenticated) is sent by the API"""


class ParameterException(Exception):
    """Error raised when a 400 error (argument error) is sent by the API"""


class RouteNotFoundException(Exception):
    """Error raised when a 404 error (not found) is sent by the API"""


class ServerErrorException(Exception):
    """Error raised when a 500 error (server error) is sent by the API"""


class TaskStatusNotFound(Exception):
    """Error raised when a task status is not found"""


class UploadFailedException(Exception):
    """Error raised due to remote server processing failure when uploading a file"""
