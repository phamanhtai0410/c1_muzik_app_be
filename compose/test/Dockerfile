FROM python:3.7-buster

ENV PYTHONUNBUFFERED=1

RUN mkdir /code
WORKDIR /code

RUN pip install --upgrade pip==20.2.4
RUN apt-get update && apt-get install -y netcat
COPY requirements /code/requirements
RUN pip install -r requirements/test.txt

COPY . /code/

COPY ./entrypoint.sh /
RUN chmod +x /entrypoint.sh

COPY ./compose/test/start /start
RUN chmod +x /start

ENTRYPOINT ["/entrypoint.sh"]
