FROM python:3.7

ENV PYTHONUNBUFFERED=1

RUN mkdir /code
WORKDIR /code

RUN pip install --upgrade pip==20.2.4
RUN apt-get update && apt-get install -y netcat
COPY requirements /code/requirements
RUN pip install -r requirements/dev.txt

EXPOSE 8000

COPY . /code/

COPY ./entrypoint.sh /
RUN chmod +x /entrypoint.sh

COPY ./compose/dev/start /start
RUN chmod +x /start

COPY ./compose/start-celery /start-celery
RUN chmod +x /start-celery

COPY ./compose/start-celerybeat /start-celerybeat
RUN chmod +x /start-celerybeat

COPY ./compose/start-scanner /start-scanner
RUN chmod +x /start-scanner

COPY ./compose/start-websockets /start-websockets
RUN chmod +x /start-websockets

ENTRYPOINT ["/entrypoint.sh"]
