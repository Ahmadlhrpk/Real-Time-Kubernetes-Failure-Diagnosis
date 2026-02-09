FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY sre_agent_simple.py . /app/
ENV PYTHONUNBUFFERED=1
CMD ["python3", "-u", "/app/sre_agent_simple.py"]
