FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1

RUN pip install --upgrade pip && pip install dropbox

RUN mkdir -p /opt
WORKDIR /opt
COPY backup.py ./

