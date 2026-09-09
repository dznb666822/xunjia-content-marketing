# -*- coding: utf-8 -*-
"""
迁移脚本：将现有 brands/competitors/videos/tasks 数据全部归属到管理员账号（admin）。

运行一次即可（幂等）：只处理 owner_id 为空的记录。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import storage
from services import user_auth


def main():
    user_auth.ensure_admin()
    admins = storage.find_by("users", lambda u: u.get("username") == user_auth.ADMIN_USERNAME)
    if not admins:
        print("未找到管理员账号，退出")
        return
    admin_id = admins[0]["id"]
    print("管理员账号 id =", admin_id)

    for entity in ["brands", "competitors", "videos", "tasks"]:
        items = storage.load_all(entity)
        count = 0
        for item in items:
            if not item.get("owner_id"):
                storage.update_one(entity, item["id"], {"owner_id": admin_id})
                count += 1
        print("{}: 共 {} 条，已归属管理员 {} 条".format(entity, len(items), count))


if __name__ == "__main__":
    main()
