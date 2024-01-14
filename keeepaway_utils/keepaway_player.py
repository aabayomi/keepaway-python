import time
from base.decision import (
    get_decision,
    get_decision_keepaway,
)

from base.sample_communication import SampleCommunication
from base.view_tactical import ViewTactical
from lib.action.go_to_point import GoToPoint
from lib.action.intercept import Intercept
from lib.action.neck_body_to_ball import NeckBodyToBall
from lib.action.neck_turn_to_ball import NeckTurnToBall
from lib.action.neck_turn_to_ball_or_scan import NeckTurnToBallOrScan
from lib.action.scan_field import ScanField
from lib.debug.debug import log
from lib.debug.level import Level

# from lib.player.keepaway_player_agent import PlayerAgent
from keeepaway_utils.kp_agent import PlayerAgent
from lib.rcsc.server_param import ServerParam
from lib.rcsc.types import GameModeType

from lib.debug.debug import log


class KeepawayPlayer(PlayerAgent):
    def __init__(
        self,
        team_name,
        shared_values,
        manager,
        lock,
        event,
        event_from_subprocess,
        main_process_event,
        world,
        obs,
        last_action_time,
        reward,
        terminated,
    ):
        # super().__init__()
        super().__init__(
            shared_values, manager, lock, event, world, reward,terminated, team_name
        )
        self._communication = SampleCommunication()
        self._count_list = shared_values  # actions
        self._barrier = manager  #
        self._event_from_subprocess = event_from_subprocess  #
        self._main_process_event = main_process_event
        self._real_world = world
        self._full_world = world
        self._obs = obs
        self._last_action_time = last_action_time
        self._reward = reward
        self._terminated = terminated

        # TODO: check the use of full or real world.
        # self._full_world = world

    def count(self):
        # Wait for all processes to be ready to start
        # print("count list", self._count_list)
        wm = self.world()
        self._barrier.wait()
        index = wm.self().unum()

        # Each process will increment its count in count_list by 1, 100 times
        for i in range(1, 101):
            with self._count_list.get_lock():
                self._count_list[index] = self._current_time.cycle()
                # print("count list", self._count_list)
            # print(list(self._count_list))

    def action_impl(self):
        wm = self.world()
        if self.do_preprocess():
            return

        # print("world: before decision", wm.time())

        # get_decision(self)
        # self.count()
        # print("world: ", self._real_world.time())
        # if self._reward.get_lock:
        #     print("reward here : ",  self._reward.value)
        # print("Passer is before com .. ", self._communication._current_sender_unum)
        # if self._communication.should_say_ball(self):
        #     print("Passer is .. ", self._communication._current_sender_unum)
        # self._communication.say_ball_and_players(self)

        get_decision_keepaway(
            self,
            self._count_list,
            self._barrier,
            self._event_from_subprocess,
            self._main_process_event,
            self._obs,
            self._last_action_time,
            self._reward,
            self._terminated,
            self._full_world,
        )

    def do_preprocess(self):
        wm = self.world()

        if wm.self().is_frozen():
            self.set_view_action(ViewTactical())
            self.set_neck_action(NeckTurnToBallOrScan())
            return True

        if not wm.self().pos_valid():
            self.set_view_action(ViewTactical())
            ScanField().execute(self)
            return True

        count_thr = 10 if wm.self().goalie() else 5
        if wm.ball().pos_count() > count_thr or (
            wm.game_mode().type() is not GameModeType.PlayOn
            and wm.ball().seen_pos_count() > count_thr + 10
        ):
            self.set_view_action(ViewTactical())
            NeckBodyToBall().execute(self)
            return True

        self.set_view_action(ViewTactical())

        if self.do_heard_pass_receive():
            return True

        return False

    def do_heard_pass_receive(self):
        wm = self.world()

        if (
            wm.messenger_memory().pass_time() != wm.time()
            or len(wm.messenger_memory().pass_()) == 0
            or wm.messenger_memory().pass_()[0]._receiver != wm.self().unum()
        ):
            return False

        self_min = wm.intercept_table().self_reach_cycle()
        intercept_pos = wm.ball().inertia_point(self_min)
        heard_pos = wm.messenger_memory().pass_()[0]._pos

        print("(sample palyer do heard pass) heard_pos={heard_pos}, intercept_pos={intercept_pos}".format(
            heard_pos=heard_pos, intercept_pos=intercept_pos
        ))

        log.sw_log().team().add_text(
            f"(sample palyer do heard pass) heard_pos={heard_pos}, intercept_pos={intercept_pos}"
        )

        if (
            not wm.kickable_teammate()
            and wm.ball().pos_count() <= 1
            and wm.ball().vel_count() <= 1
            and self_min < 20
        ):
            print(
                "sample player do heard pass) intercepting!", "i am ", wm.self().unum()
            )
            ## intercept pos == sender pos
            ## heard pos == receiver pos (where i should be to get the ball)
            log.sw_log().team().add_text(
                f"(sample palyer do heard pass) intercepting!, self_min={self_min}"
            )
            log.debug_client().add_message("Comm:Receive:Intercept")
            # Intercept().execute(self)
            GoToPoint(heard_pos, 0.5, ServerParam.i().max_dash_power()).execute(self)
            
            self.set_neck_action(NeckTurnToBall())
        else:
            print("(sample player do heard pass) go to point!,  cycle ", self_min, " i am ", wm.self().unum())

            log.sw_log().team().add_text(
                f"(sample palyer do heard pass) go to point!, cycle={self_min}"
            )
            log.debug_client().set_target(heard_pos)
            log.debug_client().add_message("Comm:Receive:GoTo")

            GoToPoint(heard_pos, 0.5, ServerParam.i().max_dash_power()).execute(self)
            self.set_neck_action(NeckTurnToBall())

        # TODO INTENTION?!?
