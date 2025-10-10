from flask import Flask, jsonify
import argparse

app = Flask(__name__)

def ensure_datasets_installed():
    import importlib.util
    import subprocess
    import sys
    if importlib.util.find_spec("datasets") is None:
        print("Installing 'datasets' package...", flush=True)
        subprocess.check_call([sys.executable, "-m", "pip", "install", "datasets"])

def pull_prompts_db():
    ensure_datasets_installed()
    from datasets import load_dataset
    ds = load_dataset("hellaswag", split="validation")
    return ds[0]["ctx_a"]

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200

@app.route("/launch_ollama_clients", methods=["POST"])
def launch_ollama_clients_api():
    try:
        result = pull_prompts_db()
        return jsonify({"success": True, "prompt": result}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5000, help="Port to run the Ollama client server on")
    args = parser.parse_args()
    app.run(host="0.0.0.0", port=args.port)