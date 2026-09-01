#!/usr/bin/env bash
# Обновление инстанса на PythonAnywhere из GitHub + перезагрузка веб-приложения.
#
# Запускать в Bash-консоли PythonAnywhere ИЗ ПАПКИ ИНСТАНСА:
#     cd ~/single_sales_bot && ./deploy.sh
#
# Скрипт сам находит wsgi-файл именно этого веб-приложения, поэтому один и тот же
# файл работает для любого числа инстансов в разных папках.
# Данные инстанса (.env, bot.db, images/) не в git — pull их не трогает.
set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIR="$(pwd)"
echo "▶ Инстанс: $DIR"

# 1. Бэкап базы — её нет в git, это единственная копия
if [ -f bot.db ]; then
    BACKUP="bot.db.backup-$(date +%F_%H%M%S)"
    cp -a bot.db "$BACKUP"
    echo "✔ Бэкап базы: $BACKUP"
    # оставляем 7 последних бэкапов
    ls -t bot.db.backup-* 2>/dev/null | tail -n +8 | xargs -r rm -f
else
    echo "⚠ bot.db не найден — бэкап пропущен"
fi

# 2. Правки руками на сервере? Тогда pull остановить, иначе они молча исчезнут
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
    echo "✖ На сервере есть правки в отслеживаемых файлах — обновление остановлено:"
    git status --short --untracked-files=no
    echo
    echo "  Посмотреть, что изменено:  git diff"
    echo "  Выбросить правки сервера:  git checkout -- ."
    exit 1
fi

# 3. Забрать код
echo "▶ git pull"
git pull --ff-only

# 4. Перезагрузить веб-приложение (touch по wsgi-файлу = то же, что кнопка Reload)
WSGI="$(grep -lE "['\"]${DIR}['\"]" /var/www/*_wsgi.py 2>/dev/null | head -1 || true)"
if [ -n "$WSGI" ]; then
    touch "$WSGI"
    echo "✔ Веб-приложение перезагружено: $WSGI"
else
    echo "⚠ wsgi-файл для $DIR не найден — нажми Reload на вкладке Web вручную."
fi

echo "▶ Версия на сервере: $(git log -1 --pretty='%h %s')"
