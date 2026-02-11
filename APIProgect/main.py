from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
import json
import uvicorn
import os
import glob
from typing import Optional


app = FastAPI(
    title="Korean Words API",
    version="1.0"
)

# Настройка CORS - обязательно для мобильных приложений
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Разрешаем все источники для мобильного приложения
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Путь к JSON файлам
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_DIR = os.path.join(CURRENT_DIR, "data")


# ------------------- Утилиты -------------------

def get_all_json_files():
    """Получить все JSON файлы в текущей директории"""
    files = []
    for file_path in glob.glob(os.path.join(JSON_DIR, "*.json")):
        file_name = os.path.basename(file_path)
        files.append({
            "name": file_name,
            "path": file_path,
            "url": f"/file/{file_name}"
        })
    return files


def load_json_file(filename: str):
    """Загрузить КОНКРЕТНЫЙ JSON файл"""
    file_path = os.path.join(JSON_DIR, filename)
    if not os.path.exists(file_path):
        return None

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {filename}: {e}")
        return None


def save_json_file(filename: str, data: dict):
    """Сохранить данные в JSON файл"""
    file_path = os.path.join(JSON_DIR, filename)
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Error saving {filename}: {e}")
        return False


# ------------------- Простые эндпоинты -------------------

@app.get("/")
async def root():
    """Корневой эндпоинт - информация об API"""
    files = get_all_json_files()
    return {
        "api": "Korean Words API",
        "version": "1.0",
        "description": "Простой API для мобильного приложения на Kotlin",
        "endpoints": {
            "Список файлов в папке data: ": "/files",
            "Получить конкретный файл: ": "/file/{filename}",
            "Обновить значение по id_items в файле ": "/update/{filename}/{item_id}",
            "search": "/search/{filename}?q={query}",
            "stats": "/stats/{filename}",
            "health": "/health",
            "Методы API": "/method"
        },
        "available_files": files
    }


@app.get("/files")
async def list_files():
    """Получить список всех доступных JSON файлов"""
    files = get_all_json_files()
    return {
        "success": True,
        "count": len(files),
        "files": files
    }


@app.get("/file/{filename}")
async def get_file(filename: str):
    """Получить содержимое JSON файла полностью"""
    data = load_json_file(filename)
    if data is None:
        raise HTTPException(status_code=404, detail=f"File {filename} not found or invalid")

    return JSONResponse(
        content=data,
        headers={"Content-Type": "application/json; charset=utf-8"}
    )


@app.get("/search/{filename}")
async def search_in_file(
        filename: str,
        q: str,
        field: Optional[str] = None  # optional: russian, korean, example_russian, example_korean
):
    """Поиск по файлу"""
    data = load_json_file(filename)
    if data is None:
        raise HTTPException(status_code=404, detail=f"File {filename} not found")

    if "words" not in data:
        raise HTTPException(status_code=400, detail="Invalid file format: missing 'words' field")

    results = []
    query_lower = q.lower()

    for category in data["words"]:
        category_name = category.get("category", "")
        for item in category.get("items", []):
            # Поиск по всем полям если field не указан
            if field:
                # Поиск в конкретном поле
                if field in item:
                    text = str(item[field]).lower()
                    if query_lower in text:
                        item_copy = item.copy()
                        item_copy["category"] = category_name
                        results.append(item_copy)
            else:
                # Поиск во всех текстовых полях
                found = False
                for key, value in item.items():
                    if isinstance(value, str) and query_lower in value.lower():
                        found = True
                        break

                if found:
                    item_copy = item.copy()
                    item_copy["category"] = category_name
                    results.append(item_copy)

    return {
        "success": True,
        "query": q,
        "field": field,
        "filename": filename,
        "results": results,
        "count": len(results)
    }


@app.put("/update/{filename}/{item_id}")
async def update_item(
        filename: str,
        item_id: int,
        learned: Optional[bool] = None,
        custom_data: Optional[dict] = None
):
    """Обновить элемент в файле"""
    data = load_json_file(filename)
    if data is None:
        raise HTTPException(status_code=404, detail=f"File {filename} not found")

    if "words" not in data:
        raise HTTPException(status_code=400, detail="Invalid file format: missing 'words' field")

    item_found = False
    updated_item = None

    for category in data["words"]:
        for item in category.get("items", []):
            if item.get("id") == item_id:
                item_found = True

                # Обновляем поле learned если передано
                if learned is not None:
                    item["learned"] = learned

                # Обновляем кастомные поля если переданы
                if custom_data:
                    for key, value in custom_data.items():
                        item[key] = value

                updated_item = item.copy()
                updated_item["category"] = category.get("category", "")
                break

        if item_found:
            break

    if not item_found:
        raise HTTPException(status_code=404, detail=f"Item with id {item_id} not found in {filename}")

    # Сохраняем изменения
    if save_json_file(filename, data):
        return {
            "success": True,
            "message": "Item updated successfully",
            "filename": filename,
            "item_id": item_id,
            "item": updated_item
        }
    else:
        raise HTTPException(status_code=500, detail="Failed to save changes")


@app.get("/stats/{filename}")
async def get_file_stats(filename: str):
    """Получить статистику по файлу"""
    data = load_json_file(filename)
    if data is None:
        raise HTTPException(status_code=404, detail=f"File {filename} not found")

    if "words" not in data:
        raise HTTPException(status_code=400, detail="Invalid file format: missing 'words' field")

    total_items = 0
    total_learned = 0
    categories_stats = []

    for category in data["words"]:
        category_name = category.get("category", "")
        items = category.get("items", [])
        category_total = len(items)
        category_learned = sum(1 for item in items if item.get("learned", False))

        total_items += category_total
        total_learned += category_learned

        categories_stats.append({
            "category": category_name,
            "total": category_total,
            "learned": category_learned,
            "percentage": round((category_learned / category_total * 100) if category_total > 0 else 0, 1)
        })

    overall_percentage = round((total_learned / total_items * 100) if total_items > 0 else 0, 1)

    return {
        "success": True,
        "filename": filename,
        "overall": {
            "total_items": total_items,
            "learned_items": total_learned,
            "remaining": total_items - total_learned,
            "percentage": overall_percentage
        },
        "by_category": categories_stats
    }


@app.get("/health")
async def health_check():
    """Проверка здоровья API"""
    files = get_all_json_files()
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "available_files": len(files),
        "server": "Korean Words API"
    }


@app.get("/categories/{filename}")
async def get_categories(filename: str):
    """Получить список категорий из файла"""
    data = load_json_file(filename)
    if data is None:
        raise HTTPException(status_code=404, detail=f"File {filename} not found")

    if "words" not in data:
        raise HTTPException(status_code=400, detail="Invalid file format: missing 'words' field")

    categories = []
    for category in data["words"]:
        category_name = category.get("category", "")
        item_count = len(category.get("items", []))
        learned_count = sum(1 for item in category.get("items", []) if item.get("learned", False))

        categories.append({
            "name": category_name,
            "item_count": item_count,
            "learned_count": learned_count,
            "items": category.get("items", [])[:5]  # Первые 5 элементов для предпросмотра
        })

    return {
        "success": True,
        "filename": filename,
        "categories": categories,
        "total_categories": len(categories)
    }


@app.get("/item/{filename}/{item_id}")
async def get_item_by_id(filename: str, item_id: int):
    """Получить конкретный элемент по ID"""
    data = load_json_file(filename)
    if data is None:
        raise HTTPException(status_code=404, detail=f"File {filename} not found")

    if "words" not in data:
        raise HTTPException(status_code=400, detail="Invalid file format: missing 'words' field")

    for category in data["words"]:
        for item in category.get("items", []):
            if item.get("id") == item_id:
                result = item.copy()
                result["category"] = category.get("category", "")
                return {
                    "success": True,
                    "item": result
                }

    raise HTTPException(status_code=404, detail=f"Item with id {item_id} not found in {filename}")


# ------------------- Запуск сервера -------------------

def print_server_info():
    """Вывести информацию о сервере"""
    print("=" * 60)
    print("KOREAN WORDS API - Простой сервер для мобильного приложения")
    print("=" * 60)

    # Получаем локальный IP
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except:
        local_ip = "127.0.0.1"

    print(f"\n🌐 СЕРВЕР ЗАПУЩЕН:")
    print(f"   Локальный доступ:    http://127.0.0.1:8000")
    print(f"   Сеть:                http://{local_ip}:8000")

    print(f"\n📱 ДЛЯ МОБИЛЬНОГО ПРИЛОЖЕНИЯ KOTLIN:")
    print(f"   Базовый URL:         http://{local_ip}:8000")

    print(f"\n📂 ДОСТУПНЫЕ ФАЙЛЫ:")
    files = get_all_json_files()
    for file in files:
        print(f"   • {file['name']} ({file['size']} bytes)")

    print(f"\n🔧 ОСНОВНЫЕ ЭНДПОИНТЫ:")
    print(f"   GET  /                    - Информация об API")
    print(f"   GET  /files               - Список файлов")
    print(f"   GET  /file/{{filename}}     - Получить файл")
    print(f"   PUT  /update/{{filename}}/{{id}} - Обновить элемент")
    print(f"   GET  /search/{{filename}}   - Поиск")
    print(f"   GET  /stats/{{filename}}    - Статистика")

    print(f"\n📚 ДОКУМЕНТАЦИЯ:")
    print(f"   Swagger UI: http://127.0.0.1:8000/docs")
    print(f"   ReDoc:      http://127.0.0.1:8000/redoc")

    print(f"\n🚀 СЕРВЕР ЗАПУЩЕН! Готов к подключению мобильного приложения.")
    print("=" * 60)


if __name__ == "__main__":
    # Показываем информацию о сервере
    print_server_info()

    # Запускаем сервер
    uvicorn.run(
        app,
        host="0.0.0.0",  # Слушаем все интерфейсы
        port=8000,
        reload=False
    )