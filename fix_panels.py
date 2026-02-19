#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""AppData의 panels.json 파일을 수정하는 스크립트"""

import os
import json
from pathlib import Path
from datetime import datetime
import pytz

KST = pytz.timezone('Asia/Seoul')
appdata = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'News_System' / 'data' / 'overlay' / 'panels.json'

print(f'AppData panels.json 수정 도구')
print('=' * 60)

if appdata.exists():
    print(f'📂 파일 경로: {appdata}')
    
    with open(appdata, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f'📋 수정 전:')
    print(f'  - updated: "{data.get("updated", "")}"')
    print(f'  - resetToken: {data.get("resetToken", 0)}')
    
    # updated 필드를 현재 시간으로 업데이트
    old_updated = data.get('updated', '')
    data['updated'] = datetime.now(KST).strftime('%Y-%m-%d %H:%M')
    
    with open(appdata, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f'\n✅ 수정 완료!')
    print(f'  - updated: "{data["updated"]}"')
    print(f'  - resetToken: {data["resetToken"]}')
    print(f'\n💡 파일이 AppData에 저장되었습니다.')
    print(f'   설치 폴더의 overlay/panels.json과는 별개입니다.')
    
else:
    print(f'❌ 파일을 찾을 수 없습니다!')
    print(f'   예상 경로: {appdata}')
    print(f'   먼저 News System을 한 번 실행하세요.')
