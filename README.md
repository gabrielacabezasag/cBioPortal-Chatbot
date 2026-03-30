# cBioPortal-Chatbot

Dieses Projekt implementiert einen intelligenten Chatbot, der das Large Language Model (LLM) des FAU High-Performance Computing (HPC) mit der biomedizinischen Middleware BioMCP verbindet. Ziel ist es, komplexe biomedizinische Anfragen in natürliche Sprache zu verarbeiten und relevante Daten aus der cBioPortal-Datenbank abzurufen. Das Projekt dient als praktische Anwendung und technische Untersuchung im Rahmen einer Bachelorarbeit, die sich mit der Integration von LLMs in spezialisierte biomedizinische Dateninfrastrukturen befasst.


## Installation und Einrichtung

Um den Chatbot lokal auszuführen, folgen Sie bitte diesen Schritten:

### 1. BioMCP installieren und starten

Stellen Sie sicher, dass `uv` auf Ihrem System installiert ist. Falls nicht, installieren Sie es:

curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.cargo/env

Installieren Sie BioMCP über `uv`:

uv tool install biomcp

Starten Sie BioMCP in einem Terminalfenster. Achten Sie darauf, dass es im `serve-http` Modus auf Port 3000 läuft:

uv run --with biomcp-python biomcp run --mode streamable_http --host 127.0.0.1 --port 3000

Warten Sie, bis Uvicorn running on http://127.0.0.1:3000 (Press CTRL+C to quit) im Terminal erscheint.

### 2. Python-Backend einrichten

Klonen Sie dieses Repository oder laden Sie die Dateien herunter:

git clone https://github.com/gabrielacabezasag/cBioPortal-Chatbot.git
cd cBioPortal-Chatbot

Installieren Sie die benötigten Python-Abhängigkeiten:

pip install -r requirements.txt

*Hinweis: Eine `requirements.txt` Datei sollte die Pakete `openai` und `requests` enthalten.*

## Nutzung

Starten Sie das Backend-Skript in einem **zweiten Terminalfenster**:

export LLMAPI_KEY="Deine API-Key"
python backend.py


Sobald der Chatbot die Meldung `Du: ` anzeigt, können Sie Fragen in natürlicher Sprache stellen. Beispiele:

*   "Welche Studien haben Daten zu BRAF-Mutationen bei Melanomen?"
*   "Zeige mir die Genexpression von TP53 in Brustkrebsstudien."
*   "Was sind die häufigsten Mutationen im EGFR-Gen bei Lungenkrebs?"

Um den Chatbot zu beenden, tippen Sie `exit` oder drücken Sie `STRG+C`.

## Fehlerbehebung und Debugging

*   **Verbindungsfehler?** Überprüfen Sie, ob BioMCP auf dem korrekten Host (`127.0.0.1`) und Port (`3000`) läuft und ob keine Firewall die Verbindung blockiert.
*   **API-Key Fehler?** Nutzen Sie `test.py` um die Funktionalität Ihres FAU API-Keys isoliert zu überprüfen.
