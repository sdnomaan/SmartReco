from fastapi import FastAPI

app = FastAPI(
    title="SmartReco",
    description="Behavioral AI Recommendation Engine",
    version="1.0.0",
)


@app.get("/")
def home():
    return {
        "app": "SmartReco",
        "status": "running",
        "message": "Behavioral recommendation engine is online.",
    }