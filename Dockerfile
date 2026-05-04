FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY server.py .
COPY .env.example .

RUN mkdir -p /app/data/uploads/cv /app/data/uploads/excel /app/data/uploads/survey /app/data/processed /app/data/outputs/charts /app/data/outputs/reports /app/data/outputs/exports /app/logs

ENV DATA_DIR=/app/data
ENV UPLOAD_DIR=/app/data/uploads
ENV CV_UPLOAD_DIR=/app/data/uploads/cv
ENV EXCEL_UPLOAD_DIR=/app/data/uploads/excel
ENV SURVEY_UPLOAD_DIR=/app/data/uploads/survey
ENV PROCESSED_DIR=/app/data/processed
ENV OUTPUT_DIR=/app/data/outputs
ENV CHART_DIR=/app/data/outputs/charts
ENV REPORT_DIR=/app/data/outputs/reports
ENV EXPORT_DIR=/app/data/outputs/exports
ENV LOG_DIR=/app/logs
ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=8005
ENV MCP_TRANSPORT=sse
ENV LOG_LEVEL=INFO
ENV AUTO_LOAD_ENABLED=false

EXPOSE 8005

CMD ["python", "server.py"]
