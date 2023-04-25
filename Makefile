.PHONY: logs test 

lines?=all
stage?=dev

compose=sudo docker-compose -f $(stage).yml

test:
	sudo docker-compose -f test.yml up --build --abort-on-container-exit

build:
	$(compose) up --build -d 

logs:
	$(compose) logs -f --tail=$(lines)

stop:
	$(compose) stop

shell:
	$(compose) exec web ./manage.py shell_plus

ps:
	$(compose) ps

down:
	$(compose) down

web-build:
	$(compose) up --build -d web
web-logs:
	$(compose) logs -f --tail=$(lines) web

createsuperuser:
	$(compose) exec web ./manage.py createsuperuser

bot-build:
	$(compose) up --build -d bot
bot-logs:
	$(compose) logs -f --tail=$(lines) bot

full-migrate: makemigrations migrate

makemigrations:
	$(compose) exec web ./manage.py makemigrations
migrate:
	$(compose) exec web ./manage.py migrate

collectstatic:
	$(compose) exec web ./manage.py collectstatic

scanner-fbuild:
	$(compose) up --build -d --force-recreate scanner
scanner-build:
	$(compose) up --build -d scanner
scanner-logs:
	$(compose) logs -f --tail=$(lines) scanner
scanner-stop:
	$(compose) stop scanner

celery-build:
	$(compose) up --build -d celery celery_beat
celery-logs:
	$(compose) logs -f --tail=$(lines) celery celery_beat
celery-stop:
	$(compose) stop celery celery_beat

websockets-build:
	$(compose) up --build -d websockets
websockets-logs:
	$(compose) logs -f --tail=$(lines) websockets

redis-logs:
	$(compose) logs -f --tail=$(lines) redis


fixtures: web-build
	$(compose) exec web python manage.py create_fixtures

pre-commit:
	pip install pre-commit --upgrade
	pre-commit install -t pre-commit -t prepare-commit-msg
