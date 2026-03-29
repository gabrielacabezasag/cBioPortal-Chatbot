import requests
import json
import time


def diagnose_sse(url):
    print(f"--- DIAGNOSE: Verbinde zu {url} ---")
    headers = {"Accept": "text/event-stream"}
    try:
        # stream=True ist entscheidend für SSE
        with requests.get(url, headers=headers, stream=True, timeout=30) as r:
            print(f"Status Code: {r.status_code}")
            print(f"Response Headers: {dict(r.headers)}")

            print("\n--- Warte auf Daten (10 Sekunden) ---")
            start_time = time.time()
            for line in r.iter_lines():
                if time.time() - start_time > 10:
                    print("\n--- Diagnose beendet (Zeitlimit erreicht) ---")
                    break

                if line:
                    decoded_line = line.decode('utf-8')
                    print(f"RAW LINE: {decoded_line}")

                    if decoded_line.startswith("data:"):
                        data_content = decoded_line[5:].strip()
                        print(f"  DATA CONTENT: {data_content}")
                        try:
                            json_data = json.loads(data_content)
                            print(f"  JSON PARSED: {json.dumps(json_data, indent=2)}")
                        except:
                            print("  JSON PARSE FAILED")
    except Exception as e:
        print(f"FEHLER: {e}")


if __name__ == "__main__":
    diagnose_sse("http://127.0.0.1:3000/mcp")
