python3 -m venv env
source env/bin/activate
pip install pyyaml
pip install jsonschema

python test_validator.py

deactivate
rm -rf env