from enum import Enum
from typing import TYPE_CHECKING
from lib.math.vector_2d import Vector2D
from lib.player.messenger.messenger_memory import MessengerMemory
from lib.rcsc.game_time import GameTime

from lib.rcsc.server_param import ServerParam
if TYPE_CHECKING:
    from lib.player.world_model import WorldModel
    
    
class Messenger:
    class Types(Enum):
        BALL_POS_VEL_MESSAGE = 'b'
        PLAYER_POS_VEL_UNUM = 'P'
        NONE = ''
    
   
    
    SIZES: dict[Types, int] = {
        Types.BALL_POS_VEL_MESSAGE: 6,
        Types.PLAYER_POS_VEL_UNUM: 4, # TODO CHECK SIZE
    }
    
    def __init__(self) -> None:
        self._type: Messenger.Types = Messenger.Types.NONE
        self._size: int = 0
        self._message: str = None
        self._header: str = None
    
    def encode(self, wm: 'WorldModel') -> str:
        pass
    
    def decode(self, messenger_memory: MessengerMemory, sender: int, current_time: GameTime) -> None:
        pass
    
    def size(self):
        return self._size
    
    def type(self):
        return self._type
    
    @staticmethod
    def encode_all(wm: 'WorldModel', messages: list['Messenger']):
        max_message_size = ServerParam.i().player_say_msg_size()
        size = 0
        all_messages = ""
        for i, message in enumerate(messages):
            enc = message.encode(wm)
            
            if len(enc) + size > max_message_size:
                print("(Messenger encode all) out of limitation. Deny other messages.")
                print("denied messages are:")
                for denied in messages[i:]:
                    print(denied)
                break
            
            all_messages += enc
            size += len(enc)
        return all_messages
    
    @staticmethod
    def decode_all(messenger_memory: MessengerMemory, messages: str, sender: int, current_time: GameTime):
        from lib.player.messenger.ball_pos_vel_messenger import BallPosVelMessenger
        from lib.player.messenger.player_pos_unum_messenger import PlayerPosUnumMessenger

        messenger_classes: dict[Messenger.Types, type['Messenger']] = {
            Messenger.Types.BALL_POS_VEL_MESSAGE: BallPosVelMessenger,
            Messenger.Types.PLAYER_POS_VEL_UNUM: PlayerPosUnumMessenger,
        }

        index = 0
        while index < len(messages):
            message_type = Messenger.Types(messages[index])
            message_size = Messenger.SIZES[message_type]

            message = messages[index: index+message_size]
            
            messenger_classes[message_type](message=message).decode(messenger_memory, sender, current_time)
            index += message_size
            
            
            
            
            