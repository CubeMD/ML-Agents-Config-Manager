call activate ML-Agents-Config-Manager
cd ..
python scripts/config_generator.py --source-config-path=Configs/Dino_Delayed_Base.yaml
call conda deactivate
pause