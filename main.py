# main.py
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from diagrams import Diagram
from diagrams.aws.compute import EC2
from diagrams.aws.network import ELB
from diagrams.aws.database import RDS
from diagrams.aws.storage import S3

TMP_DIR = Path("/tmp/diagrams")
TMP_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Simple Diagrams Test")

def generate_simple_diagram() -> Path:
    file_base = TMP_DIR / "simple_arch"
    file_path = file_base.with_suffix(".png")

    if file_path.is_file():
        return file_path

    with Diagram(
        name="Simple AWS architecture",
        filename=str(file_base),
        outformat="png",
        show=False,
    ):
        user = ELB("User / Frontend")
        web = EC2("Backend API")
        db = RDS("Database")
        bucket = S3("Static Files")

        user >> web >> db
        web >> bucket

    return file_path

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/diagram")
def diagram():
    path = generate_simple_diagram()
    if not path.is_file():
        raise HTTPException(status_code=500, detail="Diagram not generated")
    return FileResponse(path, media_type="image/png")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
