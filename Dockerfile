FROM n8nio/n8n:1.71.1

USER root

# Instalar Python y herramientas de compilación (necesarias para pandas en Alpine)
RUN apk add --update --no-cache python3 py3-pip python3-dev g++ make libffi-dev

# Crear entorno virtual e instalar las librerías que pediste en el .env
# Instalamos pandas y requests
RUN pip install --no-cache-dir --break-system-packages pandas requests

# Enlace simbólico para usar 'python'
RUN ln -sf /usr/bin/python3 /usr/bin/python

USER node