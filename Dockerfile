FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY llmao/ ./llmao/
COPY litellm/ ./litellm/
ENV LLMAO_HOST=0.0.0.0 LLMAO_PORT=8080
EXPOSE 8080
# Production note: front this with hypercorn and set LLMAO_AUTH_MODE=asf,
# LLMAO_LITELLM_MODE=proxy. For the simplest run, the built-in server is fine.
CMD ["python", "-m", "llmao.app"]
