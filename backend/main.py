"""FastAPI app entrypoint."""

from fastapi import FastAPI

app = FastAPI(title="ClinicalCohort")


@app.get("/health")
def health():
    return {"status": "ok"}
