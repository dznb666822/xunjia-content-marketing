# -*- coding: utf-8 -*-
"""
一次性迁移脚本：将 datas/app_data/*.json 导入 MySQL。

用法：
    1. 在 .env 中配置 MYSQL_HOST / MYSQL_PORT / MYSQL_USER / MYSQL_PASSWORD / MYSQL_DB
    2. python scripts/migrate_json_to_mysql.py

依赖 services/storage_mysql.py 的 save_all / load_all，表会在首次写入时自动创建。
"""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from services.storage_mysql import save_all, load_all

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "datas", "app_data",
)
ENTITIES = ["brands", "competitors", "tasks", "videos"]


def main():
    for entity in ENTITIES:
        path = os.path.join(DATA_DIR, "{}.json".format(entity))
        if not os.path.exists(path):
            print("[跳过] 无文件: {}".format(path))
            continue

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            data = []

        save_all(entity, data)
        db_count = len(load_all(entity))
        status = "OK" if db_count == len(data) else "FAIL"
        print("[{}] {}: 导入 {} 条 / JSON {} 条".format(status, entity, db_count, len(data)))


if __name__ == "__main__":
    main()
