# 

<img alt="Code style: black" src="https://img.shields.io/badge/code%20style-black-000000.svg?style=plastic"></a>

This repository uses [pre-commit](https://pre-commit.com/).

Please before committing to this repository do
```
make pre-commit
```

## Makefile
Below are the make commands. By default, these commands for **dev** stage. If you want to use it for **prod**, you must specify variable **stage**=prod. If you only need to see the last 20 lines of logs, you can use variables **lines**=20.

| Command | Description |
| --- | --- |
| pre-commit | Activating pre-commits with linters. |
| test | Run tests on separate images. |
| fixtures | Creating model instances from config.yaml |
| build | Creation and launch of the project. |
| logs | Project logs.  |
| stop | Stops the entire project. |
| web-build | Creation and launch of the web. |
| web-logs | Web logs. |
| createsuperuser | Create superuser. |
| makemigrations | Makemigrations. |
| migrate | Migrate. |
| full-migrate | Applies makemigrations and migrate at once. |
| scanner-build | Creation and launch of the scanner. |
| scanner-fbuild | Creation and launch of the scanner with --force-recreate. |
| scanner-logs | Scanner logs. |
| scanner-stop | Stop scanner. |
| celery-build | Creation and launch of the celery. |
| celery-logs | Celery logs. |
| celery-stop | Stop celery. |
