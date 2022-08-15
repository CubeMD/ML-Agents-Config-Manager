call activate ML-Agents-Config-Manager
python config_runner.py --folder_path=Configs/dino-continuous-50-sac-epochs --num_parallel=4 --max_workers=12
call conda deactivate
pause