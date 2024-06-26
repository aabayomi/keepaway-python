import time
from absl import logging
logging.set_verbosity(logging.DEBUG)
from keepaway.envs.keepaway_env import KeepawayEnv
from keepaway.envs.policies.handcoded_agent import HandcodedPolicy
from keepaway.config.game_config import get_config
config = get_config()["3v2"]


def main():
    env = KeepawayEnv(config)
    episodes = 20
    env.launch_game()
    policy = HandcodedPolicy(config)
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
            reward, terminated, info = env.step(actions)
            time.sleep(0.15)
            episode_reward += reward

    print("closing game")
    env.close()

if __name__ == "__main__":
    main()