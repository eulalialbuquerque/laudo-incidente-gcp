FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1
# Só biblioteca padrão do Python: nada para instalar.
COPY miniatura/ /app/
