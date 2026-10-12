FROM python:3.13-slim
WORKDIR /app
COPY requirements.lock.txt .
RUN pip install --no-cache-dir -r requirements.lock.txt && useradd -r -u 10001 agent
COPY agent_service agent_service
COPY knowledge knowledge
USER agent
EXPOSE 8001
CMD ["python", "-m", "uvicorn", "agent_service.api:create_app", "--factory", "--host", "0.0.0.0", "--port", "8001"]
