call activate ML-Agents-Config-Manager
python config_runner.py --folder_path=Configs/dino-delayed --num_parallel=4 --max_workers=12 --base_port=5015
call conda deactivate
pause