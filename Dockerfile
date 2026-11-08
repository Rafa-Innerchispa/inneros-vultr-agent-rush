FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && useradd -r -u 10001 app
COPY inneros_agent_rush ./inneros_agent_rush
RUN mkdir /data && chown app:app /data
USER app
EXPOSE 8000
# This container intentionally has NO Docker socket. Code execution fails closed.
CMD ["uvicorn", "inneros_agent_rush.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
