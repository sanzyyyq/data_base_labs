import os
import sqlite3

import pandas as pd

# --- НАСТРОЙКИ ---
DB_NAME = "database.db"  # Имя создаваемой базы данных
EXCEL_DIR = "tables"  # Папка, где лежат ваши 3 файла Excel
# ------------------


def excel_to_sqlite(folder_path, db_name):
    # Подключаемся к базе данных
    conn = sqlite3.connect(db_name)

    if not os.path.isdir(folder_path):
        print(
            f"Ошибка: Папка {folder_path} не найдена. Создайте её и положите туда 3 файла."
        )
        return

    # Получаем список всех Excel файлов в папке
    files_to_process = [
        os.path.join(folder_path, f)
        for f in os.listdir(folder_path)
        if f.endswith((".xlsx", ".xls"))
    ]

    print(f"Найдено файлов для обработки: {len(files_to_process)}")

    for file_path in files_to_process:
        # Имя таблицы делаем по имени файла (без расширения)
        file_name_clean = os.path.splitext(os.path.basename(file_path))[0]
        table_name = file_name_clean.strip().replace(" ", "_").replace("-", "_").lower()

        print(f"Обработка файла: {os.path.basename(file_path)} -> Таблица: {table_name}")

        excel_file = pd.ExcelFile(file_path)

        # Переменная, чтобы перезаписать таблицу при первом листе и дописывать при следующих
        is_first_sheet = True
        total_rows = 0

        for sheet_name in excel_file.sheet_names:
            # Загружаем данные листа
            df = pd.read_excel(file_path, sheet_name=sheet_name)

            # Если лист пустой, пропускаем его
            if df.empty:
                continue

            # Очищаем заголовки колонок
            df.columns = [
                str(c).strip().replace(" ", "_").replace(".", "") for c in df.columns
            ]

            # Режим записи: replace для первого листа (чтобы очистить старую таблицу),
            # append для последующих листов этого же файла
            if_exists_mode = "replace" if is_first_sheet else "append"

            # Записываем в БД
            df.to_sql(table_name, conn, if_exists=if_exists_mode, index=False)
            is_first_sheet = False
            total_rows += len(df)

        print(
            f"  -> Таблица '{table_name}' успешно создана/обновлена. Всего строк: {total_rows}"
        )

    # Закрываем соединение
    conn.close()
    print(f"\nГотово! База данных с 3 таблицами сохранена в: {os.path.abspath(db_name)}")


if __name__ == "__main__":
    excel_to_sqlite(EXCEL_DIR, DB_NAME)
