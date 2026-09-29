FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/srv

WORKDIR /srv
COPY frontend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY frontend /srv/frontend

RUN useradd --create-home --uid 10002 parkwise && chown -R parkwise:parkwise /srv
USER parkwise

EXPOSE 8501
CMD ["streamlit", "run", "frontend/streamlit_app.py", "--server.address=0.0.0.0", "--server.port=8501"]
