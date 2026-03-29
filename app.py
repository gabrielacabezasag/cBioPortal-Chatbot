from fastapi import FastAPI, HTTPException
import subprocess
import json

app = FastAPI()

BIOMCP_URL = "http://127.0.0.1:8000/mcp"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/biomcp/tools")
def biomcp_tools():
    return {"tools": [{"name": "article.search", "via": "biomcp article ..."},
                      {"name": "trial.search", "via": "biomcp trial ..."},
                      {"name": "variant.search", "via": "biomcp variant ..."}, ]}


@app.post("/literature")
def literature(req: dict):
    """Expected JSON body example: {"genes":["KRAS"], "diseases": ["COAD"], "keywords": ["2020"]}"""
    genes = req.get("genes", [])
    diseases = req.get("diseases", [])
    keywords = req.get("keywords", [])
    if not genes and not diseases and not keywords:
        raise HTTPException(status_code=400, detail="Provide at least one of: genes, disease, keywords")
    cmd = ["biomcp", "article", "search", "--json"]
    for g in genes:
        cmd += ["--gene", str(g)]
    for d in diseases:
        cmd += ["--disease", str(d)]
    for k in keywords:
        cmd += ["--keyword", str(k)]
    page = req.get("page", 1)
    if page:
        cmd += ["--page", str(int(page))]
    try:
        out = subprocess.check_output(cmd, text=True)
        return json.loads(out)
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=502, detail=(e.output or str(e)))
    except json.JSONDecodeError:
        return {"raw": out}
