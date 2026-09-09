# -*- coding: utf-8 -*-
"""实测抖音搜索接口真实可获取的字段，输出到 _verify_douyin.json"""
import os, sys, json, time, random

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.dirname(BASE))


def load_env():
    env = {}
    with open(os.path.join(os.path.dirname(BASE), '.env'), 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


env = load_env()
from builder.auth import DouyinAuth
from dy_apis.douyin_api import DouyinAPI

auth = DouyinAuth()
auth.perepare_auth(env.get('DY_COOKIES', ''))
auth.ticket = env.get('DY_TICKET', '')
auth.ts_sign = env.get('DY_TS_SIGN', '')
auth.client_cert = env.get('DY_CLIENT_CERT', '')
auth.private_key = env.get('DY_PRIVATE_KEY', '')

out = {'keyword': '宠物衣服', 'general': {}, 'video': {}, 'user_info': {}}

# 1) 综合搜索
try:
    resp = DouyinAPI.search_general_work(auth, '宠物衣服', sort_type='0', publish_time='0')
    data = resp.get('data') or []
    works = [w for w in data if w.get('aweme_info')]
    first = works[0]['aweme_info'] if works else {}
    out['general'] = {
        'resp_keys': list(resp.keys()),
        'data_count': len(data),
        'aweme_count': len(works),
        'aweme_info_keys': list(first.keys()) if first else [],
        'sample': {
            'aweme_id': first.get('aweme_id'),
            'desc': first.get('desc'),
            'create_time': first.get('create_time'),
            'statistics': first.get('statistics'),
            'cha_list': first.get('cha_list'),
            'text_extra': first.get('text_extra'),
            'author_keys': list(first.get('author', {}).keys()) if first.get('author') else [],
            'author': {
                'nickname': first.get('author', {}).get('nickname'),
                'sec_uid': first.get('author', {}).get('sec_uid'),
                'follower_count': first.get('author', {}).get('follower_count'),
            },
        },
    }
    print('[general] data=%d aweme=%d keys=%s' % (len(data), len(works), list(resp.keys())))
    if first:
        st = first.get('statistics') or {}
        print('[general] desc=%s' % (first.get('desc') or '')[:40])
        print('[general] stat=digg:%s comment:%s share:%s collect:%s play:%s' % (
            st.get('digg_count'), st.get('comment_count'), st.get('share_count'),
            st.get('collect_count'), st.get('play_count')))
        print('[general] cha_list=%s text_extra=%s' % (first.get('cha_list'), first.get('text_extra')))
        print('[general] author.follower_count=%s' % first.get('author', {}).get('follower_count'))
except Exception as e:
    out['general']['error'] = str(e)
    print('[general] ERROR', e)

time.sleep(random.uniform(5, 10))

# 2) 视频频道搜索（含引导词 guide_search_words）
try:
    search_id, guide, resp = DouyinAPI.search_video_work(auth, '宠物衣服', offset='0', count='16', sort_type='0', publish_time='0')
    data = resp.get('data') or []
    first = data[0].get('aweme_info', {}) if data else {}
    out['video'] = {
        'resp_keys': list(resp.keys()),
        'guide_search_words': guide,
        'data_count': len(data),
        'sample_desc': first.get('desc'),
        'sample_statistics': first.get('statistics'),
        'sample_author_follower': first.get('author', {}).get('follower_count'),
    }
    print('[video] data=%d guide=%s' % (len(data), json.dumps(guide, ensure_ascii=False)[:80]))
except Exception as e:
    out['video']['error'] = str(e)
    print('[video] ERROR', e)

time.sleep(random.uniform(5, 10))

# 3) 用第一个作者的 sec_uid 二次调用 get_user_info，验证粉丝数
try:
    resp = DouyinAPI.search_general_work(auth, '宠物衣服', sort_type='0', publish_time='0')
    works = [w for w in (resp.get('data') or []) if w.get('aweme_info')]
    if works:
        sec_uid = works[0]['aweme_info']['author'].get('sec_uid')
        if sec_uid:
            info = DouyinAPI.get_user_info(auth, 'https://www.douyin.com/user/' + sec_uid)
            user = info.get('user') or {}
            out['user_info'] = {
                'sec_uid': sec_uid,
                'nickname': user.get('nickname'),
                'follower_count': user.get('follower_count'),
                'following_count': user.get('following_count'),
                'total_favorited': user.get('total_favorited'),
                'aweme_count': user.get('aweme_count'),
                'user_keys': list(user.keys()) if user else [],
            }
            print('[user_info] nickname=%s follower=%s following=%s aweme=%s' % (
                user.get('nickname'), user.get('follower_count'),
                user.get('following_count'), user.get('aweme_count')))
except Exception as e:
    out['user_info']['error'] = str(e)
    print('[user_info] ERROR', e)

with open(os.path.join(BASE, '_verify_douyin.json'), 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=2, default=str)
print('done -> _verify_douyin.json')
