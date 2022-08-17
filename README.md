


# ML-Agents Config Manager

Tools for generating multiple configs from a single one and scheduling training runs for all configs in the folder.

## About

The purpose of this repo is to simplify the installation of ML-Agents, provide a few additional features, and speed up the training routine.

If you have game-development background, you might be unfamiliar with Python and package management, which is a big part of it. However, it is an unnecessary complication if you just want to train an agent. Installing and using this repository does not require any interaction with the console.

The workflow is designed around batch files and creating new console windows, therefore Windows is the only supported OS. If you would like to use the scripts directly, I suggest looking into the commands in batch files.

The Nvidia GPU newer than 1050 is required for GPU training (don't forget to specify it in the config).

For illustration purposes, I have added files that I used for hyperparameter search and training of the [Dino](https://github.com/CubeMD/Dino) agent. The build is lightweight enough to be included too.
                                                                                                                                                                                 
## Installation

1. Clone the project using a version control system of your choice.
2. Download and install the [Anaconda](https://www.anaconda.com/products/individual). It is important to select `Just Me` in `Install for:` step and add Anaconda to the path to allow you to use the included batch files.
3. Open `Anaconda Navigator` once to finish up the installation. Just close it when it finishes loading.
4. Run `Install.bat` (to be able to train using both CPU and GPU)
5. (Optional) If you have less than 32 Gigs of RAM you will most probably need to increase the amount of virtual memory
  
## Configs

I suggest taking a look at the [descriptions](https://github.com/Unity-Technologies/ml-agents/blob/main/docs/Training-Configuration-File.md) of hyperparameters and [training](https://github.com/Unity-Technologies/ml-agents/blob/main/docs/Training-ML-Agents.md) in the ML-Agents documentation. The structure of the config is exactly the same, except for `opt_values`.

1. Open the `Configs` folder and either edit or copy the `Dino_Base.yaml` config. This config contains almost all possible hyperparameters and some suggested values. Defining an `opt_value` as a value of a parameter will result in all possible combinations of the values being generated in separate configs. It's important to define the `run_id` as it is going to be used as the name of both the folder and the base name of sub-configs. Do not define the`base_port` as it is going to be assigned automatically.
<pre> behaviors:
	Dino:
		trainer_type: ppo
		hyperparameters:
			batch_size:
				<b>opt_values: [16, 32, 64]</b>
		network_settings:  
			vis_encoder_type:
				<b>opt_values: [simple, fully_connected]</b></pre>
				
2. Adjust `source-config-path` in `generate_dino_from_base.bat`. This batch file will create a new folder and populate it with generated configs and a `config_info.txt` file, which lists individual value combinations associated with run IDs. If there is a folder with the same `run_id`, delete or rename it. 
 
3. Run `generate_dino_from_base.bat` or `python scripts/config_generator.py --source-config-path=Configs/Dino_Base.yaml` from the root of the project and with the appropriate Anaconda environment activated to generate the configs.  

## Training

The batch files used for training are stored in the `DinoTraining` folder. 

- `Dino_editor.bat` simply activates an appropriate Anaconda environment and starts a regular ML-Agents training with the config path as a parameter.

- `Dino.bat` activates an appropriate Anaconda environment and launches the main process. There are parameters such as `--folder_path=Configs/dino --num_parallel=2 --max_workers=12 --base_port=5015` that should be provided. `Num_parallel` is responsible for the number of concurrent ML-Agents sub-processes and `max_workers` corresponds to the total maximum number of Unity executables. If the `num_envs` in the next config would make the total number of current executables exceed `max_workers` then the main process is going to wait before starting it.

- `start_tensorboard.bat` starts a Tensorboard from the root folder.

![runs](/Images/runs.png)

## Notes

- `Results` folder should be manually cleaned as ML-Agents would fail if a run with the same `run_id` exists.

- To stop the training, select the main console which reports slots and press `Ctrl + C`

- Running multiple instances of ML-Agents results in pseudo-parallelization, but there is a large memory overhead. I had to increase the amount of virtual memory to a ridiculous 64 Gigs to get rid of warnings when running more than 4 instances (each of them running 3 executables). For some reason, memory utilization reported in the task manager stays in a reasonable range. The speed of individual training runs is unaffected if the number of workers is less than the amount of cores in your CPU.

- ML-Agents sub-process closes up automatically upon completion. It makes it impossible to figure out the reasons for crashes, as logs are not saved to the file. Currently, if it crashes, I test the config directly with ML-Agents. The main reasons for crashes are: the results folder contains a run with the same name, port is occupied, virtual memory is insufficient or something wrong with the config file.

- Training with multiple behaviours per config has not been tested.

- The functionality of `opt_stop` is currently unsupported due to the splitting of config generation and running into different scripts. I will address this issue soon.

- I would like to extend the functionality of the default ML-Agents and simplify the training routine further. Ideally, it should be possible to configure and start the default training loop from within the Unity Editor.

- Workflow should be more streamlined, i.e. trained models should be automatically added to the project, make builds automatically?

- The area of hyperparameter search is largely unexplored. At the moment, you are not even able to set up the order of experiments and only grid search is supported. ML-Agents supports initialization of new runs from already existing models, which should make implementation of Population Based Training pretty straightforward. It could be possible to make a setup using Ray clusters (without RLLib) to bring it to its extreme.

## Credits

I would like to thank mbaske for the [original](https://github.com/mbaske/ml-agents-hyperparams) codebase. This repository is primarily based on his work and features only slight modifications:

- Introduction of batch files for installation, generation of configs, and running the training.

- The original code was split into config generation and running, as it corresponds to my workflow better. However, the ability to train from base config is probably going to be reintroduced.

- ML-Agents sub-process is called with two parameters - `config_path` and `base_port`. The generated config now contains all the parameters required for the training, including `engine_settings`, `checkpoint_settings`,  `torch_settings` and `environment_parameters`, not only the `behaviors`.

- The main contribution is the ability to launch multiple ML-Agents trainers in separate console windows. Only the `base_port` needs to be defined. All executable ports are going to be offset accordingly and reused upon release.
