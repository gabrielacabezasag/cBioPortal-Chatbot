import os
import json
import uuid
from typing import Any, Dict, Optional, List

import httpx
from openai import OpenAI

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://hub.nhr.fau.de/api/llmgw/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-oss-120b")
LLM_API_KEY = os.environ["LLMAPI_KEY"]

MCP_URL = os.getenv("BIOMCP_MCP_URL", "http://127.0.0.1:8000/mcp")
MCP_SESSION_ID = os.getenv("MCP_SESSION_ID", str(uuid.uuid4()))
NCI_API_KEY = os.getenv("NCI_API_KEY")


class McpStreamableHttpClient:
    def __init__(self, mcp_url: str, session_id: str):
        self.mcp_url = mcp_url.rstrip("/")
        self.session_id = session_id
        self._next_id = 1

    def ping(self) -> Dict[str, Any]:
        return self.call("ping", {})

    def _make_id(self) -> int:
        i = self._next_id
        self._next_id += 1
        return i

    def _endpoint(self) -> str:
        return f"{self.mcp_url}?session_id={self.session_id}"

    def _parse_sse_data_events(self, response: httpx.Response) -> List[Dict[str, Any]]:
        """
        Parse SSE and return only JSON-decoded payloads from `data:` lines.
        BioMCP sends JSON-RPC frames inside data lines.
        """
        data_events: List[Dict[str, Any]] = []
        for line in response.iter_lines():
            if not line:
                continue
            if line.startswith("data:"):
                payload = line[len("data:"):].strip()
                if payload == "[DONE]":
                    break
                try:
                    data_events.append(json.loads(payload))
                except json.JSONDecodeError:
                    # ignore non-JSON chunks
                    continue
        return data_events

    def _sse_to_jsonrpc(self, data_events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Heuristic: pick the last JSON object that looks like a JSON-RPC response
        (has jsonrpc + (result|error) and an id).
        """
        candidates = []
        for ev in data_events:
            if isinstance(ev, dict) and ev.get("jsonrpc") == "2.0" and "id" in ev and ("result" in ev or "error" in ev):
                candidates.append(ev)
        if candidates:
            return candidates[-1]
        # fallback: if server sends a wrapper format, return last event
        return data_events[-1] if data_events else {
            "jsonrpc": "2.0",
            "id": "client-error",
            "error": {"code": -32000, "message": "Empty SSE response from MCP server"}
        }

    def call(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        req_id = self._make_id()
        payload = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params or {}}

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }

        with httpx.Client(timeout=180.0) as client:
            r = client.post(self._endpoint(), headers=headers, json=payload)
            ct = (r.headers.get("content-type") or "").lower()

            if "text/event-stream" in ct:
                data_events = self._parse_sse_data_events(r)
                return self._sse_to_jsonrpc(data_events)

            # JSON response
            return r.json()

    def initialize(self) -> Dict[str, Any]:
        return self.call("initialize", {
            "clientInfo": {"name": "cbioportal-terminal-cli", "version": "0.2.0"},
            "capabilities": {}
        })

    def tools_list(self) -> Dict[str, Any]:
        return self.call("tools/list", {})

    def tool_call(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        return self.call("tools/call", {"name": name, "arguments": arguments})


def _tool_message_content(jsonrpc_resp: Dict[str, Any]) -> str:
    """
    Feed ONLY the result/error back to the LLM to avoid huge SSE logs.
    """
    if "error" in jsonrpc_resp:
        return json.dumps({"error": jsonrpc_resp["error"]}, ensure_ascii=False)
    return json.dumps({"result": jsonrpc_resp.get("result")}, ensure_ascii=False)


llm = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "think",
            "description": "BioMCP required first step: structured research planning / sequential thinking.",
            "parameters": {
                "type": "object",
                "properties": {
                    "thought": {"type": "string"},
                    "thoughtNumber": {"type": "integer", "minimum": 1},
                    "totalThoughts": {"type": "integer", "minimum": 1},
                    "nextThoughtNeeded": {"type": "boolean", "default": True},
                },
                "required": ["thought", "thoughtNumber", "totalThoughts"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search",
            "description": "BioMCP unified search. Required param: query.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "domain": {"type": ["string", "null"]},
                    "page": {"type": "integer", "default": 1},
                    "page_size": {"type": "integer", "default": 10},
                    "max_results_per_domain": {"type": ["integer", "null"]},
                    "explain_query": {"type": "boolean", "default": False},
                    "get_schema": {"type": "boolean", "default": False},
                    "call_benefit": {"type": ["string", "null"]},
                    "api_key": {"type": ["string", "null"]},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch",
            "description": "BioMCP fetch details for a specific record by id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "domain": {"type": ["string", "null"]},
                    "detail": {"type": ["string", "null"]},
                    "call_benefit": {"type": ["string", "null"]},
                    "api_key": {"type": ["string", "null"]},
                },
                "required": ["id"],
            },
        },
    },
]

SYSTEM = """You are a biomedical research assistant used inside cBioPortal.

Rules:
- For literature requests, you MUST call 'search' with domain='article' (or a unified query) and extract PMIDs from the tool results.
- Never invent PMIDs/NCT IDs/rsIDs. Only output identifiers that appear in tool output.
- Use 'fetch' to verify details for at least 1-2 key items if uncertain.

Workflow:
1) call 'think' once
2) call 'search' once (maybe twice max)
3) answer with IDs taken from tool output
"""


def _coerce_tool_args(tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    if tool_name in ("search", "fetch"):
        if args.get("api_key") in (None, "") and NCI_API_KEY:
            args["api_key"] = NCI_API_KEY
    return args


def _mcp_result(jsonrpc_resp: Dict[str, Any]) -> Any:
    if "error" in jsonrpc_resp:
        raise RuntimeError(f"MCP error: {jsonrpc_resp['error']}")
    return jsonrpc_resp.get("result")

def _extract_ids_from_search_result(result_obj: Any, max_n: int = 5) -> List[str]:
    """
    BioMCP search returns something like {"results":[{"id":...,"title":...,"text":...,"url":...}, ...]}
    but sometimes it's wrapped. We handle both.
    """
    if result_obj is None:
        return []
    if isinstance(result_obj, dict) and "results" in result_obj and isinstance(result_obj["results"], list):
        items = result_obj["results"]
    elif isinstance(result_obj, dict) and "content" in result_obj:
        # some servers return MCP content blocks; keep fallback simple
        return []
    else:
        return []

    ids = []
    for it in items:
        if isinstance(it, dict) and it.get("id"):
            ids.append(str(it["id"]))
        if len(ids) >= max_n:
            break
    return ids

def answer_with_biomcp_papers(mcp: McpStreamableHttpClient, question: str) -> str:
    # 1) think (optional but BioMCP likes it)
    _ = mcp.tool_call("think", {
        "thought": f"Plan: interpret question '{question}', then search articles and extract PMIDs.",
        "thoughtNumber": 1,
        "totalThoughts": 1,
        "nextThoughtNeeded": False
    })

    # 2) search explicitly in article domain
    search_resp = mcp.tool_call("search", {
        "query": "gene:BRAF AND (V600E OR p.V600E) AND disease:melanoma",
        "domain": "article",
        "page_size": 10,
        "page": 1
    })
    result_obj = _mcp_result(search_resp)
    pmids = _extract_ids_from_search_result(result_obj, max_n=5)

    # 3) If BioMCP didn't return IDs, fall back to a broader query
    if not pmids:
        search_resp = mcp.tool_call("search", {
            "query": "BRAF V600E melanoma",
            "domain": "article",
            "page_size": 10,
            "page": 1
        })
        result_obj = _mcp_result(search_resp)
        pmids = _extract_ids_from_search_result(result_obj, max_n=5)

    # 4) LLM formats answer, but is forced to only use given PMIDs
    messages = [
        {"role": "system", "content": "You are a biomedical research assistant. Do not invent PMIDs."},
        {"role": "user", "content": (
            f"User question: {question}\n\n"
            f"BioMCP returned these PMIDs/IDs (use ONLY these IDs): {pmids}\n"
            f"Write a German answer listing them as 5 papers with PMIDs. "
            f"If fewer than 5, say so."
        )},
    ]
    resp = llm.chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
        temperature=0.2,
    )
    return resp.choices[0].message.content or ""


def main():
    print("Starting BioMCP MCP client (streamable_http)…")
    print("MCP_URL      =", MCP_URL)
    print("SESSION_ID   =", MCP_SESSION_ID)

    mcp = McpStreamableHttpClient(MCP_URL, MCP_SESSION_ID)

    tools = mcp.tools_list()
    if "result" in tools and isinstance(tools["result"], dict):
        names = [t["name"] for t in tools["result"].get("tools", [])]
        print("tools:", ", ".join(names))
    else:
        print("tools/list error", tools.get("error"))

    while True:
        user = input("\nYou> ").strip()
        if user.lower() in ("exit", "quit"):
            break
        answer = answer_with_biomcp_papers(mcp, user)
        print("\nAssistant>\n" + answer)


if __name__ == "__main__":
    main()