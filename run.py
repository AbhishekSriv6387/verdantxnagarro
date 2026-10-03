"""Start the local demo (install requirements once first)."""
import os
import subprocess
import sys
from pathlib import Path

if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    os.chdir(root)
    local_python = root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if local_python.exists() and Path(sys.executable).resolve() != local_python.resolve():
        raise SystemExit(subprocess.call([str(local_python), str(root / "run.py"), *sys.argv[1:]]))
    if "--test" in sys.argv:
        raise SystemExit(subprocess.call([sys.executable, "-m", "pytest", "-q"]))
    from dotenv import load_dotenv
    import uvicorn

    load_dotenv()
    uvicorn.run("app.api.main:app", host=os.getenv("HOST", "127.0.0.1"),
                port=int(os.getenv("PORT", "8000")), access_log=False)
