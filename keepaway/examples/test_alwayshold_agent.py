from __future__ import absolute_import, division, print_function

import time
from absl import logging

logging.set_verbosity(logging.DEBUG)
from keepaway.envs.keepaway_env import KeepawayEnv
from keepaway.envs.policies.always_hold import AlwaysHoldPolicy

from keepaway.config.game_config import get_config
config = get_config()["3v2"]

def main():
    env = KeepawayEnv(config)
    episodes = 1000000
    env.launch_game()
    agents = env.num_keepers
    policy = AlwaysHoldPolicy(config)
    env.render()
    for e in range(episodes):
        print(f"Episode {e}")
        env.reset()
        terminated = False
        episode_reward = 0
        env.start()

        while not terminated:
            obs = env.get_obs()
            actions, agent_infos = policy.get_actions(obs)
            # print("actions ", actions)

            reward, terminated, info = env.step(actions)
            # print("reward ", reward, "terminated ", terminated, "info ", info)
            # print("matrix jfjfj ", env.get_proximity_adj_mat())
            time.sleep(0.15)
            episode_reward += reward

    print("closing game")
    env.close()


if __name__ == "__main__":
    main()
