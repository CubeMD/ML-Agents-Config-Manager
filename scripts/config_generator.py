from typing import Any, Dict, List
import os
import yaml
import argparse

parser = argparse.ArgumentParser()

parser.add_argument(
    "--source-config-path",
    type=str,
    help="Path to the source config file that will be used to generate config combinations. Run id has to be "
         "specified (has to be NOT opt_values) and the base port will be ignored.",
)

parser.add_argument(
    "--destination-folder-path",
    type=str,
    default="Configs",
    help="Path to the folder where a new folder will be created to store all modified config files. "
         "The new folder will be named after the source config run id. If the folder already exists, "
         "the configs inside of it will be overwritten.",
)


class SourceConfigRunIdException(Exception):
    pass


class ValueOption:
    def __init__(self, key: str, values: List[Any]):
        self.key: str = key
        self.values: List[Any] = values
        print(f'Found config param option - {self}')

    def __str__(self) -> str:
        return f'{KeyUtil.simple(self.key)}: {", ".join(map(str, self.values))}'


class KeyUtil:
    incr = 0
    join = '___'

    def unique(key: str) -> str:
        KeyUtil.incr += 1
        return key + KeyUtil.join + str(KeyUtil.incr)

    def simple(key: str) -> str:
        return key.split(KeyUtil.join)[0]


class ConfigGenerator:
    def __init__(self, source_config_path, destination_folder_path):
        self.source_config = self.parse_yaml_config(source_config_path)

        if 'env_settings' in self.source_config.keys() and 'base_port' in self.source_config['env_settings'].keys():
            print('There should be no base port defined in the source config. Key value pair is going to be '
                  'ignored.')
            del self.source_config['env_settings']['base_port']

        if 'checkpoint_settings' not in self.source_config.keys() \
                or 'run_id' not in self.source_config['checkpoint_settings'].keys() \
                or 'opt_values' in self.source_config['checkpoint_settings']['run_id']:
            raise SourceConfigRunIdException('Run id has to be defined and not contain opt_values, exiting')

        self.source_run_id = self.source_config['checkpoint_settings']['run_id']
        self.destination_path = os.path.join(destination_folder_path, self.source_run_id)

        self.value_options: List[ValueOption] = []
        self.generated_configs: List[Dict[str, Any]] = []
        self.generated_configs_info: List[str] = []

    @staticmethod
    def parse_yaml_config(source_config_path):
        try:
            with open(source_config_path) as f:
                return yaml.load(f, Loader=yaml.FullLoader)
        except FileNotFoundError:
            print(f'Could not load configuration from {source_config_path}. File not found.')

    def generate_configs_and_info(self):
        parsed: Dict[str, Any] = self.parse_config(self.unique_keys(self.source_config))

        if self.value_options:

            param_names: List[str] = [x.key for x in self.value_options]
            value_combos: List[List[Any]] = self.get_value_combinations()
            for i, value_combo in enumerate(value_combos):
                mod_config: Dict[str, Any] = self.insert_values(parsed, param_names, value_combo)
                mod_config_simple = self.simple_keys(mod_config)
                mod_config_simple['checkpoint_settings']['run_id'] = self.source_run_id + '-' + str(i)

                self.generated_configs.append(mod_config_simple)

                value_info: List[str] = [f'\n{self.source_run_id}-{str(i)}\n']
                for j, param_name in enumerate(param_names):
                    key: str = KeyUtil.simple(param_name)
                    value_info.append(f'  - {key}: {str(value_combo[j])}\n')
                self.generated_configs_info.extend(value_info)

            if not os.path.exists(self.destination_path):
                os.makedirs(self.destination_path)

            self.save_info(self.generated_configs_info, self.destination_path)
            self.save_configs(self.destination_path)

        else:
            print('No options found, nothing was created, exiting')

    def parse_config(self, config: Dict[str, Any], key: str = None) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for k, v in config.items():
            if 'opt_values' in k:
                self.value_options.append(ValueOption(key, v))
            if isinstance(v, dict):
                v = self.parse_config(v, k)
            if 'opt_' not in k:
                result[k] = v
        return result

    def get_value_combinations(self, result: List[List[Any]] = None, tmp: List[Any] = None, i: int = 0) -> List[List[Any]]:
        n: int = len(self.value_options)
        result: List[List[Any]] = [] if result is None else result
        tmp: List[Any] = [None] * n if tmp is None else tmp
        for v in self.value_options[i].values:
            tmp[i] = v
            if i is n - 1:
                result.append(tmp.copy())
            else:
                self.get_value_combinations(result, tmp, i + 1)
        return result

    def insert_values(self, config: Dict[str, Any], param_names: List[str], values: List[Any]) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for k, v in config.items():
            if isinstance(v, dict):
                v = self.insert_values(v, param_names, values)
            result[k] = values[param_names.index(k)] if k in param_names else v
        return result

    @staticmethod
    def save_info(info: List[str], dir: str):
        path: str = os.path.join(dir, "config_info.txt")
        try:
            with open(path, "w") as f:
                for line in info:
                    f.write(line)
        except FileNotFoundError:
            print(f'Could not save configuration info to {path}. Upper folder probably does not exist')

    def save_configs(self, destination_folder_path):
        for i, config in enumerate(self.generated_configs):
            self.save_config(config, destination_folder_path, str(i))

    @staticmethod
    def save_config(config: Dict[str, Any], dir: str, name: str):
        path: str = os.path.join(dir, name + ".yaml")
        try:
            with open(path, 'w') as f:
                try:
                    yaml.dump(config, f, sort_keys=False)
                except TypeError:  # Older versions of pyyaml don't support sort_keys
                    yaml.dump(dir, f)
        except FileNotFoundError:
            print(f'Could not save configuration to {path}. Upper folder probably does not exist')

    def unique_keys(self, config: Dict[str, Any], key: str = None, ignore: bool = False) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for k, v in config.items():
            if isinstance(v, dict):
                v = self.unique_keys(v, k, ignore or 'opt_' in k)
            result[k if ignore or 'opt_' in k else KeyUtil.unique(k)] = v
        return result

    def simple_keys(self, config: Dict[str, Any], key: str = None) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for k, v in config.items():
            if isinstance(v, dict):
                v = self.simple_keys(v, k)
            result[KeyUtil.simple(k)] = v
        return result


if __name__ == "__main__":
    args = parser.parse_args()

    source_config_path = args.source_config_path
    destination_folder_path = args.destination_folder_path

    generator = ConfigGenerator(source_config_path, destination_folder_path)
    generator.generate_configs_and_info()
