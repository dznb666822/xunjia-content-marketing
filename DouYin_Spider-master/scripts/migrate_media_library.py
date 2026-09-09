# -*- coding: utf-8 -*-
"""
迁移脚本：将已有素材库视频文件及其分类数据写入 MySQL media_library 表（归属 admin）。

运行一次即可（幂等）：只处理数据库中尚不存在的视频。
"""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import storage
from services import user_auth
from services import video_mashup

VIDEO_EXTS = {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv'}
LIBRARY_JSON = os.path.join(video_mashup.UPLOAD_DIR, '_library.json')


def main():
    user_auth.ensure_admin()
    admins = storage.find_by("users", lambda u: u.get("username") == user_auth.ADMIN_USERNAME)
    if not admins:
        print("未找到管理员账号，退出")
        return
    admin_id = admins[0]["id"]
    print("管理员账号 id =", admin_id)

    # 旧磁盘分类缓存（如果存在）
    legacy = {}
    if os.path.exists(LIBRARY_JSON):
        try:
            with open(LIBRARY_JSON, 'r', encoding='utf-8') as fp:
                data = json.load(fp)
            if isinstance(data, dict):
                legacy = data
        except Exception as e:
            print("读取旧缓存失败:", e)

    existing = {m.get('id') for m in storage.load_all('media_library')}

    video_mashup.ensure_dirs()
    count = 0
    if os.path.isdir(video_mashup.UPLOAD_DIR):
        for f in os.listdir(video_mashup.UPLOAD_DIR):
            fpath = os.path.join(video_mashup.UPLOAD_DIR, f)
            if not os.path.isfile(fpath):
                continue
            ext = os.path.splitext(f)[1].lower()
            if ext not in VIDEO_EXTS:
                continue
            video_id = os.path.splitext(f)[0]
            if len(video_id) < 4:
                continue
            if video_id in existing:
                continue

            legacy_item = legacy.get(video_id, {})
            storage.save_one('media_library', {
                'id': video_id,
                'filename': legacy_item.get('filename', f),
                'path': fpath,
                'classification': legacy_item.get('classification'),
                'timeline': legacy_item.get('timeline'),
                'owner_id': admin_id,
            })
            count += 1

    print("已迁移 {} 个素材视频到 media_library（owner=admin）".format(count))


if __name__ == "__main__":
    main()
