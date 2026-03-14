from fastapi import FastAPI

app = FastAPI(title="Lineaf Parser")


@app.get("/health")
async def health():
    return {"status": "ok"}
