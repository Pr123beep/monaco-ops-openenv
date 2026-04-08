from uvicorn import run

def main():
    run("app:app", host="0.0.0.0", port=7860)