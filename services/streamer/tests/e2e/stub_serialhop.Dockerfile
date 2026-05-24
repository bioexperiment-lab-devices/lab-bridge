FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libavdevice61 libavfilter10 libavformat61 libavcodec61 libavutil59 \
    libswscale8 libswresample5 libsrtp2-1 libopus0 libvpx9 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir 'fastapi==0.115.*' 'uvicorn[standard]==0.30.*' \
    'aiortc>=1.10.0' 'httpx==0.28.*'

COPY stub_serialhop.py /stub.py

ENV PYTHONPATH=/
EXPOSE 8001
CMD ["uvicorn", "stub:app", "--host", "0.0.0.0", "--port", "8001"]
