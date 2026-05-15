FROM python:3.13-slim
WORKDIR /app
RUN pip install --no-cache-dir 'fastapi>=0.115,<0.116' 'uvicorn[standard]>=0.30,<0.31'
COPY main.py /app/main.py
EXPOSE 9000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9000"]
