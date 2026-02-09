import time
import os
from kubernetes import client, config
from openai import OpenAI

from google import genai
from google.genai.errors import APIError

import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def log(msg):
    """Prints message with UTC timestamp"""
    print(f"[{datetime.datetime.utcnow().isoformat()}] {msg}")


# -------------------------------
# Email Alert Function (ADDED)
# -------------------------------
EMAIL_TO = os.getenv("ALERT_EMAIL_TO")
EMAIL_FROM = os.getenv("ALERT_EMAIL_FROM")
EMAIL_PASS = os.getenv("ALERT_EMAIL_PASS")

def send_email(subject, body):
    """Send alert email using Gmail SMTP."""
    if not EMAIL_FROM or not EMAIL_PASS or not EMAIL_TO:
        log("EMAIL: Missing EMAIL_FROM / EMAIL_PASS / EMAIL_TO environment variables.")
        return

    msg = MIMEMultipart()
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(EMAIL_FROM, EMAIL_PASS)
        server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
        server.quit()
        log(f"📧 Email alert sent to {EMAIL_TO}")
    except Exception as e:
        log(f"EMAIL ERROR: {e}")


# -------------------------------
# 1. Load OpenAI API Key
# -------------------------------
if "OPENAI_API_KEY" not in os.environ:
    print("FATAL: Missing OPENAI_API_KEY")
    exit(1)
client_gemini = genai.Client(api_key=os.environ['OPENAI_API_KEY'])


# -------------------------------
# 2. Load Kubernetes Config
# -------------------------------
try:
    config.load_incluster_config()
    v1 = client.CoreV1Api()
except Exception as e:
    print(f"FATAL: Could not load Kubernetes configuration: {e}")
    v1 = None

NAMESPACE = "default"


# -------------------------------
# 3. Crash Detection (FIXED)
# -------------------------------
def get_crashing_pods():
    if not v1:
        return []

    crashed = []

    try:
        pods = v1.list_namespaced_pod(NAMESPACE).items
    except Exception as e:
        print("ERROR fetching pods:", e)
        return []

    for pod in pods:
        container_statuses = pod.status.container_statuses or []

        for cs in container_statuses:
            waiting = cs.state.waiting
            term = cs.state.terminated
            last_term = cs.last_state.terminated

            # Print debug info
            log(
                f"DEBUG: {pod.metadata.name} | "
                f"waiting={waiting.reason if waiting else None} | "
                f"term_exit={term.exit_code if term else None} | "
                f"last_term_exit={last_term.exit_code if last_term else None} | "
                f"restarts={cs.restart_count}"
            )

            # ---- Correct CrashLoopBackOff detection ----
            if waiting and waiting.reason == "CrashLoopBackOff":
                crashed.append(pod)
                break

            if term and term.exit_code != 0:
                crashed.append(pod)
                break

            if last_term and last_term.exit_code != 0:
                crashed.append(pod)
                break

            if cs.restart_count > 3:
                crashed.append(pod)
                break

    return crashed


# -------------------------------
# 4. Fetch Logs
# -------------------------------
def fetch_pod_context(pod):
    name = pod.metadata.name
    try:
        logs = v1.read_namespaced_pod_log(name, NAMESPACE, tail_lines=40)
    except Exception:
        logs = "Could not fetch logs."
    return logs


# -------------------------------
# 5. GPT Diagnosis
# -------------------------------
def diagnose_with_gpt(pod_name, logs):
    prompt = f"""
    A Kubernetes pod '{pod_name}' is crashing (CrashLoopBackOff).

    Analyze these logs and provide:
    - Root cause
    - Possible fix
    - What to check next

    Logs:
    {logs}
    """

    try:
        response = client_gemini.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                temperature=0.2
            )
        )
        return response.text

    except Exception as e:
        return f"AI Error: {e}"


# -------------------------------
# 6. Main Agent Loop
# -------------------------------
def run_simple_agent():
    print("🤖 SRE AI Agent Started — monitoring for crashed pods...")

    while True:
        crashed = get_crashing_pods()

        if not crashed:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] All systems nominal.")
        else:
            for pod in crashed:
                name = pod.metadata.name
                print("\n" + "-" * 60)
                print(f"🚨 Crash Detected → {name}")

                logs = fetch_pod_context(pod)
                print("\n--- LOGS ---")
                print(logs)

                diag = diagnose_with_gpt(name, logs)
                print("\n--- AI DIAGNOSIS ---")
                print(diag)
                print("-" * 60)

                # -------------------------
                # EMAIL ALERT (ADDED)
                # -------------------------
                email_body = f"""
🚨 Kubernetes Crash Alert

Pod: {name}

--- Logs ---
{logs}

--- AI Diagnosis ---
{diag}
"""
                send_email(
                    subject=f"K8s Crash Alert: {name}",
                    body=email_body
                )

        time.sleep(30)


# -------------------------------
# 7. Run
# -------------------------------
if __name__ == "__main__":
    run_simple_agent()
