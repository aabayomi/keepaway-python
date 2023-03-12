from logging import Logger

import team_config
from lib.debug.debug_client import DebugClient
from lib.debug.os_logger import get_logger
from lib.debug.sw_logger import SoccerWindow_Logger
from lib.rcsc.game_time import GameTime


class DebugLogger:
    def __init__(self):
        self._sw_log: SoccerWindow_Logger = None
        self._os_log: Logger = None
        self._debug_client: DebugClient = None

    def setup(self, team_name, unum, time: GameTime):
        self._sw_log = SoccerWindow_Logger(team_name, unum, time)
        self._os_log = get_logger(unum, team_config.OUT == team_config.OUT_OPTION.UNUM)
        self._debug_client = DebugClient()

    def sw_log(self):
        return self._sw_log

    def os_log(self):
        return self._os_log

    def debug_client(self):
        return self._debug_client


log = DebugLogger()
