import time
import numpy as np
from dowel import logger, tabular
from keepaway.garage.misc.prog_bar_counter import ProgBarCounter
from keepaway.garage.sampler.batch_sampler import BatchSampler

from keepaway.envs import REGISTRY as env_REGISTRY
from keepaway.envs.keepaway_env import KeepawayEnv



class CentralizedMAOnPolicySampler(BatchSampler):
# class CentralizedMAOnPolicySampler(B):
    """
    Args:
        algo (keepaway.garage.np.algos.RLAlgorithm): An algorithm instance.
        env (keepaway.garage.envs.keepaway.garageEnv): An environement instance.
    """

    def __init__(self, algo, env, 
                 batch_size=60000, 
                 n_trajs_limit=None,
                 limit_by_traj=False):
        super().__init__(algo, env)
        # self._env = env
        self._env = env_REGISTRY["keepaway"](num_keepers=3, num_takers=2, pitch_size=20)
        self.tot_num_env_steps = 0
        self.limit_by_traj = limit_by_traj
        self.batch_size = batch_size
        self.n_trajs_limit = n_trajs_limit
        self.n_samples = 0
        self.n_trajs = 0

        if limit_by_traj:
            assert n_trajs_limit is not None
        else:
            assert batch_size is not None
    
    def reset_sample_counters(self):
        self.n_samples = 0
        self.n_trajs = 0
    
    def loop_flag(self):
        return self.n_trajs < self.n_trajs_limit if self.limit_by_traj \
            else self.n_samples < self.batch_size
    

    ## TODO: clean up this function

    def convert_to_numpy(self,proxy):
        if isinstance(proxy, dict):
            regular_dict = dict
        else:
            regular_dict = dict(proxy)
        values = [item if isinstance(item, np.ndarray) else item['state_vars'] for item in regular_dict.values()] 
        # for i in range(len(values)):
        #     print("values ", values[i], "length ", len(values[i]))
        # print("values ", values[0], "length ", len(values[0]))
        numpy_array = np.stack(values, axis=0)
        return numpy_array

    def obtain_samples(self, itr, tbx):
        """
            batch_size is the number of env_steps
        """

        logger.log('Obtaining samples for iteration %d...' % itr)

        paths = []

        self.reset_sample_counters()

        if hasattr(self._env, 'curriculum_learning'):
            obses = self._env.reset(itr)
        else:
            obses = self._env.reset()

        running_path = None

        pbar = ProgBarCounter(self.n_trajs_limit if self.limit_by_traj 
                              else self.batch_size)
        policy_time = 0
        env_time = 0
        process_time = 0

        policy = self.algo.policy

        if self._env._run_flag == False:
            self._env._launch_game()
            self._env.render()
            # self.reset()
            self._env._run_flag = True
            
        terminated = False
        episode_return = 0
        self._env.start()

        while self.loop_flag():
            if not self._env._is_game_started():
                time.sleep(1)
            
            t = time.time()
            policy.reset(True)
            avail_actions = self._env.get_avail_actions()
            # print("adjacent matrix ", self._env.get_proximity_adj_mat(False,False,True))

            if self.algo.policy.proximity_adj:
                adj = self._env.get_proximity_adj_mat() # renormalized adj
                alive_mask = None
            else:
                adj = None # will be computed by policy
                alive_mask = np.array(self._env.alive_mask) 
                # most primitive form, (n_agents, )
            
            # print("obses ", obses)
            ob = obses[0]
            # print("ob ", ob)
            obs_ = self.convert_to_numpy(ob)

            # ob = obs_n_reshape2 = obs_n.reshape(1, 39)

            actions, _ = policy.get_actions(obs_, avail_actions, 
                adjs=adj, alive_masks=alive_mask)

            adj = np.asarray(adj)
            adj = np.reshape(adj, (-1,)) # flatten like obses

            policy_time += time.time() - t
            t = time.time()
            state = obs_.flatten()
            
            rewards, dones, env_infos = self._env.step(actions)
            env_time += time.time() - t
            t = time.time()
            
            if running_path is None:
                running_path = dict(observations=[],
                                    states=[],
                                    actions=[],
                                    avail_actions=[],
                                    alive_masks=[],
                                    rewards=[],
                                    adjs=[],
                                    dones=[])
            running_path['observations'].append(obs_.flatten())
            running_path['states'].append(state)
            running_path['actions'].append(actions)
            running_path['avail_actions'].append(avail_actions)
            running_path['alive_masks'].append(alive_mask)
            running_path['rewards'].append(rewards)
            running_path['dones'].append(dones)
            running_path['adjs'].append(adj)
            
            # print("running_path ", running_path)

            # obses = next_obses

            if dones:
                paths.append(
                    dict(observations=np.asarray(running_path['observations']),
                         states=np.asarray(running_path['states']),
                         actions=np.asarray(running_path['actions']),
                         avail_actions=np.asanyarray(running_path['avail_actions']),
                         alive_masks=np.asanyarray(running_path['alive_masks']),
                         rewards=np.asarray(running_path['rewards']),
                         dones=np.asarray(running_path['dones']),
                         adjs=np.asarray(running_path['adjs']),
                    )
                )
                self.n_samples += len(running_path['rewards'])
                self.n_trajs += 1
                self.tot_num_env_steps += len(running_path['rewards'])
                running_path = None
                obses = self._env.reset()
                if self.limit_by_traj:
                    pbar.inc(1)

            process_time += time.time() - t
            if not self.limit_by_traj:
                pbar.inc(1)
            # print(self.n_samples)
        # self._env.close()
    
        pbar.stop()

        tabular.record('PolicyExecTime', policy_time)
        tabular.record('EnvExecTime', env_time)
        tabular.record('ProcessExecTime', process_time)
        tabular.record('EnvSteps', self.tot_num_env_steps)
        tabular.record('BatchSize', self.n_samples)
        tabular.record('NumTrajs', self.n_trajs)

        tbx.add_scalar('train/env_steps', self.tot_num_env_steps, itr)
        tbx.add_scalar('train/batch_size', self.n_samples, itr)
        tbx.add_scalar('train/n_trajs', self.n_trajs, itr)
        
        return paths
