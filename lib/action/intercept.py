import math

from lib.action.basic_actions import TurnToPoint
from lib.action.go_to_point import GoToPoint
from lib.action.intercept_info import InterceptInfo
from lib.action.intercept_table import InterceptTable
from lib.math.vector_2d import Vector2D
from lib.player.object_player import PlayerObject
from lib.player.templates import PlayerAgent, WorldModel
from lib.rcsc.server_param import ServerParam


class Intercept:
    def __init__(self, save_recovery: bool = True,
                 face_point: Vector2D = Vector2D.invalid()):
        self._save_recovery = save_recovery
        self._face_point = face_point

    def execute(self, agent: PlayerAgent):
        wm = agent.world()

        if self.do_kickable_opponent_check(agent):
            return True

        table = wm.intercept_table()
        if table.self_reach_cycle() > 100:
            final_point = wm.ball().inertia_final_point()
            GoToPoint(final_point,
                      2,
                      ServerParam.i().max_dash_power()).execute(agent)
            return True

        best_intercept: InterceptInfo = self.get_best_intercept(wm, table)
        target_point = wm.ball().inertia_point(best_intercept.reach_cycle())
        if best_intercept.dash_cycle() == 0:
            face_point = self._face_point.copy()
            if not face_point.is_valid():
                face_point.assign(50.5, wm.self().pos().y() * 0.75)

            TurnToPoint(face_point,
                        best_intercept.reach_cycle()).execute(agent)
            return True

        if best_intercept.turn_cycle() > 0:
            my_inertia = wm.self().inertia_point(best_intercept.reach_cycle())
            target_angle = (target_point - my_inertia).th()
            if best_intercept.dash_power() < 0:
                target_angle -= 180

            return agent.do_turn(target_angle - wm.self().body())

        if self.do_wait_turn(agent, target_point, best_intercept):
            return True

        if self._save_recovery and not wm.self().stamina_model().capacity_is_empty():
            consumed_stamina = best_intercept.dash_power()
            if best_intercept.dash_power() < 0:
                consumed_stamina *= -2

            if (wm.self().stamina() - consumed_stamina
                    < ServerParam.i().recover_dec_thr_value() + 1):
                agent.do_turn(0)
                return False

        return self.do_inertia_dash(agent,
                                    target_point,
                                    best_intercept)

    def do_kickable_opponent_check(self,
                                   agent: PlayerAgent) -> bool:
        wm = agent.world()
        if wm.ball().dist_from_self() < 2 and wm.exist_kickable_opponents():
            opp: PlayerObject = wm.opponents_from_ball()[0]
            if opp is not None:
                goal_pos = Vector2D(-ServerParam.i().pitch_half_length(), 0)
                my_next = wm.self().pos() + wm.self().vel()
                attack_pos = opp.pos() + opp.vel()

                if attack_pos.dist2(goal_pos) > my_next.dist2(goal_pos):
                    GoToPoint(attack_pos,
                              0.1,
                              ServerParam.i().max_dash_power(),
                              -1,
                              1,
                              True,
                              15).execute(agent)
                    return True
        return False

    def get_best_intercept(self, wm: WorldModel,
                           table: InterceptTable) -> InterceptInfo:
        SP = ServerParam.i()
        cache = table.self_cache()

        if len(cache) == 0:
            return InterceptInfo()

        goal_pos = Vector2D(65, 0)
        our_goal_pos = Vector2D(-SP.pitch_half_length(), 0)
        max_pitch_x = SP.pitch_half_length() - 1
        max_pitch_y = SP.pitch_half_width() - 1
        penalty_x = SP.our_penalty_area_line_x()
        penalty_y = SP.penalty_area_half_width()
        speed_max = wm.self().player_type().real_speed_max() * 0.9
        opp_min = table.opponent_reach_cycle()
        mate_min = table.teammate_reach_cycle()

        attacker_best: InterceptInfo = None
        attacker_score = 0.0

        forward_best: InterceptInfo = None
        forward_score = 0.0

        noturn_best: InterceptInfo = None
        noturn_score = 10000.0

        nearest_best: InterceptInfo = None
        nearest_score = 10000.0

        goalie_best: InterceptInfo = None
        goalie_score = -10000.0

        goalie_aggressive_best: InterceptInfo = None
        goalie_aggressive_score = -10000.0

        MAX = len(cache)
        for i in range(MAX):

            if self._save_recovery and cache[i].mode() != InterceptInfo.Mode.NORMAL:
                continue

            cycle = cache[i].reach_cycle()
            self_pos = wm.self().inertia_point(cycle)
            ball_pos = wm.ball().inertia_point(cycle)
            ball_vel = wm.ball().vel() * SP.ball_decay() ** cycle

            if ball_pos.absX() > max_pitch_x or \
                    ball_pos.absY() > max_pitch_y:
                continue

            if (wm.self().goalie()
                    and wm.last_kicker_side() != wm.our_side()
                    and ball_pos.x() < penalty_x - 1
                    and ball_pos.absY() < penalty_y - 1
                    and cycle < opp_min - 1):
                if ((cache[i].turn_cycle() == 0
                     and cache[i].ball_dist() < wm.self().player_type().catchable_area() * 0.5)
                        or cache[i].ball_dist() < 0.01):
                    d = ball_pos.dist2(our_goal_pos)
                    if d > goalie_score:
                        goalie_score = d
                        goalie_best = cache[i]

            attacker = False
            if (ball_vel.x() > 0.5
                    and ball_vel.r2() > speed_max ** 2
                    and cache[i].dash_power >= 0
                    and ball_pos.x() < 47
                    and (ball_pos.x() > 35
                         or ball_pos.x() > wm.offside_line_x())):
                attacker = True

            opp_rate = 0.95 if attacker else 0.7
            if cycle >= opp_min * opp_rate:
                continue

            # attacker type
            if attacker:
                goal_dist = 100 - min(100, ball_pos.dist(goal_pos))
                x_diff = 47 - ball_pos.x()
                score = ((goal_dist / 100)
                         * math.e ** (-(x_diff ** 2) / (2 * 100)))

                if score > attacker_score:
                    attacker_best = cache[i]
                    attacker_score = score

                continue

            # no turn type
            if cache[i].turn_cycle() == 0:
                score = cycle
                if score < noturn_score:
                    noturn_best = cache[i]
                    noturn_score = score
                continue

            # forward type
            if ball_vel.x() > 0.1 and \
                    cycle <= opp_min - 5 and \
                    ball_vel.r2() > 0.6 ** 2:
                score = (100 ** 2
                         - min(100 ** 2, ball_pos.dist2(goal_pos)))

                if score > forward_score:
                    forward_best = cache[i]
                    forward_score = score
                continue

            # other: select nearest one
            d = self_pos.dist2(ball_pos)
            if d < nearest_score:
                nearest_best = cache[i]
                nearest_score = d

        if goalie_aggressive_best is not None:
            return goalie_aggressive_best

        if goalie_best is not None:
            return goalie_best

        if attacker_best is not None:
            return attacker_best

        if noturn_best is not None and forward_best is not None:
            noturn_ball_vel = (wm.ball().vel()
                               * SP.ball_decay() ** noturn_best.reach_cycle())
            noturn_ball_speed = noturn_ball_vel.r()
            if (noturn_ball_vel.x > 0.1
                    and (noturn_ball_speed > speed_max
                         or noturn_best.reach_cycle() <= forward_best.reach_cycle() + 2)):
                return noturn_best

        if forward_best is not None:
            return forward_best

        fastest_pos = wm.ball().inertia_point(cache[0].reach_cycle())
        fastest_vel = wm.ball().vel() * SP.ball_decay() ** cache[0].reach_cycle()

        if ((fastest_pos.x() > -33
             or fastest_pos.absY() > 20)
                and (cache[0].reach_cycle() >= 10
                     or fastest_vel.r() < 1.2)):
            return cache[0]

        if noturn_best is not None and nearest_best is not None:
            noturn_self_pos = wm.self().inertia_point(noturn_best.reach_cycle())
            noturn_ball_pos = wm.ball().inertia_point(noturn_best.reach_cycle())
            nearest_self_pos = wm.self().inertia_point(nearest_best.reach_cycle())
            nearest_ball_pos = wm.ball().inertia_point(nearest_best.reach_cycle())

            if noturn_self_pos.dist2(noturn_ball_pos) < nearest_self_pos.dist2(nearest_ball_pos):
                return noturn_best

            if nearest_best.reach_cycle() <= noturn_best.reach_cycle() + 2:
                nearest_ball_vel = (wm.ball().vel()
                                    * SP.ball_decay() ** nearest_best.reach_cycle())
                nearest_ball_speed = nearest_ball_vel.r()
                if nearest_ball_speed < 0.7:
                    return nearest_best

                noturn_ball_vel = (wm.ball().vel()
                                   * SP.ball_decay() ** noturn_best.reach_cycle())
                if (nearest_best.ball_dist() < wm.self().player_type().kickable_area() - 0.4
                        and nearest_best.ball_dist() < noturn_best.ball_dist()
                        and noturn_ball_vel.x() < 0.5
                        and noturn_ball_vel.r2() > 1 ** 2
                        and noturn_ball_pos.x() > nearest_ball_pos.x()):
                    return nearest_best

                nearest_self_pos = wm.self().inertia_point(nearest_best.reach_cycle())
                if nearest_ball_speed > 0.7 and \
                        nearest_self_pos.dist2(nearest_ball_pos) < wm.self().player_type().kickable_area():
                    return nearest_best
            return noturn_best

        if noturn_best is not None:
            return noturn_best

        if nearest_best is not None:
            return nearest_best

        if (wm.self().pos().x() > 40
                and wm.ball().vel().r() > 1.8
                and wm.ball().vel().th().abs() < 100
                and cache[0].reach_cycle() > 1):
            chance_best: InterceptInfo = None
            for i in range(MAX):
                if (cache[i].reach_cycle() <= cache[0].reach_cycle() + 3
                        and cache[i].reach_cycle <= opp_min - 2):
                    chance_best = cache[i]

            if chance_best is not None:
                return chance_best
            
        return cache[0]