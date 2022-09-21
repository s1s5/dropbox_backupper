FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1

RUN pip instlal dropbox

RUN mkdir -p /opt
WORKDIR /opt
COPY backup.py ./

