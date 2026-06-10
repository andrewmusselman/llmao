FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY hayward/ ./hayward/
COPY litellm/ ./litellm/
ENV HAYWARD_HOST=0.0.0.0 HAYWARD_PORT=8080
EXPOSE 8080
# Production note: front this with hypercorn and set HAYWARD_AUTH_MODE=asf,
# HAYWARD_LITELLM_MODE=proxy. For the simplest run, the built-in server is fine.
CMD ["python", "-m", "hayward.app"]
