import logging
from typing import Optional

from whylabs_client.api_client import ApiClient, Configuration  # type: ignore

from whylogs.api.whylabs.session.config import InitConfig, SessionConfig
from whylogs.api.whylabs.session.session import (
    ApiKeySession,
    GuestSession,
    LocalSession,
    Session,
)
from whylogs.api.whylabs.session.session_types import SessionType

logger = logging.getLogger(__name__)


class SessionManager:
    __instance: Optional["SessionManager"] = None

    def __init__(
        self,
        config: SessionConfig,
    ):
        self._config = config
        client_config = Configuration()
        client_config.host = self._config.get_whylabs_endpoint()
        self._whylabs_client = ApiClient(client_config)

        self.session: Session
        session_type = config.get_session_type()
        if session_type == SessionType.LOCAL:
            self.session = LocalSession(self._config)
        elif session_type == SessionType.WHYLABS_ANONYMOUS:
            self.session = GuestSession(self._config, self._whylabs_client)
        elif session_type == SessionType.WHYLABS:
            client_config.api_key = {"ApiKeyAuth": self._config.require_api_key()}
            self.session = ApiKeySession(self._config, self._whylabs_client)
        else:
            raise ValueError(f"Unknown session type: {session_type}")

    @staticmethod
    def init(session_config: SessionConfig) -> "SessionManager":
        if SessionManager.__instance is None:
            SessionManager.__instance = SessionManager(session_config)
        else:
            logger.debug("SessionManager is already initialized. Ignoring call to init()")

        return SessionManager.__instance

    @staticmethod
    def reset() -> None:
        SessionManager.__instance = None

    @staticmethod
    def get_instance() -> Optional["SessionManager"]:
        return SessionManager.__instance

    @staticmethod
    def is_active() -> bool:
        return SessionManager.get_instance() is not None


def init(
    reinit: bool = False,
    allow_anonymous: bool = True,
    allow_local: bool = False,
    whylabs_api_key: Optional[str] = None,
    default_dataset_id: Optional[str] = None,
) -> None:
    """
    Set up authentication for this whylogs logging session. There are three modes that you can authentiate in.

    1. WHYLABS: Data is sent to WhyLabs and is associated with a specific WhyLabs account. You can get a WhyLabs api
        key from the WhyLabs Settings page after logging in.
    2. WHYLABS_ANONYMOUS: Data is sent to WhyLabs, but no authentication happens and no WhyLabs account is required.
        Sessions can be claimed into an account later on the WhyLabs website.
    3. LOCAL: No authentication. No data is automatically sent anywhere. Use this if you want to explore profiles
        locally or manually upload them somewhere.

    Typically, you should only have to put `why.init()` with no arguments at the start of your application/notebook/script.
    The arguments allow for some customization of the logic that determines the session type. Here is the priority order:

    - If there is an api key directly supplied to init, then use it and authenticate session as WHYLABS.
    - If there is an api key in the environment variable WHYLABS_API_KEY, then use it and authenticate session as WHYLABS.
    - If there is an api key in the whylogs config file, then use it and authenticate session as WHYLABS.
    - If we're in an interractive environment (notebook, colab, etc.) then prompt the user to pick a method explicitly.
        The options are determined by the allow* argument values to init().
    - If allow_anonymous is True, then authenticate session as WHYLABS_ANONYMOUS.
    - If allow_local is True, then authenticate session as LOCAL.

    Args:
        reinit: Normally, init() is idempotent, so you can run it over and over again in a notebook without any issues, for example.
            If reinit=True then it will run the initialization logic again, so you can switch authentication methods without restarting.
        allow_anonymous: If True, then the user will be able to choose WHYLABS_ANONYMOUS if no other authentication method is found.
        allow_local: If True, then the user will be able to choose LOCAL if no other authentication method is found.
        whylabs_api_key: A WhyLabs api key to use for uploading profiles. There are other ways that you can set an api key that don't
            require direclty embedding it in code, like setting WHYLABS_API_KEY env variable or supplying the api key interractively
            via the init() prompt in a notebook.
        default_dataset_id: The default dataset id to use for uploading profiles. This is only used if the session is authenticated.
            This is a convenience argument so that you don't have to supply the dataset id every time you upload a profile if
            you're only using a single dataset id.

    """
    if reinit:
        SessionManager.reset()

    session_config = SessionConfig(
        InitConfig(
            allow_anonymous=allow_anonymous,
            allow_local=allow_local,
            whylabs_api_key=whylabs_api_key,
            default_dataset_id=default_dataset_id,
        )
    )

    try:
        SessionManager.init(session_config)
        session_config.notify_session_type()
    except PermissionError as e:
        logger.warning("Could not create or read configuration file for session. Profiles won't be uploaded.", e)
    except Exception as e:
        logger.warning("Could not initialize session", e)


_missing_session_warned = False

_INIT_DOCS = "https://docs.whylabs.ai/docs/whylabs-whylogs-init"


def get_current_session() -> Optional[Session]:
    global _missing_session_warned
    manager = SessionManager.get_instance()
    if manager is not None:
        return manager.session

    if not _missing_session_warned:
        logger.warning(
            f"No session found. Call whylogs.init() to initialize a session and authenticate. See {_INIT_DOCS} for more information."
        )
        _missing_session_warned = True

    return None
