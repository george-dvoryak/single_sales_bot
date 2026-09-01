# Деплой: Mac ⇄ GitHub ⇄ PythonAnywhere

Заменяет схему «зазиповал — залил — скачал». Архивы больше не нужны.

## Модель: что где живёт

| | Где источник правды | В git? |
|---|---|---|
| Код (`*.py`, `*.md`, `deploy.sh`) | GitHub | да |
| `.env` — токены, ID канала, настройки инстанса | только на сервере | **нет** |
| `bot.db` — покупки, платежи | только на сервере | **нет** |
| `images/` — кэш картинок, докачивается сам | только на сервере | **нет** |
| `webhook_requests.log` — лог входящих вебхуков | только на сервере | **нет** |

Правило: **код едет только сверху вниз (GitHub → сервер), данные вверх не едут никогда.**
`git pull` физически не может затереть `.env` и `bot.db` — они в `.gitignore`.

Один и тот же репозиторий обслуживает все инстансы: код общий, различия — в `.env`.

---

## 1. Одноразовая настройка сервера

Делается один раз для каждой папки-инстанса. Превращает папку, залитую архивом, в git-клон
**без потери данных** — ни один файл не перезаписывается, пока ты сам этого не подтвердишь.

Bash-консоль PythonAnywhere:

```bash
cd ~/single_sales_bot && cp -a bot.db bot.db.before-git-$(date +%F) && cp -a .env .env.before-git-$(date +%F)
```

```bash
git init -b stable && git remote add origin https://github.com/george-dvoryak/single_sales_bot.git && git fetch origin stable
```

```bash
git reset origin/stable && git branch --set-upstream-to=origin/stable stable
```

`git reset` без флагов ставит индекс из репозитория, **рабочие файлы не трогает**. Теперь смотрим,
чем сервер отличается от репозитория:

```bash
git status --short
```

Как читать вывод:

* `??` перед `.env`, `bot.db`, `images/`, `__pycache__/` — так и должно быть, это данные инстанса.
* `??` перед чем-то ещё — файл есть на сервере, но нет в репозитории. Разберись, нужен ли он.
* `M` перед `.py` — **на сервере правили код руками**, и в репозитории этих правок нет. Сначала
  посмотри `git diff`, перенеси нужное на Mac, и только потом продолжай.

Когда в `M` ничего важного не осталось — приводим отслеживаемые файлы к состоянию репозитория:

```bash
git checkout -- .
```

Делаем скрипт деплоя исполняемым:

```bash
chmod +x deploy.sh
```

---

## 2. Ежедневный цикл

**На Mac** — правки, коммит, отправка:

```bash
git add -A && git commit -m "что сделал" && git push origin stable
```

**На сервере** — забрать и перезагрузить (одна команда на инстанс):

```bash
cd ~/single_sales_bot && ./deploy.sh
```

`deploy.sh` сам: делает бэкап `bot.db`, отказывается работать, если на сервере есть неучтённые
правки кода, делает `git pull --ff-only`, находит wsgi-файл именно этого веб-приложения и
перезагружает его (`touch` по wsgi-файлу = кнопка Reload на вкладке Web).

Проверка, что доехало:

```bash
curl -s https://ysingle-goshadvoryak.pythonanywhere.com/ && echo && cd ~/single_sales_bot && git log -1 --oneline
```

---

## 3. Второй инстанс (другой магазин)

Код общий, отличается только `.env`. Настройка та же, что в разделе 1, но в своей папке:

```bash
cd ~/ВТОРАЯ_ПАПКА && git init -b stable && git remote add origin https://github.com/george-dvoryak/single_sales_bot.git && git fetch origin stable
```

Дальше — `git reset origin/stable`, `git status --short`, разбор расхождений, `git checkout -- .`,
`chmod +x deploy.sh`. Деплой потом: `cd ~/ВТОРАЯ_ПАПКА && ./deploy.sh`.

Перед этим обязательно сравни код инстансов — если второй успел разойтись, `git checkout -- .`
затрёт его правки:

```bash
diff -rq -x .git -x __pycache__ -x images -x '*.db*' -x '.env*' -x '*.log*' ~/single_sales_bot ~/ВТОРАЯ_ПАПКА
```

* Расхождений нет или они только в `.env` → обе папки живут на одной ветке `stable`, правка
  один раз — деплой в две папки.
* Расхождения в коде и они нужны → либо перенести различия в `.env`/настройки (правильный путь),
  либо завести второму инстансу свою ветку (`git checkout -b shop2`) и деплоить его с неё.

---

## 4. Забрать `bot.db` на Mac для анализа

git этого не сделает и не должен. Способы:

* вкладка **Files** на PythonAnywhere → перейти в папку инстанса → скачать `bot.db`;
* если в тарифе есть SSH: `scp goshadvoryak@ssh.pythonanywhere.com:single_sales_bot/bot.db ./snapshots/`.

⚠️ **Скачанный `bot.db` — снимок для чтения. Никогда не заливай его обратно на сервер** — это
затрёт все продажи, случившиеся после снятия снимка. Локально держи снимки в отдельной папке
(`snapshots/`, она в `.gitignore`), а не под именем `bot.db`.

---

## 5. Если деплой сломал прод

Откат кода на предыдущую версию (на сервере):

```bash
cd ~/single_sales_bot && git log --oneline -5
```

```bash
git reset --hard <хэш_рабочей_версии> && touch /var/www/$(ls /var/www | grep wsgi | head -1)
```

Откат базы из бэкапа, который сделал `deploy.sh`:

```bash
cd ~/single_sales_bot && ls -t bot.db.backup-* | head -5
```

```bash
cp -a bot.db.backup-ВЫБРАННЫЙ bot.db
```

Логи, если приложение не поднялось: вкладка **Web** → Error log, или

```bash
tail -50 /var/log/ysingle-goshadvoryak.pythonanywhere.com.error.log
```
