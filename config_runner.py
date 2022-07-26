from subprocess import Popen, CREATE_NEW_CONSOLE
from typing import Any, Dict, List, Union
import time
import os
import yaml
import requests
import json
import urllib.parse
import argparse

parser = argparse.ArgumentParser()

parser.add_argument(
    "--folder_path",
    type=str,
    default="Configs/dino-continuous-new",
    help="Path to the folder with configs. ML Agents is going to be ran iteratively, with configs passed as "
         "arguments. Base port is the only command argument which is going to be passed as the additional argument.",
)

parser.add_argument(
    "--num_parallel",
    type=int,
    default="2",
    help="Number of ML Agents instances, which are going to be ran in parallel",
)

parser.add_argument(
    "--max_workers",
    type=int,
    default="3",
    help="Maximum number of concurrently active Unity executable instances",
)

parser.add_argument(
    "--base_port",
    type=int,
    default="5005",
    help="Ports for Unity subprocesses are going to be reassigned to during training",
)


class StopCondition:
    tb_api = 'http://localhost:6006/data/plugin/scalars/scalars?'

    def __init__(self, params: Dict[str, Any]):
        assert 'tag' in params, 'No tag found in stop condition.'
        self.tag: str = params['tag']
        self.min: float = float(params['min'] if 'min' in params else -999999999)
        self.max: float = float(params['max'] if 'max' in params else 999999999)
        self.max = max(self.max, self.min)
        self.step: int = int(params['step'] if 'step' in params else 0)
        print(f'Found stop condition - {self}')

    def evaluate(self, run_id: str):
        args: Dict[str, str] = {'run': run_id, 'tag': self.tag}
        url: str = StopCondition.tb_api + urllib.parse.urlencode(args)
        try:
            r = requests.get(url=url, verify=False, timeout=5)
            if r.status_code == requests.codes.ok:
                data: List[List[float]] = json.loads(r.text)
                step = data[-1][1]  # Latest step
                value: float = data[-1][2]  # Latest scalar
                if step >= self.step:
                    if value < self.min:
                        return True, f'{self.tag}: {value} < {self.min} [step: {step}]'
                    elif value > self.max:
                        return True, f'{self.tag}: {value} > {self.max} [step: {step}]'
            # else:
            # log(r.text)
            # No scalar data yet.
        except:
            print('Could not connect to TensorBoard.')

        return False, None

    def __eq__(self, other):
        return self.tag == other.tag

    def __str__(self) -> str:
        return f'tag: {self.tag}, step: {self.step}, min: {str(self.min)}, max: {str(self.max)}'


class ConfigRunner:
    def __init__(self, folder_path, num_parallel, max_workers, base_port):
        self.slot_ports: List[List[int]] = [None] * num_parallel
        self.slots: List[Popen] = [None] * num_parallel
        self.short_run_ids: List[str] = [None] * num_parallel
        self.verbose_run_ids: List[List[str]] = [None] * num_parallel
        self.verbose_run_ids_for_configs: List[List[str]] = [[]]
        self.base_port = base_port
        self.max_workers = max_workers
        self.run_count: int = 0
        self.active_ports = []
        self.stop_conditions = []
        self.stop_conditions_temp = []
        self.all_short_run_ids = []
        self.num_envs_in_configs = []
        self.incomplete_runs = []
        self.config_paths = self.get_configs_from_folder(folder_path)
        self.parse_stop_conditions()

        print(f'Results folder is located at {os.path.abspath(os.getcwd())}')

    def parse_stop_conditions(self):
        for i, config_path in enumerate(self.config_paths):
            config = self.parse_yaml_config(config_path)
            self.parse_config(config)

            run_id = config['checkpoint_settings']['run_id']
            self.verbose_run_ids_for_configs.append([])
            for k, v in config['behaviors'].items():
                self.verbose_run_ids_for_configs[i].append(f'{run_id}\{k}')

        for cond in self.stop_conditions_temp:
            if cond not in self.stop_conditions:
                self.stop_conditions.append(cond)

    @staticmethod
    def get_configs_from_folder(path):
        files = []

        for file in os.listdir(path):
            if file.endswith('.yaml'):
                files.append(file)

        # https://stackoverflow.com/questions/44721221/natural-sort-of-list-containing-paths-in-python
        files = sorted(files, key=lambda i: int(os.path.splitext(os.path.basename(i))[0]))

        return [os.path.abspath(os.path.join(path, str(f))) for f in files]

    def parse_config(self, config: Dict[str, Any], key: str = None) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for k, v in config.items():
            if 'num_envs' in k:
                self.num_envs_in_configs.append(v)
            if 'run_id' in k:
                self.all_short_run_ids.append(v)
            if 'opt_stop' in k:
                self.stop_conditions_temp.append(StopCondition(v))
            if isinstance(v, dict):
                v = self.parse_config(v, k)
            if 'opt_' not in k:
                result[k] = v
        return result

    def run_controller(self, interval: int = 10):
        interrupt: bool = False

        while self.has_active_runs() or self.has_pending_runs():
            try:
                self.handle_current_slots()

                self.handle_process_starting()

                time.sleep(interval)

            except KeyboardInterrupt:
                interrupt = True
                for i, slot in enumerate(self.slots):
                    if slot:
                        self.stop_process(i)
                break

        if interrupt:
            print('Training was interrupted.')
        elif self.incomplete_runs:
            print(f'The runs {self.incomplete_runs} were not run to completion')
        else:
            print('All training runs complete.')

    def handle_process_starting(self):
        while self.has_pending_runs() and self.max_workers >= len(self.active_ports) + self.num_envs_in_configs[self.run_count]:
            i: int = self.get_free_slot()

            if i > -1:
                self.start_process(i)
            else:
                break

    def handle_current_slots(self):
        if self.has_active_runs():
            print(f'Checking current slots {self.short_run_ids}')
            for i, slot in enumerate(self.slots):
                if slot:
                    id: str = self.short_run_ids[i]
                    if slot.poll() is not None:
                        code: int = self.slots[i].returncode
                        if code is 0:
                            print(f'{id} complete.')
                        else:
                            self.incomplete_runs.append(id)
                            print(f'An error {code} occurred in {id}')
                        self.slots[i].kill()  # TODO do we need this?
                        self.slots[i] = None
                        # print(f'Removed slot {i} from {self.slot_ports} slot ports while there are {self.active_ports} active ports')
                        for p in self.slot_ports[i]:
                            self.active_ports.remove(p)
                        self.slot_ports[i] = None
                        # print(f'Now there are {self.slot_ports} slot ports and {self.active_ports} active ports')
                    elif self.must_stop(i):
                        self.stop_process(i)

    def start_process(self, i: int) -> None:
        n: int = self.run_count
        self.run_count += 1

        run_ports = self.get_free_ports(self.num_envs_in_configs[n])
        #print(f'Started run {self.run_count-1} in slot {i} ports {run_ports} while there are {self.slot_ports} slot ports and {self.active_ports} active ports')
        args: List[str] = ['mlagents-learn', self.config_paths[n],
                           f'--base-port={run_ports[0]}']
        # Windows only
        self.slots[i] = Popen(args, creationflags=CREATE_NEW_CONSOLE)

        run_id: str = self.all_short_run_ids[n]
        self.slot_ports[i] = run_ports
        for run_port in run_ports:
            self.active_ports.append(run_port)

        self.short_run_ids[i] = run_id
        self.verbose_run_ids[i] = self.verbose_run_ids_for_configs[n]
        print(f'{run_id} started.')
        #print(f'Now there are {self.slot_ports} slot ports and {self.active_ports} active ports')

    """Returns a starting port for a run of the given number of environments"""
    def get_free_ports(self, amount):
        start_offset = 0
        while True:
            candidate_ports = [self.base_port + start_offset + i for i in range(amount)]
            start_offset += 1
            should_continue = False

            for port in candidate_ports:
                if port in self.active_ports:
                    should_continue = True
                    break

            if should_continue:
                continue
            else:
                return candidate_ports

    def stop_process(self, i: int):
        # Windows only
        self.slots[i].terminate()
        self.slots[i] = None

    def must_stop(self, i: int) -> bool:
        for cond in self.stop_conditions:
            for id in self.verbose_run_ids[i]:
                stop, reason = cond.evaluate(id)
                if stop:
                    print(f'Stopping {self.short_run_ids[i]} because {reason}')
                    return True
        return False

    def has_pending_runs(self) -> bool:
        return self.run_count < len(self.config_paths)

    def has_active_runs(self) -> bool:
        for slot in self.slots:
            if slot is not None:
                return True
        return False

    def get_free_slot(self) -> int:
        for i, slot in enumerate(self.slots):
            if slot is None:
                return i
        return -1

    @staticmethod
    def parse_yaml_config(source_config_path):
        try:
            with open(source_config_path) as f:
                return yaml.load(f, Loader=yaml.FullLoader)
        except FileNotFoundError:
            print(f'Could not load configuration from {source_config_path}. File not found.')


if __name__ == "__main__":
    args = parser.parse_args()

    runner = ConfigRunner(args.folder_path, args.num_parallel, args.max_workers, args.base_port)
    runner.run_controller()
