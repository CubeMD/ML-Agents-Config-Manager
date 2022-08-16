call activate ML-Agents-Config-Manager
cd ..
python scripts/config_runner.py --folder_path=Configs/dino --num_parallel=1 --max_workers=3
call conda deactivate
pause