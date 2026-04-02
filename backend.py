import json
import asyncio
import sys
import requests
import os
from asyncio import timeout
from http.client import responses
from datetime import timedelta
from mcp import ClientSession, types
from mcp.client.streamable_http import streamable_http_client

LLM_API_KEY = os.environ["LLMAPI_KEY"]
BIOMCP_URL = "http://127.0.0.1:3000/mcp"

async def run_chatbot():
    # Konfiguration
    fau_key = LLM_API_KEY
    fau_url = "https://hub.nhr.fau.de/api/llmgw/v1/chat/completions"
    fau_model = "gpt-oss-120b"

    print(f"\ncBioPortal Chatbot {fau_model}")

    # Chat-Historie initialisieren
    messages = [
        {"role": "system",
         "content": "Du bist ein hilfreicher Assistent für cBioPortal. Nutze das 'biomcp' Tool mit dem 'command' Parameter, um biomedizinische Fragen zu beantworten."}
    ]

    # Call BioMCP
    print(f"DEBUG: Verbinde mit BioMCP unter {BIOMCP_URL}...")
    try:
        async with streamable_http_client(
                BIOMCP_URL,
                terminate_on_close=False,
        ) as (r, w, _):
            async with ClientSession(
                    r,
                    w,
                    read_timeout_seconds=timedelta(seconds=60)
            ) as session:
                result = await session.initialize()
                print(f"DEBUG: BioMCP Server Info: {result.serverInfo}")

                while True:
                    user_input = input("\nDu: ")
                    if user_input.lower() in ["exit", "quit"]:
                        break

                    messages.append({"role": "user", "content": user_input})
                    call_result = await session.list_tools()

                    try:
                        # Anfrage an das FAU Gateway mit Tools
                        payload = {
                            "model": fau_model,
                            "messages": messages,
                            "tools": [{"type": "function",
                                      "function": json.loads(call_result.model_dump_json())["tools"][0]
                                      }],
                            "tool_choice": "auto",
                            "temperature": 0.7
                        }
                        headers = {
                            "Authorization": f"Bearer {fau_key}",
                            "Content-Type": "application/json"
                        }
                        response = requests.post(fau_url, json=payload, headers=headers)

                        if response.status_code != 200:
                            print(f"FEHLER VOM FAU-SERVER (Status {response.status_code}):")
                            print(response.text)
                            messages.pop()
                            continue

                        res_json = response.json()
                        resp_msg = res_json["choices"][0].get("message", {})

                        # Tool-Calling
                        if "tool_calls" in resp_msg and resp_msg["tool_calls"]:
                            print("DEBUG: LLM möchte ein Tool aufrufen.")
                            messages.append(resp_msg)

                            for tool_call in resp_msg["tool_calls"]:
                                function_name = "biomcp"
                                function_args = json.loads(tool_call["function"]["arguments"])
                                tool_call_id = tool_call["id"]

                                # BioMCP Tool aufrufen
                                print(f"DEBUG: Rufe BioMCP Tool '{function_name}' auf mit {function_args}...")
                                try:
                                    tool_output = await session.call_tool(function_name, function_args)

                                    tool_content = ""
                                    for content in tool_output.content:
                                        if isinstance(content, types.TextContent):
                                            tool_content += content.text + "\n"
                                            print(content.text)

                                    messages.append({
                                        "tool_call_id": tool_call_id,
                                        "role": "tool",
                                        "name": function_name,
                                        "content": tool_content,
                                    })

                                except Exception as e:
                                    print(f"FEHLER beim BioMCP Aufruf: {e}")
                                    messages.append({
                                        "tool_call_id": tool_call_id,
                                        "role": "tool",
                                        "name": function_name,
                                        "content": f"FEHLER beim BioMCP Aufruf: {e}",
                                    })

                            # Finale Antwort
                            print("DEBUG: Sende Tool-Ergebnis zurück an LLM für finale Antwort.")
                            final_response = requests.post(fau_url, json={"model": fau_model, "messages": messages},
                                                           headers=headers)

                            if final_response.status_code != 200:
                                print(
                                    f"FEHLER VOM FAU-SERVER (Status {final_response.status_code}) beim finalen Aufruf:")
                                print(final_response.text)
                                messages.pop()
                                continue

                            final_res_json = final_response.json()
                            final_resp_msg = final_res_json["choices"][0].get("message", {})
                            final_content = final_resp_msg.get("content", "Kein Inhalt in der finalen Antwort.")

                            print(f"\nChatbot: {final_content}")
                            messages.append({"role": "assistant", "content": final_content})
                        else:
                            content = resp_msg.get("content", "Kein Inhalt in der Antwort.")
                            print(f"\nChatbot: {content}")
                            messages.append({"role": "assistant", "content": content})
                    except Exception as e:
                        print(f"LOKALER FEHLER: {e}")
                        messages.pop()
    except Exception as e:
        print(f"VERBINDUNGSFEHLER: {e}")


if __name__ == "__main__":
    asyncio.run(run_chatbot())
